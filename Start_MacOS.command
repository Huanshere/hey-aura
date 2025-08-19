#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"

# Check and fix directory permissions
echo "Checking directory permissions..."
if [ ! -w "." ]; then
  echo "Directory is not writable, attempting to fix permissions..."
  chmod 755 . || {
    echo "Warning: Could not fix directory permissions. You may need to run:"
    echo "  chmod 755 $(pwd)"
    echo "  or contact your system administrator."
  }
fi

# Ensure recordings directory exists and is writable
if [ ! -d "recordings" ]; then
  echo "Creating recordings directory..."
  mkdir -p recordings || {
    echo "Warning: Could not create recordings directory."
  }
fi

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
