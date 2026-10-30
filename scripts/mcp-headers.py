#!/usr/bin/env python3
"""Emit owner-only MCP bearer headers. Stdout is a secret-bearing protocol."""
import json
import os
from pathlib import Path
import stat
import sys

ROOT = Path(__file__).resolve().parents[2]
FILES = {
    'anpr': ROOT / 'ANPR-Shikmim/data/private/mcp-auth-token',
    'tivtaam': ROOT / 'tivtaam-mcp/private/auth-token',
    'mashov': ROOT / 'mashov-mcp/private/auth-token',
    'webtop': ROOT / 'webtop-mcp/private/auth-token',
    'multi-whatsapp': ROOT / 'multi-whatsapp/private/auth-token',
}
try:
    if len(sys.argv) != 2 or sys.argv[1] not in FILES:
        raise ValueError('Unknown MCP')
    fd = os.open(FILES[sys.argv[1]], os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd) as source:
        info = os.fstat(source.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise ValueError('Private token permissions required')
        token = source.read(4097).strip()
    if not 32 <= len(token) <= 4096 or any(c.isspace() for c in token):
        raise ValueError('Invalid token')
except (OSError, ValueError):
    print('MCP credential unavailable; check the owner-only token file.', file=sys.stderr)
    sys.exit(1)
print(json.dumps({'Authorization': 'Bearer ' + token}))
