#!/usr/bin/env bash
# Installs dependencies and Python 3 venv
# Usage:
#     ./setup.sh

create_venv() {
    local venv=$1
    if [ ! -d "$venv" ]; then
        mkdir -p $(dirname "$venv")
        python3 -m venv "$venv" --without-pip
        activate_venv
        curl https://bootstrap.pypa.io/get-pip.py | python3
    fi
}

source ./utils.sh

if is_command sudo; then SUDO=sudo; fi
if is_command apt-get; then
    $SUDO apt-get install -y python3-pip wpasupplicant
else
    echo "Could not find package manager. Please install: pip3 wpasupplicant"
fi

venv=$(find_venv)

if [ "$1" = "clean" ]; then
    rm -rf "$venv"
fi

create_venv "$venv"
activate_venv "$venv"

pip3 install -r requirements.txt
