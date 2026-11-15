#!/usr/bin/python3
"""Run a single DSH turn as experiment and send audit records to the serial port."""

import datetime
import fcntl
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import uuid


CONFIG = Path('/etc/puluo')
STATE = Path('/var/lib/puluo')
ACCOUNT = Path('/home/experiment')
SESSION_ID = re.compile(r'session-[0-9a-f-]{36}\Z')


def run(mode, audit):
    test = mode == 'test'
    prompt = sys.stdin.read() if test else (CONFIG / 'wake.txt').read_text()
    if not prompt.strip():
        raise ValueError('A nonempty prompt is required')
    secret = (CONFIG / 'deepseek-key').read_text().strip()
    if not secret:
        raise ValueError('DeepSeek API Key is missing')
    state = STATE / mode
    state.mkdir(mode=0o700, parents=True, exist_ok=True)
    session_file = state / 'session-id'
    expected = session_file.read_text().strip() if session_file.exists() else None
    if expected is not None and not SESSION_ID.fullmatch(expected):
        raise ValueError('Saved session ID is invalid')

    run_id = uuid.uuid4().hex

    def emit(kind, **fields):
        stamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
        line = json.dumps({'time': stamp, 'run': run_id, 'mode': mode, 'kind': kind, **fields})
        audit.write(line.replace(secret, '[REDACTED]') + '\n')

    emit('start', session=expected)
    workspace = ACCOUNT / ('acceptance' if test else 'workspace')
    env = {
        'PATH': '/opt/puluo/node/bin:/usr/sbin:/usr/bin:/sbin:/bin',
        'HOME': str(ACCOUNT),
        'DSH_HOME': str(ACCOUNT / ('.dsh-acceptance' if test else '.dsh-puluo')),
        'DEEPSEEK_API_KEY': secret,
        'DSH_TELEMETRY_DISABLED': '1',
        'LANG': 'C.UTF-8',
    }
    cmd = ['/usr/sbin/runuser', '-u', 'experiment', '--',
           '/opt/puluo/runtime/node_modules/.bin/dsh', 'headless', '--patch',
           str(CONFIG / 'guest.cordis.yml')]
    patch = CONFIG / ('acceptance.yml' if test else 'system-prompt.yml')
    if not test or patch.is_file():
        cmd.extend(['--patch', str(patch)])
    cmd.extend(['--json', '--permission-mode', 'workspace-write', '--approval-policy', 'never'])
    if expected:
        cmd.extend(['--session-id', expected])
    cmd.extend(['--', prompt])
    session = None
    final = None
    with subprocess.Popen(cmd, cwd=workspace, env=env, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, text=True, errors='replace') as process:
        for line in process.stdout:
            try:
                event = json.loads(line)
            except ValueError:
                emit('diagnostic', text=line.rstrip())
                continue
            if not isinstance(event, dict):
                emit('diagnostic', text=line.rstrip())
                continue
            emit('dsh', event=event)
            if event.get('type') == 'session':
                session = event.get('sessionId')
            elif event.get('type') == 'final':
                final = event
        status = process.wait()
    reason = final.get('reason') if final else None
    valid = (isinstance(session, str) and SESSION_ID.fullmatch(session) and
             (expected is None or session == expected) and final and
             final.get('sessionId') == session and isinstance(reason, dict) and
             reason.get('kind') == 'completed')
    if status == 0 and valid and not expected:
        pending = state / '.session-id.tmp'
        pending.write_text(session + '\n')
        pending.replace(session_file)
    emit('exit', status=status, valid=bool(valid))
    return status or (0 if valid else 1)


if __name__ == '__main__':
    if len(sys.argv) != 2 or sys.argv[1] not in ('test', 'experiment'):
        sys.exit('Usage: guest-run.py {test|experiment}')
    os.umask(0o077)
    STATE.mkdir(mode=0o700, exist_ok=True)
    with (STATE / 'run.lock').open('a') as lock, open('/dev/hvc0', 'w', buffering=1) as serial:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        sys.exit(run(sys.argv[1], serial))
