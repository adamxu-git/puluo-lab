"""Launch Tart and capture its guest serial output without forwarding input."""

import errno
import fcntl
import ipaddress
import os
from pathlib import Path
import pty
import selectors
import socket
import subprocess
import sys
import tty


SERIAL_LOG_LIMIT = 32 * 1024 * 1024


def capture_serial(events, vm, network, serial, output, log_path):
    size = output.tell()
    try:
        while vm.poll() is None:
            for key, _ in events.select(timeout=0.25):
                if key.fileobj is network:
                    network.recv(65536)
                    continue
                try:
                    data = serial.read(65536)
                except OSError as error:
                    if error.errno != errno.EIO:
                        raise
                    continue
                if size + len(data) > SERIAL_LOG_LIMIT:
                    output.close()
                    log_path.replace(log_path.with_name(log_path.name + '.1'))
                    output = log_path.open('ab', buffering=0)
                    size = 0
                size += output.write(data)
    finally:
        output.close()


def network_rules(mode):
    if mode == 'offline':
        return []
    rules = ['in proto tcp @host port 22'] if mode == 'provision' else []
    allowlist = 'provision' if mode == 'build' else mode
    state = Path(os.environ.get('PULUO_VM_STATE', Path(__file__).resolve().parent / 'state'))
    path = state / f'{allowlist}-ipv4.txt'
    if path.exists():
        for line in path.read_text().splitlines():
            address = ipaddress.IPv4Address(line)
            if not address.is_global or address.is_multicast:
                raise ValueError(f'Allowlist contains a non-public address: {address}')
            rules.append(f'out proto tcp {address}/32 port 443')
    args = ['--net-softnet-block', 'in,out,out @host']
    if rules:
        args.extend(['--net-softnet-allow', ','.join(rules)])
    return args


def run(cli, name, log, mode, seed=None):
    master, slave = pty.openpty()
    tty.setraw(slave)
    network, guest = socket.socketpair(socket.AF_UNIX, socket.SOCK_DGRAM)
    with network, guest, os.fdopen(master, 'rb', buffering=0) as serial, os.fdopen(slave, 'rb', buffering=0):
        args = [cli, 'run', '--no-graphics', '--no-clipboard', '--no-audio',
                '--no-usb-accessories', '--serial-path', os.ttyname(slave)]
        if mode == 'offline':
            args.extend(['--net-fd', str(guest.fileno())])
        else:
            args.extend(network_rules(mode))
        if seed:
            args.extend(['--disk', f'{Path(seed).resolve(strict=True)}:ro'])
        args.append(name)
        log_path = Path(log)
        lock_path = log_path.with_name(log_path.name + '.lock')
        with lock_path.open('ab') as lock, selectors.DefaultSelector() as events:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with subprocess.Popen(args, pass_fds=(guest.fileno(),)) as vm:
                guest.close()
                events.register(network, selectors.EVENT_READ)
                events.register(master, selectors.EVENT_READ)
                try:
                    capture_serial(events, vm, network, serial, log_path.open('ab', buffering=0), log_path)
                finally:
                    if vm.poll() is None:
                        vm.terminate()
                return vm.wait()


if __name__ == '__main__':
    if len(sys.argv) not in (5, 6) or sys.argv[4] not in ('offline', 'provision', 'isolated', 'build'):
        sys.exit('Usage: launch.py TART VM LOG MODE [SEED]')
    sys.exit(run(*sys.argv[1:]))
