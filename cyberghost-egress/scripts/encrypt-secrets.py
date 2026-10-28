#!/usr/bin/env python3
"""Validate local CyberGhost material and emit only an encrypted GitOps Secret."""
import argparse
import json
import os
import pathlib
import secrets
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument('--credentials-dir', type=pathlib.Path, required=True)
parser.add_argument('--replace', action='store_true', help='Explicitly replace an existing encrypted Secret')
args = parser.parse_args()
app = pathlib.Path(__file__).resolve().parents[1]
gitops = app.parent
folder = args.credentials_dir.resolve()
required = ['password.txt', 'client.crt', 'client.key']
missing = [name for name in required if not (folder / name).is_file()]
if missing:
    raise SystemExit('Missing credential files: ' + ', '.join(missing))
if (app / 'secrets.yaml').exists() and not args.replace:
    raise SystemExit('Encrypted Secret exists; use --replace only for an authorized rotation')
folder.chmod(0o700)
for name in ['username.txt', 'password.txt', 'client.key']:
    if (folder / name).exists():
        (folder / name).chmod(0o600)

def run(command, **kwargs):
    try:
        return subprocess.run(command, check=True, capture_output=True, **kwargs).stdout
    except subprocess.CalledProcessError:
        raise SystemExit('Credential validation/encryption failed; sensitive diagnostics omitted') from None

auth_lines = (folder / 'password.txt').read_text().splitlines()
if (folder / 'username.txt').exists():
    user = (folder / 'username.txt').read_text().strip()
    password = (folder / 'password.txt').read_text().strip()
elif len(auth_lines) == 2 and all(line.strip() for line in auth_lines):
    # Standard OpenVPN auth-user-pass file: username, then password.
    user, password = (line.strip() for line in auth_lines)
    print('Using the supplied standard two-line OpenVPN authentication file.')
else:
    raise SystemExit('Provide username.txt, or a two-line OpenVPN authentication file in password.txt')
if not user or not password or '\n' in user or '\n' in password:
    raise SystemExit('Manual OpenVPN username/password must each contain one nonempty line')
certificate = (folder / 'client.crt').read_text()
key = (folder / 'client.key').read_text()
run(['openssl', 'x509', '-in', str(folder / 'client.crt'), '-checkend', '86400', '-noout'])
public_certificate = run(['openssl', 'x509', '-in', str(folder / 'client.crt'), '-pubkey', '-noout'])
public_certificate = run(['openssl', 'pkey', '-pubin', '-outform', 'DER'], input=public_certificate)
public_key = run(['openssl', 'pkey', '-in', str(folder / 'client.key'), '-passin', 'pass:', '-pubout', '-outform', 'DER'])
if public_key != public_certificate:
    raise SystemExit('Client certificate and private key do not match')
if (folder / 'ca.crt').exists():
    run(['openssl', 'verify', '-CAfile', str(folder / 'ca.crt'), str(folder / 'client.crt')])
proxy_password_file = folder / 'proxy-password'
if not proxy_password_file.exists():
    fd = os.open(proxy_password_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as stream:
        stream.write(secrets.token_urlsafe(48))
proxy_password_file.chmod(0o600)
proxy_password = proxy_password_file.read_text().strip()
if len(proxy_password) < 32:
    raise SystemExit('Proxy password must contain at least 32 characters')
secret = {
    'apiVersion': 'v1', 'kind': 'Secret',
    'metadata': {'name': 'cyberghost-egress-secrets'}, 'type': 'Opaque',
    'stringData': {
        'openvpn_user': user, 'openvpn_password': password,
        'openvpn_clientcrt': certificate, 'openvpn_clientkey': key,
        'httpproxy_user': 'cluster', 'httpproxy_password': proxy_password,
    },
}
recipient = 'age103wy5wh49l0ptpscalt4ywxezd2nqykd29jru0fvgen7aweffp2s99kne9'
encrypted = run(['sops', '--encrypt', '--age', recipient, '--input-type', 'json', '--output-type', 'yaml', '/dev/stdin'], input=json.dumps(secret).encode())
if b'ENC[AES256_GCM' not in encrypted or key.strip().encode() in encrypted or password.encode() in encrypted:
    raise SystemExit('Encryption verification failed')
target = app / 'secrets.yaml'
target.write_bytes(encrypted)
env = os.environ.copy()
env['SOPS_AGE_KEY_FILE'] = str(gitops / 'keys.txt')
decrypted = run(['sops', '--decrypt', '--output-type', 'json', str(target)], env=env)
if json.loads(decrypted) != secret:
    target.unlink()
    raise SystemExit('Encrypted Secret round-trip verification failed')
print('Validated certificate/key and encrypted the VPN/proxy credentials. No secret values displayed.')
