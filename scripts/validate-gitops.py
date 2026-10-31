#!/usr/bin/env python3
"""Validate deployable GitOps without credentials or executing repository plugins."""
import json
import pathlib
import shutil
import subprocess
import tempfile

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
CUSTOM = {"Application", "ApplicationSet", "AppProject", "Certificate", "ClusterIssuer",
          "Issuer", "Connector", "ProxyClass", "Rollout", "AnalysisTemplate",
          "ServiceMonitor", "PrometheusRule", "CustomResourceDefinition"}


def load(path):
    return list(yaml.safe_load_all(path.read_text()))


def check_source(source):
    if "github.com/jshipster-io/gitops" in source.get("repoURL", ""):
        assert source.get("targetRevision") == "production", "GitOps source must track production"


def validate(root=ROOT):
    # Copy only tracked files: never copy local age keys, credentials or caches.
    files = subprocess.check_output(["git", "ls-files", "-z"], cwd=root).decode().split("\0")
    with tempfile.TemporaryDirectory(prefix="gitops-validation-") as tmp:
        tree = pathlib.Path(tmp).resolve()
        for name in filter(None, files):
            src = root / name
            assert not src.is_symlink(), f"Symlinks are not allowed: {name}"
            dest = tree / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dest)
            text = src.read_text(errors="replace")
            # Construct the markers so this validator does not match itself.
            assert "AGE-SECRET-" + "KEY-1" not in text, f"Private age key: {name}"
            assert "-----BEGIN " + "OPENSSH PRIVATE KEY-----" not in text, f"Private SSH key: {name}"
            if src.suffix in {".yaml", ".yml"} and "templates" not in src.parts:
                load(src)  # Parse all YAML, including workflows and inactive manifests.

        # KSOPS is intentionally not executed in CI. Verify encryption and remove
        # generators in the disposable copy; Argo CD alone holds the age key.
        for path in tree.rglob("kustomization.yaml"):
            data = load(path)[0]
            for generator in data.pop("generators", []):
                gen = load(path.parent / generator)[0]
                assert gen.get("kind") == "ksops", f"Unexpected generator: {generator}"
                for filename in gen["files"]:
                    secret = (path.parent / filename).resolve()
                    assert secret.is_relative_to(tree), "Generator escapes repository"
                    for doc in load(secret):
                        assert doc.get("sops", {}).get("mac", "").startswith("ENC["), f"Missing SOPS integrity metadata: {filename}"
                        payload = doc.get("data", {}) | doc.get("stringData", {})
                        assert payload, f"Empty encrypted payload: {filename}"
                        assert all(isinstance(v, str) and v.startswith("ENC[") for v in payload.values()), f"Plaintext secret: {filename}"
            assert not data.get("transformers"), "Executable transformers are not allowed"
            path.write_text(yaml.safe_dump(data, sort_keys=False))

        apps = list(yaml.safe_load_all(subprocess.check_output(["kustomize", "build", str(tree / "apps")], text=True)))
        targets = {"apps"}
        for app in apps:
            if app["kind"] == "Application":
                spec = app["spec"]
                for source in spec.get("sources", [spec.get("source", {})]):
                    check_source(source)
                    if "github.com/jshipster-io/gitops" in source.get("repoURL", ""):
                        targets.add(source["path"])
            elif app["kind"] == "ApplicationSet":
                check_source(app["spec"]["template"]["spec"]["source"])
                for generator in app["spec"]["generators"]:
                    assert generator["git"]["revision"] == "production", "ApplicationSet must read production"
        # Root app is not listed in apps/kustomization.yaml.
        check_source(load(tree / "apps/apps.yaml")[0]["spec"]["source"])
        count = 0
        for target in sorted(targets):
            path = (tree / target).resolve()
            assert path.is_relative_to(tree), "Application path escapes repository"
            config = load(path / "kustomization.yaml")[0]
            if not any(config.get(k) for k in ("resources", "components", "configMapGenerator", "secretGenerator", "helmCharts")):
                print(f"PASS {target} (empty retirement manifest)")
                continue
            rendered = subprocess.check_output(["kustomize", "build", str(path)], text=True)
            count += validate_rendered(rendered)
            print(f"PASS {target}")
        chart = tree / "multi-whatsapp/worker-chart"
        subprocess.run(["helm", "lint", str(chart), "--set-string",
                        "accountID=00000000-0000-0000-0000-000000000000"], check=True)
        for account in (tree / "multi-whatsapp/accounts").glob("*.json"):
            data = json.loads(account.read_text())
            assert isinstance(data["enabled"], bool)
            rendered = subprocess.check_output(["helm", "template", "validation", str(chart),
                "--set-string", f"accountID={data['account_id']}",
                "--set", f"enabled={str(data['enabled']).lower()}",
                "--set", f"generation={data['generation']}"], text=True)
            count += validate_rendered(rendered)
        print(f"Validated {count} resources; encrypted secret contents are not decrypted in CI.")


def validate_rendered(rendered):
    docs = [d for d in yaml.safe_load_all(rendered) if d]
    standard = []
    for doc in docs:
        assert doc.get("apiVersion") and doc.get("kind") and doc.get("metadata", {}).get("name"), "Incomplete resource"
        if doc["kind"] == "Secret":
            assert not (doc.get("data") or doc.get("stringData")), "Plaintext Secret in rendered manifests"
        if doc["kind"] == "Service" and doc.get("spec", {}).get("type") in {"LoadBalancer", "NodePort"}:
            assert all(p.get("port") != 22 and p.get("targetPort") not in {22, "ssh"}
                       for p in doc["spec"].get("ports", [])), "SSH must stay private behind Tailscale"
        if doc["kind"] not in CUSTOM:
            standard.append(doc)
    result = subprocess.run(["kubeconform", "-strict", "-summary", "-kubernetes-version", "1.35.0"],
                            input=yaml.safe_dump_all(standard), text=True, capture_output=True)
    if result.returncode:
        raise RuntimeError(result.stdout + result.stderr)
    return len(docs)


if __name__ == "__main__":
    validate()
