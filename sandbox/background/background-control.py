#!/usr/bin/python3
"""Accept only fixed operations on the one unprivileged background unit."""
import socket
import subprocess

UNIT = 'puluo-background.service'
COMMANDS = {
    b'start\n': ['start', UNIT],
    b'stop\n': ['stop', UNIT],
    b'status\n': ['show', UNIT, '-p', 'ActiveState', '-p', 'SubState', '-p', 'Result', '-p', 'MainPID'],
}


def main():
    with socket.socket(fileno=0) as connection:
        connection.settimeout(3)
        with connection.makefile('rb') as stream:
            request = stream.readline(32)
        command = COMMANDS.get(request)
        if command is None:
            connection.sendall(b'Unsupported operation\n')
            return
        result = subprocess.run(['/usr/bin/systemctl', *command], capture_output=True, timeout=10)
        action = command[0]
        with open('/dev/hvc0', 'w') as audit:
            audit.write(f'PULUO_BACKGROUND {action} exit={result.returncode}\n')
        output = result.stdout or result.stderr or b'OK\n'
        connection.sendall((b'OK\n' if result.returncode == 0 else b'ERROR\n') + output)


if __name__ == '__main__':
    main()
