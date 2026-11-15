"""Launch Tart and capture its guest serial output without forwarding input."""

import errno
import ipaddress
import os
from pathlib import Path
import pty
import selectors
import socket
import subprocess
import sys
import tty


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
        with open(log, 'ab', buffering=0) as output, selectors.DefaultSelector() as events:
            with subprocess.Popen(args, pass_fds=(guest.fileno(),)) as vm:
                guest.close()
                events.register(network, selectors.EVENT_READ)
                events.register(master, selectors.EVENT_READ)
                try:
                    while vm.poll() is None:
                        for key, _ in events.select(timeout=0.25):
                            if key.fileobj is network:
                                network.recv(65536)
                                continue
                            try:
                                output.write(serial.read(65536))
                            except OSError as error:
                                if error.errno != errno.EIO:
                                    raise
                finally:
                    if vm.poll() is None:
                        vm.terminate()
                return vm.wait()


if __name__ == '__main__':
    if len(sys.argv) not in (5, 6) or sys.argv[4] not in ('offline', 'provision', 'isolated', 'build'):
        sys.exit('Usage: launch.py TART VM LOG MODE [SEED]')
    sys.exit(run(*sys.argv[1:]))
