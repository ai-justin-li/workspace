#!/usr/bin/env bash
# Idempotent dependency setup for the SoCo Spa reservation tool.
set -euo pipefail

cd "$(dirname "$0")/.."

# The base image ships Python 3.12 but not the venv/ensurepip module, so add it
# when it is missing. apt-get is idempotent, so this is safe to run repeatedly.
if ! python3 -c "import ensurepip" >/dev/null 2>&1; then
  sudo apt-get update -qq
  sudo apt-get install -y -qq python3.12-venv
fi

# Create the virtual environment the app scripts expect (./.venv).
if [ ! -x ".venv/bin/python" ]; then
  python3 -m venv .venv
fi

./.venv/bin/python -m pip install --upgrade pip
./.venv/bin/pip install -r requirements.txt

echo "Install complete. Activate with: source .venv/bin/activate"
