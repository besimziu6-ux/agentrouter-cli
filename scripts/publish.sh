#!/usr/bin/env bash
# Build, check, and publish agentrouter-cli to PyPI.
#
# Usage:
#   bash scripts/publish.sh --dry-run   # build + twine check only, no upload/tag
#   bash scripts/publish.sh             # build + check + upload + git tag + push
set -euo pipefail
cd "$(dirname "$0")/.."

DRY_RUN=0
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    -h|--help)
      echo "Usage: bash scripts/publish.sh [--dry-run]"
      exit 0
      ;;
    *) echo "Unknown arg: $arg" >&2; exit 2 ;;
  esac
done

PYBIN="$(command -v python3 || command -v python)"
VERSION=$("$PYBIN" -c "import tomllib;print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])" 2>/dev/null || "$PYBIN" -c "import re;print(re.search(r'version\s*=\s*\"([^\"]+)\"', open(\"pyproject.toml\").read()).group(1))")
TAG="v${VERSION}"

if [ "$DRY_RUN" = "0" ]; then
  if ! git diff --quiet || ! git diff --cached --quiet; then
    echo "Refusing to publish with uncommitted changes. Commit first." >&2
    exit 1
  fi
fi

rm -rf dist build
"$PYBIN" -m build
twine check dist/*

if [ "$DRY_RUN" = "1" ]; then
  echo "dry-run OK: built ${TAG}, twine check passed (no upload, no tag)."
  exit 0
fi

twine upload dist/*

if git rev-parse "$TAG" >/dev/null 2>&1; then
  echo "Tag $TAG already exists, skipping tag creation."
else
  git tag -a "$TAG" -m "Release $TAG"
  git push origin "$TAG"
fi
git push origin HEAD
echo "Published $TAG."
