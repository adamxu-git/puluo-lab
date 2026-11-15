"""Render the guest's proxy ACL and nftables rules from validated IPv4 inputs."""

import ipaddress
from pathlib import Path
import subprocess
import sys


def main():
    source = Path(__file__).resolve().parent
    state, output = map(Path, sys.argv[1:])
    model = [ipaddress.IPv4Address(line) for line in
             (state / 'isolated-ipv4.txt').read_text().splitlines()]
    if not model or any(not address.is_global or address.is_multicast for address in model):
        sys.exit('The model API allowlist must contain public IPv4 addresses.')
    restricted = [ipaddress.IPv4Network(line) for line in
                  (source / 'restricted-ipv4.txt').read_text().splitlines()]
    interfaces = subprocess.check_output(['/sbin/ifconfig', '-a'], text=True)
    for line in interfaces.splitlines():
        columns = line.split()
        if columns and columns[0] == 'inet':
            address = ipaddress.IPv4Address(columns[1])
            if address.is_global and not address.is_multicast:
                restricted.append(ipaddress.IPv4Network(f'{address}/32'))
    blocked = list(ipaddress.collapse_addresses(restricted))
    (output / 'browser-deny-ipv4.txt').write_text(''.join(f'{net}\n' for net in blocked))
    rules = (source / 'egress.nft').read_text()
    rules = rules.replace('@BLOCKED@', ', '.join(map(str, blocked)))
    rules = rules.replace('@MODEL@', ', '.join(map(str, sorted(set(model)))))
    (output / 'browser-egress.nft').write_text(rules)


if __name__ == '__main__':
    main()
