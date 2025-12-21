#!/usr/bin/env bash
set -euo pipefail

REPO_DEFAULT="MarshallEriksen-Neura/AI-Higress-Gateway"
REF_DEFAULT="master"
DIST_DIR_DEFAULT="dist/bridge"
DEV_PREFIX_DEFAULT="bridge_dev"

usage() {
  cat <<'EOF'
Install AI Bridge CLI (bridge) from this repository.

Usage:
  curl -fsSL https://raw.githubusercontent.com/<owner>/<repo>/<ref>/scripts/install-bridge.sh | bash
  (Windows PowerShell) irm https://raw.githubusercontent.com/<owner>/<repo>/<ref>/scripts/install-bridge.ps1 | iex

Options (env vars):
  REPO=<owner/repo>          Default: MarshallEriksen-Neura/AI-Higress-Gateway
  REF=<git ref>              Default: master (used for dev artifacts in dist/)
  VERSION=<bridge-vX.Y.Z>    If set, download from GitHub Release assets
  INSTALL_DIR=<dir>          Default: ~/.local/bin

Notes:
  - Dev artifacts come from: dist/bridge/bridge_dev_<os>_<arch>.{tar.gz|zip}
  - Release artifacts come from: bridge_<VERSION>_<os>_<arch>.{tar.gz|zip}
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

REPO="${REPO:-$REPO_DEFAULT}"
REF="${REF:-$REF_DEFAULT}"
DIST_DIR="${DIST_DIR:-$DIST_DIR_DEFAULT}"
DEV_PREFIX="${DEV_PREFIX:-$DEV_PREFIX_DEFAULT}"
VERSION="${VERSION:-}"

INSTALL_DIR="${INSTALL_DIR:-${HOME}/.local/bin}"

uname_s="$(uname -s | tr '[:upper:]' '[:lower:]')"
case "${uname_s}" in
  linux*) os="linux" ;;
  darwin*) os="darwin" ;;
  msys*|mingw*|cygwin*) os="windows" ;;
  *)
    echo "Unsupported OS: ${uname_s}" >&2
    exit 1
    ;;
esac

uname_m="$(uname -m | tr '[:upper:]' '[:lower:]')"
case "${uname_m}" in
  x86_64|amd64) arch="amd64" ;;
  aarch64|arm64) arch="arm64" ;;
  *)
    echo "Unsupported arch: ${uname_m}" >&2
    exit 1
    ;;
esac

ext="tar.gz"
if [[ "${os}" == "windows" ]]; then
  ext="zip"
fi

if [[ -n "${VERSION}" ]]; then
  asset="bridge_${VERSION}_${os}_${arch}.${ext}"
  url="https://github.com/${REPO}/releases/download/${VERSION}/${asset}"
else
  asset="${DEV_PREFIX}_${os}_${arch}.${ext}"
  url="https://raw.githubusercontent.com/${REPO}/${REF}/${DIST_DIR}/${asset}"
fi

echo "Installing bridge"
echo "  repo: ${REPO}"
if [[ -n "${VERSION}" ]]; then
  echo "  version: ${VERSION}"
else
  echo "  ref: ${REF}"
fi
echo "  asset: ${asset}"
echo "  url: ${url}"
echo "  install_dir: ${INSTALL_DIR}"

if ! command -v curl >/dev/null 2>&1; then
  echo "curl not found in PATH" >&2
  exit 1
fi

work="$(mktemp -d)"
trap 'rm -rf "${work}"' EXIT

archive="${work}/${asset}"
curl -fsSL "${url}" -o "${archive}"

extract_dir="${work}/extract"
mkdir -p "${extract_dir}"

if [[ "${ext}" == "tar.gz" ]]; then
  tar -xzf "${archive}" -C "${extract_dir}"
else
  if command -v unzip >/dev/null 2>&1; then
    unzip -q "${archive}" -d "${extract_dir}"
  else
    python3 - <<PY
import zipfile
from pathlib import Path

archive = Path(${archive@Q})
out = Path(${extract_dir@Q})
with zipfile.ZipFile(archive, "r") as z:
    z.extractall(out)
PY
  fi
fi

bin_src="${extract_dir}/bridge"
if [[ "${os}" == "windows" ]]; then
  bin_src="${extract_dir}/bridge.exe"
fi

if [[ ! -f "${bin_src}" ]]; then
  echo "bridge binary not found after extracting: ${bin_src}" >&2
  exit 1
fi

mkdir -p "${INSTALL_DIR}"
bin_dst="${INSTALL_DIR}/bridge"
if [[ "${os}" == "windows" ]]; then
  bin_dst="${INSTALL_DIR}/bridge.exe"
fi

install -m 0755 "${bin_src}" "${bin_dst}"

echo "Installed: ${bin_dst}"
echo "Tip: add to PATH if needed (e.g. export PATH=\"${INSTALL_DIR}:\$PATH\")"
