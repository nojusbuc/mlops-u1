#!/usr/bin/env bash
# Trivy CRITICAL vartas -> multi-arch build ir push į GHCR su tag'u sha-<commit>.
# Reikia: `gh auth refresh -h github.com -s write:packages,read:packages`.
set -euo pipefail
OWNER=$(gh api user --jq '.login | ascii_downcase')
SHA=$(git rev-parse --short=8 HEAD)
LOCAL=mlops-u1/train:sha-$SHA
REMOTE=ghcr.io/$OWNER/mlops-u1/train:sha-$SHA

if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
  echo "Uncommitted changes: the image tag would not match its code" >&2; exit 1
fi
docker image inspect "$LOCAL" >/dev/null
trivy image -q --scanners vuln --severity CRITICAL --exit-code 1 "$LOCAL"

gh auth token | docker login ghcr.io -u "$OWNER" --password-stdin
# amd64 + arm64: vaizdas veikia ir Intel/AMD kompiuteriuose, ir Apple Silicon
docker buildx build --platform linux/amd64,linux/arm64 -f docker/Dockerfile.train \
  --build-arg GIT_COMMIT="$SHA" -t "$REMOTE" --push .
docker buildx imagetools inspect "$REMOTE" | head -3
echo "Make the package public once: GitHub -> Packages -> mlops-u1/train -> Package settings -> Public"
