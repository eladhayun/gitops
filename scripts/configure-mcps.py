#!/usr/bin/env python3
"""Install consistent owner MCP HTTP entries, preserving unrelated Codex settings."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import tempfile
import tomllib

URLS = {
    'anpr': 'http://anpr-cloud.anpr.svc.cluster.local/mcp',
    'tivtaam': 'http://tivtaam-mcp.tivtaam-mcp.svc.cluster.local:8081/mcp',
    'mashov': 'http://mashov-mcp.mashov-mcp.svc.cluster.local:8081/mcp',
    'webtop': 'http://webtop-mcp.webtop-mcp.svc.cluster.local:8081/mcp',
    'multi-whatsapp': 'http://multi-whatsapp-manager.multi-whatsapp.svc.cluster.local:8080/mcp',
}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=Path.home() / '.codex/config.toml')
    parser.add_argument('--server', choices=URLS)
    args = parser.parse_args()
    path = args.config.expanduser().resolve()
    source = path.read_text()
    previous = tomllib.loads(source)
    names = [args.server] if args.server else list(URLS)
    helper = Path(__file__).resolve().with_name('mcp-headers.py')
    output = source
    replaced_names = set(names)
    if 'tivtaam' in names:
        servers = previous.get('mcp_servers', {})
        legacy = servers.get('tivtaam-mcp')
        current = servers.get('tivtaam')
        if legacy is not None and current is not None and legacy != current:
            raise ValueError('Both TivTaam names exist with different settings; reconcile them before installing')
        output = re.sub(r'(?ms)^\[mcp_servers\.tivtaam-mcp(?:\.[^\]]+)?\][^\n]*\n.*?(?=^\[|\Z)', '', output)
        replaced_names.add('tivtaam-mcp')
    for name in names:
        pattern = r'(?ms)^\[mcp_servers\.' + re.escape(name) + r'(?:\.[^\]]+)?\][^\n]*\n.*?(?=^\[|\Z)'
        output = re.sub(pattern, '', output)
        # Keep explicit tool allow/deny lists when replacing the transport.
        servers = previous.get('mcp_servers', {})
        restrictions = servers.get(name, servers.get('tivtaam-mcp', {}) if name == 'tivtaam' else {})
        preserved = ''.join(f'{key} = {json.dumps(restrictions[key])}\n' for key in ('enabled_tools', 'disabled_tools', 'enabled') if key in restrictions)
        command = f'{helper} {name}'
        tool_timeout = max(360, restrictions.get('tool_timeout_sec', 90)) if name == 'tivtaam' else 90
        output = output.rstrip() + f'\n\n[mcp_servers.{name}]\nurl = {json.dumps(URLS[name])}\nhttp_headers_helper = {json.dumps(command)}\nstartup_timeout_sec = 30\ntool_timeout_sec = {tool_timeout}\n' + preserved
    updated = tomllib.loads(output)
    if 'tivtaam' in names and 'tivtaam-mcp' in updated['mcp_servers']:
        raise ValueError('Legacy TivTaam entry was not migrated')
    for name, value in previous.get('mcp_servers', {}).items():
        if name not in replaced_names and updated['mcp_servers'].get(name) != value:
            raise ValueError('Unrelated MCP configuration changed')
    if {k:v for k,v in previous.items() if k != 'mcp_servers'} != {k:v for k,v in updated.items() if k != 'mcp_servers'}:
        raise ValueError('Unrelated configuration changed')
    backup = path.with_name(path.name + '.backup-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as target:
        target.write(source)
    fd, temporary = tempfile.mkstemp(prefix='.mcp-config-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as target:
            target.write(output)
            target.flush()
            os.fsync(target.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    print('Configured ' + ', '.join(names) + '; owner-only backup created. Reload Codex to reconnect.')

if __name__ == '__main__':
    main()
