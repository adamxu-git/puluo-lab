"""Read-only local dashboard for Tart and the host's serial audit log."""

from collections import OrderedDict
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
from threading import Lock
from urllib.parse import urlsplit

HERE = Path(__file__).resolve().parent
SANDBOX = HERE.parent
BEIJING = timezone(timedelta(hours=8))
ASSETS = {
    '/': ('index.html', 'text/html; charset=utf-8'),
    '/style.css': ('style.css', 'text/css; charset=utf-8'),
    '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
}
USAGE_KEYS = ('inputTokens', 'outputTokens', 'cacheReadTokens', 'cacheWriteTokens', 'totalTokens')
MAX_RUNS = 48
MAX_EVENTS = 48
MAX_LINE = 256 * 1024


def clip(value, limit=1800):
    if not isinstance(value, str):
        value = json.dumps(value, ensure_ascii=False)
    return value if len(value) <= limit else value[:limit] + '…'


def records(paths):
    pending = b''
    discard = False
    for path in paths:
        try:
            stream = path.open('rb')
        except FileNotFoundError:
            continue
        with stream:
            for chunk in iter(lambda: stream.readline(MAX_LINE + 1), b''):
                finished = chunk.endswith(b'\n')
                if discard or len(pending) + len(chunk) > MAX_LINE:
                    pending = b''
                    discard = not finished
                    continue
                pending += chunk
                if finished:
                    try:
                        entry = json.loads(pending)
                    except (ValueError, RecursionError):
                        if pending.lstrip().startswith(b'{'):
                            yield None
                    else:
                        if isinstance(entry, dict):
                            yield entry
                    pending = b''
    # The current file may end mid-write. A later refresh can read the whole line.


def read_audit(paths):
    runs = OrderedDict()
    skipped = 0
    for row in records(paths):
        if row is None:
            skipped += 1
            continue
        key = row.get('run')
        mode = row.get('mode')
        stamp = row.get('time')
        if (not isinstance(key, str) or not re.fullmatch('[0-9a-f]{32}', key)
                or mode not in ('experiment', 'test') or not isinstance(stamp, str)):
            continue
        active = runs.setdefault(key, {
            'id': key, 'mode': mode, 'start': None, 'end': None,
            'last': stamp, 'turn': None, 'session': None, 'summary': '',
            'state': 'unconfirmed', 'usage': {}, 'events': [],
            'toolCount': 0, 'eventCount': 0,
        })
        while len(runs) > MAX_RUNS:
            runs.popitem(last=False)
        active['last'] = stamp
        kind = row.get('kind')
        event = row.get('event')
        action = None
        if kind == 'start':
            active['start'] = stamp
            active['state'] = 'started'
        elif kind == 'exit':
            active['end'] = stamp
            active['state'] = 'complete' if row.get('status') == 0 and row.get('valid') is True else 'failed'
            action = ('进程退出', f"退出码 {row.get('status')}")
        elif kind == 'diagnostic':
            action = ('系统消息', clip(row.get('text', '')))
        elif kind == 'dsh' and isinstance(event, dict):
            typ = event.get('type')
            if typ == 'session':
                active['session'] = clip(event.get('sessionId', ''), 80)
            elif typ == 'final':
                active['summary'] = clip(event.get('text') or '', 2400)
                reason = event.get('reason')
                if not active['summary'] and reason:
                    active['summary'] = clip(reason)
                action = ('最终汇报', active['summary'])
            elif typ == 'status' and event.get('phase') == 'turn_start':
                active['turn'] = event.get('turn')
            elif typ == 'status' and event.get('phase') == 'step_end':
                usage = event.get('usage')
                if isinstance(usage, dict):
                    for field in USAGE_KEYS:
                        amount = usage.get(field)
                        if type(amount) is int and 0 <= amount <= 10**9:
                            active['usage'][field] = active['usage'].get(field, 0) + amount
            elif typ == 'tool_call':
                active['toolCount'] += 1
                tool = clip(event.get('tool', ''), 120)
                action = ('调用 ' + tool.removeprefix('mcp__browser__'), clip(event.get('input')))
            elif typ == 'tool_result':
                action = ('工具结果 · ' + clip(event.get('status', ''), 40), clip(event.get('result')))
            elif typ == 'error':
                active['summary'] = clip(event.get('message', ''))
                action = ('错误', active['summary'])
        if action:
            active['eventCount'] += 1
            active['events'].append({'time': stamp, 'title': action[0], 'text': action[1]})
            del active['events'][:-MAX_EVENTS]
    return runs, skipped


def signature(path):
    try:
        stat = path.stat()
        return (stat.st_ino, stat.st_size, stat.st_mtime_ns)
    except FileNotFoundError:
        return None


