#!/usr/bin/env bash
# Turn agentrouter-cli into a standalone public GitHub repo.
# Usage:
#   gh auth login -h github.com   # fix auth first (current token is invalid)
#   bash scripts/make-public.sh [repo-name]
set -euo pipefail
SRC="$(cd "$(dirname "$0")/.." && pwd)"
NAME="${1:-agentrouter-cli}"
TMP="/tmp/opencode/${NAME}-public"

rm -rf "$TMP"
mkdir -p "$TMP"
cp -a "$SRC"/pyproject.toml "$SRC"/README.md "$SRC"/LICENSE "$TMP"/
cp -a "$SRC"/src "$TMP"/
cp -a "$SRC"/tests "$TMP"/
cp -a "$SRC"/scripts "$TMP"/
if [ -f "$SRC/.gitignore" ]; then cp -a "$SRC/.gitignore" "$TMP"/; fi

cd "$TMP"
if [ ! -d .git ]; then git init -b main; fi
git add -A
git commit -s -m "feat: agentrouter-cli agentic CLI for AgentRouter" || true
gh repo create "$NAME" --public --source=. --description="Agentic CLI only for AgentRouter - chat, models, autonomous agent with tools" --push
echo "Public repo created and pushed."
