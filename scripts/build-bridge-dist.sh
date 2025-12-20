#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BRIDGE_DIR="${ROOT_DIR}/bridge"
OUT_DIR="${ROOT_DIR}/dist/bridge"

VERSION="${VERSION:-}"
ARCHS="${ARCHS:-amd64 arm64}"
OSES="${OSES:-linux darwin windows}"

usage() {
  cat <<'EOF'
Build AI Bridge (Go) for Linux/macOS/Windows.

Usage:
  scripts/build-bridge-dist.sh [--version vX.Y.Z] [--out dist/bridge]

Env:
  VERSION=<string>           Optional version label (default: git describe / sha)
  OSES="linux darwin windows"
  ARCHS="amd64 arm64"

Outputs:
  dist/bridge/bridge_<version>_<os>_<arch>.{tar.gz|zip}
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --version)
      VERSION="${2:-}"
      shift 2
      ;;
    --out)
      OUT_DIR="$(cd "$(dirname "${2:-}")" && pwd)/$(basename "${2:-}")"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown arg: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ -z "${VERSION}" ]]; then
  if command -v git >/dev/null 2>&1 && git -C "${ROOT_DIR}" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    VERSION="$(git -C "${ROOT_DIR}" describe --tags --always --dirty 2>/dev/null || true)"
  fi
fi
if [[ -z "${VERSION}" ]]; then
  VERSION="$(date +%Y%m%d%H%M%S)"
fi

mkdir -p "${OUT_DIR}"

if ! command -v go >/dev/null 2>&1; then
  echo "go not found in PATH" >&2
  exit 1
fi

echo "Building bridge CLI"
echo "  version: ${VERSION}"
echo "  out:     ${OUT_DIR}"

for goos in ${OSES}; do
  for goarch in ${ARCHS}; do
    name="bridge_${VERSION}_${goos}_${goarch}"
    work="$(mktemp -d)"
    bin="${work}/bridge"
    if [[ "${goos}" == "windows" ]]; then
      bin="${work}/bridge.exe"
    fi

    echo "  -> ${goos}/${goarch}"
    (
      cd "${BRIDGE_DIR}"
      CGO_ENABLED=0 GOOS="${goos}" GOARCH="${goarch}" \
        go build -trimpath -ldflags "-s -w" -o "${bin}" ./cmd/bridge
    )

    cp "${ROOT_DIR}/LICENSE" "${work}/LICENSE"
    if [[ -f "${BRIDGE_DIR}/README.md" ]]; then
      cp "${BRIDGE_DIR}/README.md" "${work}/README.md"
    fi

    if [[ "${goos}" == "windows" ]]; then
      if command -v zip >/dev/null 2>&1; then
        (cd "${work}" && zip -q -r "${OUT_DIR}/${name}.zip" .)
      else
        python3 - <<PY
import os
import zipfile

work = ${work@Q}
out = ${OUT_DIR@Q} + "/" + ${name@Q} + ".zip"

with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as z:
    for root, dirs, files in os.walk(work):
        for f in files:
            path = os.path.join(root, f)
            rel = os.path.relpath(path, work)
            z.write(path, rel)
print(out)
PY
      fi
    else
      (cd "${work}" && tar -czf "${OUT_DIR}/${name}.tar.gz" .)
    fi
    rm -rf "${work}"
  done
done

echo "Done. Artifacts:"
ls -1 "${OUT_DIR}"
