#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"

ENV_DIR="./python_env"
TARBALL="./hey-aura-macos-aarch64.tar.gz"

if [ -d "$ENV_DIR" ]; then
  echo "Using portable environment at $ENV_DIR"
  exec "$ENV_DIR/bin/python" app.py
fi

if [ -f "$TARBALL" ]; then
  echo "Found $TARBALL, extracting to $ENV_DIR..."
  mkdir -p "$ENV_DIR"
  tar -xzf "$TARBALL" -C "$ENV_DIR"
  # 修复可搬运环境中的路径（若存在）
  if [ -x "$ENV_DIR/bin/conda-unpack" ]; then
    echo "Running conda-unpack..."
    "$ENV_DIR/bin/conda-unpack" || true
  fi
  echo "Launching from $ENV_DIR"
  exec "$ENV_DIR/bin/python" app.py
fi

echo "Portable env not found; falling back to Conda env 'hey-aura'..."
if command -v conda >/dev/null 2>&1; then
  # shellcheck source=/dev/null
  source "$(conda info --base)/etc/profile.d/conda.sh"
  if conda env list | awk '{print $1}' | grep -qx "hey-aura"; then
    conda activate hey-aura
    exec python app.py
  else
    echo "Conda environment 'hey-aura' not found." >&2
    exit 1
  fi
else
  echo "Conda not available. Provide $TARBALL or install Conda env 'hey-aura'." >&2
  exit 1
fi
