#!/usr/bin/env python3
"""Create a SOPS-encrypted proxy environment Secret for one explicit consumer."""
import argparse
import json
import os
import pathlib
import re
import subprocess
import urllib.parse
parser=argparse.ArgumentParser()
parser.add_argument('--namespace',required=True)
parser.add_argument('--name',default='cyberghost-egress-proxy')
parser.add_argument('--output',type=pathlib.Path,required=True)
parser.add_argument('--replace',action='store_true')
a=parser.parse_args()
for value in [a.namespace,a.name]:
    if len(value)>63 or not re.fullmatch('[a-z0-9](?:[a-z0-9-]*[a-z0-9])?',value):
        raise SystemExit('Invalid Kubernetes namespace or Secret name')
app=pathlib.Path(__file__).resolve().parents[1];gitops=app.parent
output=a.output.resolve()
if gitops not in output.parents or not output.parent.is_dir():
    raise SystemExit('Output must be inside an existing GitOps application folder')
env=os.environ.copy();env['SOPS_AGE_KEY_FILE']=str(gitops/'keys.txt')
def run(args,**kwargs):
    try:return subprocess.run(args,check=True,capture_output=True,**kwargs).stdout
    except subprocess.CalledProcessError:raise SystemExit('Secret preparation failed; sensitive diagnostics omitted') from None
if output.exists():
    if not a.replace:raise SystemExit('Output already exists; explicit --replace required')
    previous=json.loads(run(['sops','--decrypt','--output-type','json',str(output)],env=env))
    if previous['metadata'].get('name')!=a.name or previous['metadata'].get('namespace')!=a.namespace:
        raise SystemExit('Existing Secret ownership does not match this consumer')
source=json.loads(run(['sops','--decrypt','--output-type','json',str(app/'secrets.yaml')],env=env))['stringData']
user=urllib.parse.quote(source['httpproxy_user'],safe='');password=urllib.parse.quote(source['httpproxy_password'],safe='')
proxy='http://'+user+':'+password+'@cyberghost-egress.cyberghost-egress.svc.cluster.local:8888'
no_proxy='localhost,127.0.0.1,::1,.svc,.svc.cluster.local,10.0.0.0/16,10.1.0.0/16,169.254.169.254'
data={key:proxy for key in ['HTTP_PROXY','HTTPS_PROXY','http_proxy','https_proxy']}
data.update({'NO_PROXY':no_proxy,'no_proxy':no_proxy})
secret={'apiVersion':'v1','kind':'Secret','metadata':{'name':a.name,'namespace':a.namespace},'type':'Opaque','stringData':data}
enc=run(['sops','--encrypt','--age','age103wy5wh49l0ptpscalt4ywxezd2nqykd29jru0fvgen7aweffp2s99kne9','--input-type','json','--output-type','yaml','/dev/stdin'],input=json.dumps(secret).encode())
assert source['httpproxy_password'].encode() not in enc and b'ENC[AES256_GCM' in enc
output.write_bytes(enc)
assert json.loads(run(['sops','--decrypt','--output-type','json',str(output)],env=env))==secret
print('Created encrypted consumer proxy environment Secret; no credentials displayed.')
