#!/usr/bin/env python3
"""Restart the VPN through GitOps when config or encrypted credentials change."""
import hashlib
import pathlib
import re
app = pathlib.Path(__file__).resolve().parents[1]
path = app / 'deployment.yaml'
text = path.read_text()
values = {name: hashlib.sha256((app / file).read_bytes()).hexdigest() for name,file in [('config','configmap.yaml'),('credentials','secrets.yaml')]}
if 'checksum/config:' not in text:
    marker = '    metadata:\n      labels:'
    if text.count(marker)!=1:
        raise SystemExit('Unexpected pod template shape')
    annotations = '    metadata:\n      annotations:\n' + ''.join('        checksum/'+key+': '+value+'\n' for key,value in values.items()) + '      labels:'
    text = text.replace(marker,annotations,1)
else:
    for key,value in values.items():
        text,count = re.subn(r'(?m)^        checksum/'+key+r': .+$','        checksum/'+key+': '+value,text)
        if count!=1:
            raise SystemExit('Unexpected checksum annotation shape')
path.write_text(text)
print('Updated pod-template config/credential checksums without exposing secret data.')
