#!/usr/bin/env python3
"""Render and validate the shared egress manifests without exposing Secret data."""
import json
import hashlib
import os
import pathlib
import re
import subprocess
import tempfile

app = pathlib.Path(__file__).resolve().parents[1]
gitops = app.parent
kube = ['kubectl', '--kubeconfig', str(gitops.parent / '.kube/config'), '--context', 'jshipster']
env = os.environ.copy()
env['SOPS_AGE_KEY_FILE'] = str(gitops / 'keys.txt')
with tempfile.TemporaryDirectory(prefix='cyberghost-egress-check-') as folder:
    temporary = pathlib.Path(folder)
    resources = ['namespace.yaml', 'deployment.yaml', 'service.yaml', 'configmap.yaml']
    for name in resources:
        (temporary / name).write_bytes((app / name).read_bytes())
    if (app / 'secrets.yaml').is_file():
        decrypted = subprocess.check_output(['sops', '--decrypt', '--output-type', 'json', str(app / 'secrets.yaml')], env=env)
        secret = json.loads(decrypted)
        assert secret['metadata']['name'] == 'cyberghost-egress-secrets'
        assert all(secret['stringData'].get(name) for name in ['openvpn_user', 'openvpn_password', 'openvpn_clientcrt', 'openvpn_clientkey', 'httpproxy_user', 'httpproxy_password'])
        (temporary / 'secret.json').write_bytes(decrypted)
        (temporary / 'secret.json').chmod(0o600)
        resources.append('secret.json')
    (temporary / 'kustomization.yaml').write_text(json.dumps({'apiVersion':'kustomize.config.k8s.io/v1beta1','kind':'Kustomization','namespace':'cyberghost-egress','resources':resources}))
    rendered = subprocess.check_output(kube + ['kustomize', folder])
    # Client dry-run validates against the cluster OpenAPI schema; no resources are created.
    output = subprocess.run(kube + ['create', '--dry-run=client', '--validate=true', '-f', '-', '-o', 'json'], input=rendered, capture_output=True)
    if output.returncode:
        raise SystemExit('Manifest schema validation failed; rendered secrets and diagnostics omitted')
    objects = []
    decoder = json.JSONDecoder()
    remaining = output.stdout.decode().lstrip()
    while remaining:
        item, end = decoder.raw_decode(remaining)
        objects.extend(item['items'] if item.get('kind')=='List' else [item])
        remaining = remaining[end:].lstrip()
    deployment = next(x for x in objects if x['kind']=='Deployment')
    service = next(x for x in objects if x['kind']=='Service')
    config = next(x for x in objects if x['kind']=='ConfigMap')['data']
    annotations = deployment['spec']['template']['metadata']['annotations']
    assert annotations['checksum/config']==hashlib.sha256((app/'configmap.yaml').read_bytes()).hexdigest()
    assert annotations['checksum/credentials']==hashlib.sha256((app/'secrets.yaml').read_bytes()).hexdigest()
    pod = deployment['spec']['template']['spec']
    container = pod['containers'][0]
    assert deployment['spec']['replicas']==1 and deployment['spec']['strategy']['type']=='Recreate'
    assert not pod.get('hostNetwork') and not pod.get('hostPID') and not pod.get('hostIPC')
    assert pod['automountServiceAccountToken'] is False
    assert not any('hostPath' in volume for volume in pod['volumes'])
    security = container['securityContext']
    assert security['privileged'] is False and security['allowPrivilegeEscalation'] is False
    assert security['readOnlyRootFilesystem'] is True
    assert security['capabilities']['drop']==['ALL']
    assert set(security['capabilities']['add'])=={'NET_ADMIN','MKNOD'}
    assert re.fullmatch(r'ghcr.io/qdm12/gluetun@sha256:[0-9a-f]{64}',container['image'])
    assert container['resources']['requests'] and container['resources']['limits']
    assert len(pod['initContainers'])==1
    initializer = pod['initContainers'][0]
    assert initializer['image']==container['image']
    assert initializer['securityContext']['capabilities']['drop']==['ALL']
    assert not initializer['securityContext']['capabilities'].get('add')
    assert initializer['resources']['requests'] and initializer['resources']['limits']
    assert 'mknod -m 0600' in container['args'][0]
    assert any(mount['mountPath']=='/etc/resolv.conf' and mount['subPath']=='resolv.conf' for mount in container['volumeMounts'])
    assert config['VPN_SERVICE_PROVIDER']=='cyberghost' and config['SERVER_COUNTRIES']=='Israel'
    assert config['FIREWALL_ENABLED_DISABLING_IT_SHOOTS_YOU_IN_YOUR_FOOT']=='on'
    assert config['FIREWALL_OUTBOUND_SUBNETS']=='10.1.1.0/24'
    assert config['HTTPPROXY']=='on' and config['HTTPPROXY_LOG']=='off'
    assert config['HTTP_CONTROL_SERVER_ADDRESS'].startswith('127.0.0.1:')
    assert all(not volume.get('secret',{}).get('optional',False) for volume in pod['volumes'])
    assert service['spec']['type']=='ClusterIP' and len(service['spec']['ports'])==1 and service['spec']['ports'][0]['port']==8888
print('Manifest schema, pinned image, Israel selection, private service, firewall, capabilities and encrypted credential references verified.')
