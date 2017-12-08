#!/usr/bin/env bash
# Runs wifi setup on its own, locally
# Usage:
#     ./run.sh [wifi.run|wifi.reset]

source ./utils.sh
venv=$(find_venv)
sudo "$venv/bin/python3" ./wifisetup/main.py "$@"
