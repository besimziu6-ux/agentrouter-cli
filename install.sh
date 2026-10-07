#!/usr/bin/env bash
set -euo pipefail

INSTALLER_VERSION="0.1.0"
REPO="${AGENTROUTER_REPO:-https://github.com/besimziu6-ux/agentrouter-cli}"
VERSION="${AGENTROUTER_VERSION:-main}"
VENV_DIR="${AGENTROUTER_VENV:-$HOME/.local/share/agentrouter/venv}"
BIN_DIR="$HOME/.local/bin"
LINK="$BIN_DIR/agentrouter"

usage() {
  cat <<'EOF'
agentrouter installer

Usage:
  install.sh [OPTION]

Options:
  --help        Show this help and exit
  --version     Print installer version and exit
  --uninstall   Remove venv and symlink and exit

Env:
  AGENTROUTER_REPO      Git repo URL (default: https://github.com/besimziu6-ux/agentrouter-cli)
  AGENTROUTER_VERSION   Branch, tag, or commit (default: main)
  AGENTROUTER_VENV      Venv path (default: ~/.local/share/agentrouter/venv)

Examples:
  curl -fsSL https://raw.githubusercontent.com/besimziu6-ux/agentrouter-cli/main/install.sh | bash
  AGENTROUTER_VERSION=v0.1.0 bash install.sh
  bash install.sh --uninstall
EOF
}

pkg_spec() {
  local repo="$1"
  local version="$2"
  local base="$repo"
  case "$base" in
    *.git) ;;
    *) base="${base}.git" ;;
  esac
  if [ -n "$version" ]; then
    printf 'git+%s@%s' "$base" "$version"
  else
    printf 'git+%s' "$base"
  fi
}

do_uninstall() {
  rm -f "$LINK"
  rm -rf "$VENV_DIR"
  rmdir --ignore-fail-on-non-empty "$HOME/.local/share/agentrouter" 2>/dev/null || true
  echo "Uninstalled agentrouter ($LINK and $VENV_DIR removed)."
}

do_install() {
  if ! command -v python3 >/dev/null 2>&1; then
    echo "error: python3 not found. Install Python 3.9+ first." >&2
    exit 1
  fi

  mkdir -p "$BIN_DIR"
  mkdir -p "$(dirname "$VENV_DIR")"

  if [ ! -x "$VENV_DIR/bin/python" ]; then
    python3 -m venv "$VENV_DIR"
  fi

  "$VENV_DIR/bin/pip" install --upgrade pip
  "$VENV_DIR/bin/pip" install "$(pkg_spec "$REPO" "$VERSION")"

  ln -sf "$VENV_DIR/bin/agentrouter" "$LINK"
  echo "Installed agentrouter -> $LINK"

  case ":$PATH:" in
    *":$BIN_DIR:"*) ;;
    *)
      echo ""
      echo "$BIN_DIR is not on your PATH. Add it with:"
      echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
      ;;
  esac

  echo "Run: agentrouter --help"
}

arg="${1:-}"
case "$arg" in
  -h|--help) usage; exit 0 ;;
  --version) echo "install.sh $INSTALLER_VERSION"; exit 0 ;;
  --uninstall) do_uninstall; exit 0 ;;
  "") do_install ;;
  *)
    echo "error: unknown option '$arg'. Use --help." >&2
    exit 1
    ;;
esac
