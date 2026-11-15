#!/usr/bin/python3
"""Small stdio MCP server for the experiment's background task."""
import json
import socket
import sys

TOOLS = {
    'start': 'Start the one background task. Create .puluo-background.py in your workspace first. It runs as your account, can use VM loopback, and expires after two hours.',
    'status': 'Read the state of your background task, which can run between conversation turns.',
    'stop': 'Stop your background task and its subprocesses.',
}


def call(action):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.settimeout(12)
        connection.connect('/run/puluo-background.sock')
        connection.sendall(action.encode('ascii') + b'\n')
        with connection.makefile('rb') as stream:
            result = stream.read(4096).decode(errors='replace')
    return result.startswith('OK\n'), result.removeprefix('OK\n').removeprefix('ERROR\n').strip()


def handle(message):
    method = message.get('method')
    if method == 'initialize':
        return {'protocolVersion': '2024-11-05', 'capabilities': {'tools': {}},
                'serverInfo': {'name': 'puluo-background', 'version': '1.0'}}
    if method == 'ping':
        return {}
    if method == 'tools/list':
        return {'tools': [{'name': name, 'description': description,
                           'inputSchema': {'type': 'object', 'additionalProperties': False}}
                          for name, description in TOOLS.items()]}
    if method == 'tools/call':
        action = message.get('params', {}).get('name')
        if action not in TOOLS:
            raise ValueError('Unknown operation')
        try:
            ok, value = call(action)
        except OSError as error:
            ok, value = False, str(error)
        return {'content': [{'type': 'text', 'text': value}], 'isError': not ok}
    raise ValueError('Unknown MCP method')


def main():
    for line in sys.stdin:
        message = json.loads(line)
        if 'id' not in message:
            continue
        reply = {'jsonrpc': '2.0', 'id': message['id']}
        try:
            reply['result'] = handle(message)
        except (ValueError, TypeError) as error:
            reply['error'] = {'code': -32602, 'message': str(error)}
        print(json.dumps(reply), flush=True)


if __name__ == '__main__':
    main()
