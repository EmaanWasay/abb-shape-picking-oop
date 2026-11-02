#!/bin/bash
# One-time setup on a fresh Raspberry Pi (takes about 15 minutes).
# Run from the project folder:   bash setup_pi.sh
set -e

python3 -m venv --system-site-packages ~/abb_env
source ~/abb_env/bin/activate

# Small CPU-only PyTorch first (the default one is several GB and fills the SD card)
pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu
pip install --no-cache-dir ultralytics flask pypylon ncnn

echo
echo "Setup done. Start the program with:   bash run.sh"