class Dashboard:
    def __init__(self, name):
        self.name = name
        self.logs = SANDBOX / 'logs' if name == 'puluo-ubuntu' else SANDBOX / 'instances' / name / 'logs'
        self.paths = (self.logs / 'serial.log.1', self.logs / 'serial.log')
        self.latest_signature = None
        self.audit = ({}, 0)
        self.vm_cache = (0, None)
        self.audit_lock = Lock()

    def refresh(self):
        with self.audit_lock:
            current = tuple(signature(path) for path in self.paths)
            if current != self.latest_signature:
                self.audit = read_audit(self.paths)
                self.latest_signature = current
            return self.audit

    def vm(self, now):
        checked, cached = self.vm_cache
        if now.timestamp() - checked < 10:
            return cached
        try:
            cmd = [str(SANDBOX / 'tools/tart.app/Contents/MacOS/tart'), 'list', '--format', 'json']
            env = dict(os.environ, TART_HOME=str(SANDBOX / 'tart'))
            machines = json.loads(subprocess.check_output(cmd, env=env, timeout=3, stderr=subprocess.DEVNULL))
            cached = next((machine for machine in machines if machine.get('Name') == self.name), None)
        except (OSError, ValueError, subprocess.SubprocessError):
            cached = None
        self.vm_cache = (now.timestamp(), cached)
        return cached

    def status(self):
        now = datetime.now(BEIJING)
        vm = self.vm(now) or {}
        disk_path = SANDBOX / 'tart' / 'vms' / self.name / 'disk.img'
        try:
            allocated = disk_path.stat().st_blocks * 512
        except OSError:
            allocated = None
        try:
            timer = json.loads((self.logs / 'dashboard-timer.json').read_text())
        except (OSError, ValueError):
            timer = {}
        hours = [23, 0, 1, 2, 3, 4]
        slots = sorted(datetime.combine(day, datetime.min.time(), BEIJING).replace(hour=hour)
                       for day in (now.date(), now.date() + timedelta(days=1)) for hour in hours)
        upcoming = next(slot for slot in slots if slot > now)
        runs, skipped = self.refresh()
        return {
            'name': self.name, 'now': now.isoformat(), 'vm': vm.get('Running'),
            'allocated': allocated, 'capacity': vm.get('Disk'),
            'timer': timer, 'calendarNext': upcoming.isoformat(), 'hours': hours,
            'logBytes': sum(info[1] for info in self.latest_signature if info),
            'rotated': self.latest_signature[0] is not None,
            'skipped': skipped,
            'runs': [{key: value for key, value in run.items() if key != 'events'}
                     for run in reversed(runs.values())],
        }


class Handler(BaseHTTPRequestHandler):
    timeout = 5

    def send_content(self, data, content_type, status=200):
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Cross-Origin-Resource-Policy', 'same-origin')
        self.send_header('Content-Security-Policy',
                         "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; "
                         "base-uri 'none'; frame-ancestors 'none'; form-action 'none'")
        self.end_headers()
        self.wfile.write(data)

    def send_json(self, data, status=200):
        self.send_content(json.dumps(data, ensure_ascii=True).encode(), 'application/json', status)

    def do_GET(self):
        port = self.server.server_port
        if self.headers.get('Host') not in (f'127.0.0.1:{port}', f'localhost:{port}'):
            return self.send_json({'error': 'Invalid host'}, 403)
        if self.headers.get('Sec-Fetch-Site') == 'cross-site':
            return self.send_json({'error': 'Cross-site request'}, 403)
        path = urlsplit(self.path).path
        if path in ASSETS:
            file, content_type = ASSETS[path]
            return self.send_content((HERE / file).read_bytes(), content_type)
        if path == '/api/status':
            return self.send_json(self.server.dashboard.status())
        match = re.fullmatch('/api/runs/([0-9a-f]{32})', path)
        if match:
            runs, _ = self.server.dashboard.refresh()
            if match[1] in runs:
                return self.send_json(runs[match[1]])
        return self.send_json({'error': 'Not found'}, 404)

    def log_message(self, format, *args):
        pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--instance', default=os.environ.get('PULUO_VM_NAME', 'puluo-ubuntu'))
    args = parser.parse_args()
    if not re.fullmatch('[a-z][a-z0-9-]{0,39}', args.instance) or args.instance == 'puluo-golden':
        parser.error('Choose an experiment VM name')
    with ThreadingHTTPServer(('127.0.0.1', args.port), Handler) as server:
        server.dashboard = Dashboard(args.instance)
        print(f'Puluo Lab · http://127.0.0.1:{server.server_port}', flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == '__main__':
    main()
