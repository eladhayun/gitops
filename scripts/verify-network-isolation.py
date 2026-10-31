#!/usr/bin/env python3
"""Run disposable TCP policy probes; requires explicit --run and owner kubeconfig.

Creates one unprivileged probe pod per node in default and one backup-client
probe in pg-backups. Deletes only the pods it created. Does not access credentials
or send application messages. Authenticated service checks are performed separately.
"""
import argparse
import json
import shlex
import subprocess
import time


def kubectl(*args, **kwargs):
    return subprocess.check_output(["kubectl", "--context", "jshipster", *args], text=True, **kwargs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", required=True)
    parser.parse_args()
    config = json.loads(kubectl("get", "configmap", "cilium-config", "-n", "kube-system", "-o", "json"))
    assert config["data"].get("enable-policy") == "default", "Wait for managed migration to enable policy enforcement"
    nodes = json.loads(kubectl("get", "nodes", "-o", "json"))["items"]
    assert all(any(c["type"] == "Ready" and c["status"] == "True" for c in n["status"]["conditions"]) for n in nodes)
    ds = json.loads(kubectl("get", "daemonset", "cilium", "-n", "kube-system", "-o", "json"))
    assert ds["status"].get("numberReady") == len(nodes), "Cilium must be ready on every node"
    targets = [("postgres", "shared-postgres", 5432), ("argocd", "argocd-server", 443),
               ("argocd", "argocd-repo-server", 8081), ("argocd", "argocd-redis", 6379),
               ("mashov-mcp", "mashov-mcp", 8081), ("webtop-mcp", "webtop-mcp", 8081),
               ("tivtaam-mcp", "tivtaam-mcp", 8081), ("multi-whatsapp", "multi-whatsapp-manager", 8080)]
    checks = []
    for ns, service, port in targets:
        svc = json.loads(kubectl("get", "service", service, "-n", ns, "-o", "json"))
        checks.append({"name": ns + "/" + service, "host": svc["spec"]["clusterIP"], "port": port, "allowed": False})
    created = []
    stamp = str(int(time.time()))
    specs = [("default", "deny-" + str(i), n["metadata"]["name"], {}, checks) for i, n in enumerate(nodes)]
    specs.append(("pg-backups", "backup", None, {"app": "pg-backup"}, [{**checks[0], "allowed": True}]))
    try:
        for ns, suffix, node, labels, tests in specs:
            name = "network-policy-probe-" + stamp + "-" + suffix
            commands = ["sleep 5", "failed=0"]
            for check in tests:
                expected = str(check["allowed"]).lower()
                commands.extend([
                    f"if nc -z -w 4 {shlex.quote(check['host'])} {check['port']}; then connected=true; else connected=false; fi",
                    f"printf '%s connected=%s expected=%s\\n' {shlex.quote(check['name'])} \"$connected\" {expected}",
                    f'[ "$connected" = "{expected}" ] || failed=1',
                ])
            commands.append('exit "$failed"')
            pod = {"apiVersion": "v1", "kind": "Pod", "metadata": {"name": name, "namespace": ns, "labels": labels},
                   "spec": {"restartPolicy": "Never", "activeDeadlineSeconds": 240,
                            "automountServiceAccountToken": False,
                            "securityContext": {"runAsNonRoot": True, "runAsUser": 1000, "seccompProfile": {"type": "RuntimeDefault"}},
                            "containers": [{"name": "probe", "image": "alpine:3.23",
                                            "command": ["sh", "-c", "\n".join(commands)],
                                            "securityContext": {"allowPrivilegeEscalation": False, "readOnlyRootFilesystem": True, "capabilities": {"drop": ["ALL"]}},
                                            "resources": {"requests": {"cpu": "5m", "memory": "2Mi"}, "limits": {"cpu": "100m", "memory": "16Mi"}}}]}}
            if node:
                pod["spec"]["nodeName"] = node
            kubectl("create", "-f", "-", input=json.dumps(pod))
            created.append((ns, name))
        pending = set(created)
        failed = []
        deadline = time.monotonic() + 270
        while pending and time.monotonic() < deadline:
            for ns, name in list(pending):
                pod = json.loads(kubectl("get", "pod", name, "-n", ns, "-o", "json"))
                phase = pod["status"]["phase"]
                if phase in {"Succeeded", "Failed"}:
                    print(ns + "/" + name, phase, flush=True)
                    print(pod["status"].get("message", ""), flush=True)
                    if any(s.get("state", {}).get("terminated") for s in pod["status"].get("containerStatuses", [])):
                        print(kubectl("logs", name, "-n", ns), flush=True)
                    if phase != "Succeeded":
                        failed.append(name)
                    pending.remove((ns, name))
            if pending:
                time.sleep(3)
        assert not pending and not failed, f"Unfinished: {pending}; failed: {failed}"
        print("PASS: denied access from every node and allowed backup-to-database access")
    finally:
        for ns, name in created:
            kubectl("delete", "pod", name, "-n", ns, "--ignore-not-found", "--wait=false")
    # Existing Alpine containers provide zero-I/O TCP checks. These retain the
    # real app identity and avoid creating service-selected diagnostic pods.
    for ns in ("mashov-mcp", "webtop-mcp", "tivtaam-mcp"):
        for host, port, expected in [
            ("shared-postgres.postgres.svc.cluster.local", 5432, True),
            ("cyberghost-egress.cyberghost-egress.svc.cluster.local", 8888, True),
            ("argocd-server.argocd.svc.cluster.local", 443, False),
            ("jshipster-bastion.default.svc.cluster.local", 22, False),
        ]:
            result = subprocess.run(["kubectl", "--context", "jshipster", "-n", ns,
                                     "exec", "deploy/" + ns, "--", "nc", "-z", "-w", "3", host, str(port)],
                                    capture_output=True, text=True, timeout=15)
            connected = result.returncode == 0
            print(json.dumps({"source": ns, "target": host, "connected": connected, "expected": expected}), flush=True)
            assert connected == expected, "Unexpected MCP egress result: " + result.stderr
    print("PASS: MCP database/proxy egress allowed; Argo and bastion egress denied")


if __name__ == "__main__":
    main()
