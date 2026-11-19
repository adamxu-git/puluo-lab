"""Check repository source syntax without booting a VM or using network access."""

import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def main():
    paths = subprocess.check_output(
        ['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard',
         '--', 'sandbox', 'scripts/check.py'],
        cwd=ROOT,
    )
    checked = 0
    failed = False
    for name in sorted(set(paths.split(b'\0')) - {b''}):
        path = Path(os.fsdecode(name))
        source = ROOT / path
        if not source.is_file():
            continue
        try:
            if path.suffix == '.py':
                compile(source.read_bytes(), str(path), 'exec')
            elif path.suffix == '.js':
                subprocess.run(['node', '--check', path], cwd=ROOT, check=True)
            elif path.suffix == '.json':
                json.loads(source.read_text(encoding='utf-8'))
            elif path.suffix == '.sh' or path.name == 'instance-env':
                subprocess.run(['bash', '-n', path], cwd=ROOT, check=True)
            elif not path.suffix and source.read_bytes().startswith(b'#!/bin/bash\n'):
                subprocess.run(['bash', '-n', path], cwd=ROOT, check=True)
            else:
                continue
            checked += 1
        except (SyntaxError, ValueError, OSError, subprocess.CalledProcessError) as error:
            print(f'{path}: {error}', file=sys.stderr)
            failed = True

    print(f'Validated {checked} source files.')
    return int(failed)


if __name__ == '__main__':
    sys.exit(main())
