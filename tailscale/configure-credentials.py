#!/usr/bin/env python3
"""Prompt locally and write only SOPS-encrypted OAuth credentials to disk."""

import getpass
import json
from pathlib import Path
import subprocess


def main():
    directory = Path(__file__).resolve().parent
    target = directory / "secrets.yaml"
    if target.exists():
        raise SystemExit("secrets.yaml already exists; use sops to edit it instead.")
    client_id = getpass.getpass("Tailscale OAuth client ID: ").strip()
    client_secret = getpass.getpass("Tailscale OAuth client secret: ").strip()
    if not client_id or not client_secret:
        raise SystemExit("Both OAuth values are required. No files written.")
    secret = {
        "apiVersion": "v1",
        "kind": "Secret",
        "metadata": {
            "name": "operator-oauth",
            "namespace": "tailscale",
            "annotations": {"argocd.argoproj.io/sync-wave": "-1"},
        },
        "type": "Opaque",
        "stringData": {"client_id": client_id, "client_secret": client_secret},
    }
    encrypted = subprocess.run(
        ["sops", "--encrypt", "--input-type", "json", "--output-type", "yaml",
         "--filename-override", "tailscale/secrets.yaml", "/dev/stdin"],
        input=json.dumps(secret), text=True, capture_output=True,
        cwd=directory.parent,
    )
    if encrypted.returncode:
        raise SystemExit("SOPS encryption failed. No files written; check SOPS installation and .sops.yaml.")
    with target.open("x") as output:
        output.write(encrypted.stdout)
    kustomization = directory / "kustomization.yaml"
    content = kustomization.read_text()
    if "\ngenerators:\n" not in content:
        kustomization.write_text(content + "\ngenerators:\n  - secrets-generator.yaml\n")
    print("Encrypted credentials saved and KSOPS enabled. Follow README.md to activate the app.")


if __name__ == "__main__":
    main()
