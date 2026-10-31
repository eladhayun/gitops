#!/usr/bin/env bash
set -euo pipefail
dest="${1:?tool destination required}"
mkdir -p "$dest"
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
cd "$tmp"
curl -fsSLo kustomize.tgz https://github.com/kubernetes-sigs/kustomize/releases/download/kustomize/v5.8.3/kustomize_v5.8.3_linux_amd64.tar.gz
echo 'cb9e31198d3f63b44848bd0afc4c8efc56e6cfef9c93a4a39a211940e6decd61  kustomize.tgz' | sha256sum -c -
curl -fsSLo kubeconform.tgz https://github.com/yannh/kubeconform/releases/download/v0.8.0/kubeconform-linux-amd64.tar.gz
echo '9bc2bffbf71f261128533edaf912153948b7ff238f9a531ae6d34466ec287883  kubeconform.tgz' | sha256sum -c -
curl -fsSLo helm.tgz https://get.helm.sh/helm-v4.3.1-linux-amd64.tar.gz
echo '0403a88ae20913d11b10a2467b50087721fea7581736da6b9d3992f5357fe54b  helm.tgz' | sha256sum -c -
tar -xzf kustomize.tgz -C "$dest" kustomize
tar -xzf kubeconform.tgz -C "$dest" kubeconform
tar -xzf helm.tgz linux-amd64/helm
cp linux-amd64/helm "$dest/helm"
