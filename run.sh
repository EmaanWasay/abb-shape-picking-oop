#!/bin/bash
# Start the vision program (turns on the Python environment first).
cd "$(dirname "$0")"
source ~/abb_env/bin/activate
python3 main.py
