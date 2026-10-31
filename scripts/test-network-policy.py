#!/usr/bin/env python3
"""Regression checks for the intended pod-to-pod allow/deny matrix.

This evaluates selectors and additive L4 rules for these manifests; live Cilium
connectivity tests remain necessary to verify routing, NAT and enforcement.
"""
from pathlib import Path
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[1]
PATHS = {"postgres": "shared-postgres", "argocd": "argocd-network-policy",
         "multi-whatsapp": "multi-whatsapp/manager",
         **{n: n for n in ("mashov-mcp", "webtop-mcp", "tivtaam-mcp")}}
POLICIES = {ns: list(yaml.safe_load_all((ROOT / path / "network-policy.yaml").read_text()))
            for ns, path in PATHS.items()}


def matches(selector, labels):
    if not all(labels.get(k) == v for k, v in selector.get("matchLabels", {}).items()):
        return False
    for expr in selector.get("matchExpressions", []):
        assert expr["operator"] == "In", "Extend the evaluator for new selector operators"
        if labels.get(expr["key"]) not in expr["values"]:
            return False
    return True


def allowed_side(subject, other, direction, port):
    ns, labels = subject
    selected = [p["spec"] for p in POLICIES.get(ns, [])
                if direction.title() in p["spec"]["policyTypes"]
                and matches(p["spec"]["podSelector"], labels)]
    if not selected:
        return True
    key = "from" if direction == "ingress" else "to"
    for policy in selected:
        for rule in policy.get(direction, []):
            if "ports" in rule and not any(p["port"] == port and p.get("protocol", "TCP") == "TCP" for p in rule["ports"]):
                continue
            if key not in rule:
                return True
            for peer in rule[key]:
                # In Cilium an ipBlock does not identify an in-cluster pod.
                if "ipBlock" in peer:
                    continue
                if "namespaceSelector" in peer:
                    if not matches(peer["namespaceSelector"], {"kubernetes.io/metadata.name": other[0]}):
                        continue
                elif ns != other[0]:
                    continue
                if matches(peer.get("podSelector", {}), other[1]):
                    return True
    return False


def connection(src, dst, port):
    return allowed_side(src, dst, "egress", port) and allowed_side(dst, src, "ingress", port)


class NetworkPolicyTests(unittest.TestCase):
    def test_connection_matrix(self):
        db = ("postgres", {"app": "shared-postgres"})
        outsider = ("default", {"app": "unrelated"})
        router = ("tailscale", {"tailscale.com/parent-resource": "jshipster-aks", "tailscale.com/parent-resource-type": "connector"})
        server = ("argocd", {"app.kubernetes.io/name": "argocd-server"})
        repo = ("argocd", {"app.kubernetes.io/name": "argocd-repo-server"})
        controller = ("argocd", {"app.kubernetes.io/name": "argocd-application-controller"})
        cases = [(outsider, db, 5432, False), (router, db, 5432, True),
                 (("default", {"app": "jshipster-bastion"}), db, 5432, True),
                 (("pg-backups", {"app": "pg-backup"}), db, 5432, True),
                 (("multi-whatsapp", {"app.kubernetes.io/name": "multi-whatsapp-migrate"}), db, 5432, True),
                 (("postgres", {"app": "shared-postgres-tls-reload"}), db, 5432, True),
                 (("jshipster", {"app": "drc-weekly-summary"}), db, 5432, True),
                 (outsider, server, 8080, False), (outsider, repo, 8081, False),
                 (router, server, 8080, True), (router, repo, 8081, False),
                 (("argocd", {"app": "cloudflared"}), server, 8080, True),
                 (controller, repo, 8081, True)]
        for ns in ("mashov-mcp", "webtop-mcp", "tivtaam-mcp"):
            mcp = (ns, {"app": ns})
            cases += [(mcp, db, 5432, True), (router, mcp, 8081, True),
                      (outsider, mcp, 8081, False), (mcp, server, 8080, False),
                      (mcp, ("cyberghost-egress", {"app": "cyberghost-egress"}), 8888, True)]
        for src, dst, port, expected in cases:
            with self.subTest(src=src, dst=dst, port=port):
                self.assertEqual(connection(src, dst, port), expected)

    def test_namespace_default_deny(self):
        for ns, policies in POLICIES.items():
            for direction in ("Ingress", "Egress"):
                self.assertTrue(any(not p["spec"]["podSelector"] and direction in p["spec"]["policyTypes"] for p in policies), (ns, direction))


if __name__ == "__main__":
    unittest.main()
