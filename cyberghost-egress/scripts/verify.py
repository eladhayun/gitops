#!/usr/bin/env python3
"""Check the live proxy from the existing bastion without displaying credentials."""
import argparse
import base64
import json
import pathlib
import subprocess
import sys
parser=argparse.ArgumentParser()
parser.add_argument('--webtop',action='store_true',help='Also check anonymous Webtop API access')
a=parser.parse_args()
gitops=pathlib.Path(__file__).resolve().parents[2]
kube=['kubectl','--kubeconfig',str(gitops.parent/'.kube/config'),'--context','jshipster']
secret=json.loads(subprocess.check_output(kube+['-n','cyberghost-egress','get','secret','cyberghost-egress-secrets','-o','json']))['data']
user=base64.b64decode(secret['httpproxy_user']).decode()
password=base64.b64decode(secret['httpproxy_password']).decode()
pods=json.loads(subprocess.check_output(kube+['-n','default','get','pods','-l','app=jshipster-bastion','-o','json']))['items']
if not pods:raise SystemExit('Diagnostic bastion unavailable')
remote=r'''
import base64,http.client,json,sys,urllib.request,urllib.error,urllib.parse
settings=json.load(sys.stdin)
host='cyberghost-egress.cyberghost-egress.svc.cluster.local'
result={}
def connect_status(auth=None):
 connection=http.client.HTTPConnection(host,8888,timeout=10)
 try:
  headers={}
  if auth is not None:headers['Proxy-Authorization']='Basic '+base64.b64encode(auth.encode()).decode()
  connection.request('CONNECT','webtopserver.smartschool.co.il:443',headers=headers)
  return connection.getresponse().status
 finally:connection.close()
try:
 result['missing_auth_status']=connect_status()
 result['wrong_auth_status']=connect_status(settings['user']+':deliberately-invalid')
 proxy='http://'+urllib.parse.quote(settings['user'],safe='')+':'+urllib.parse.quote(settings['password'],safe='')+'@'+host+':8888'
 opener=urllib.request.build_opener(urllib.request.ProxyHandler({'http':proxy,'https':proxy}))
 with opener.open('https://www.cloudflare.com/cdn-cgi/trace',timeout=25) as response:
  text=response.read(16384).decode()
 result['exit_country']=dict(line.split('=',1) for line in text.splitlines() if '=' in line).get('loc')
 if settings['webtop']:
  request=urllib.request.Request('https://webtopserver.smartschool.co.il/server/api/dashboard/InitDashboard',data=b'{}',headers={'Content-Type':'application/json'})
  try:
   with opener.open(request,timeout=25) as response:result['webtop_anonymous_status']=response.status
  except urllib.error.HTTPError as error:result['webtop_anonymous_status']=error.code
 result['success']=result['missing_auth_status']==407 and result['wrong_auth_status'] in (401,407) and result['exit_country']=='IL' and (not settings['webtop'] or result['webtop_anonymous_status']==401)
except Exception:
 result['success']=False
 result['request_failed']=True
print(json.dumps(result))
'''
result=subprocess.run(kube+['-n','default','exec','-i',pods[0]['metadata']['name'],'--','python3','-c',remote],input=json.dumps({'user':user,'password':password,'webtop':a.webtop}).encode(),capture_output=True)
try:report=json.loads(result.stdout)
except Exception:raise SystemExit('Proxy verification failed; sensitive diagnostics omitted') from None
print(json.dumps(report))
sys.exit(0 if report.get('success') else 1)
