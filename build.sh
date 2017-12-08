#!/usr/bin/env bash
# Builds a binary executable in dist/ using pyinstaller
# Usage:
# ./build.sh [clean]

set -eE

if [ "$1" = "clean" ]; then
    rm -rf build/ dist/
    exit 0
fi

source ./utils.sh

venv=$(find_venv)
activate_venv "$venv"

pip install pyinstaller
pip install -r requirements.txt

pyric_init=$(python3 -c "import pyric; print(pyric.__file__)")
pyric_help=${pyric_init//__init__.py/nlhelp}

pyinstaller -ysn mycroft-wifi-setup wifisetup/main.py --add-data=$pyric_help/:pyric/nlhelp --add-data=wifisetup/web/:wifisetup/web
pyinstaller -ysn mycroft-admin-service mycroft_admin_service.py --add-data=dialog/:dialog

cp -R dist/mycroft-admin-service/* dist/mycroft-wifi-setup
rm -rf dist/mycroft-admin-service

echo "Wrote output executables to dist/mycroft-wifi-setup/"

if [ "$1" = "release" ]; then
    git checkout HEAD -- wifisetup/
fi
