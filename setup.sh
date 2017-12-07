#!/usr/bin/env bash

found_exe() {
    hash $1 2>/dev/null
}

find_virtualenv() {
	VIRTUALENV_ROOT="${VIRTUALENV_ROOT:-${WORKON_HOME:-$HOME/.virtualenvs}/mycroft-wifi-setup}"
}

activate_virtualenv() {
    source "$VIRTUALENV_ROOT/bin/activate"
}

create_virtualenv() {
    if [ ! -d "$VIRTUALENV_ROOT" ]; then
        mkdir -p $(dirname "$VIRTUALENV_ROOT")
        python3 -m venv "$VIRTUALENV_ROOT" --without-pip
        activate_virtualenv
        curl https://bootstrap.pypa.io/get-pip.py | python3
    fi
}

remove_virtualenv() {
    if [ -d "$VIRTUALENV_ROOT" ]; then
        rm -rf $VIRTUALENV_ROOT
    fi
}

if found_exe sudo; then SUDO=sudo; fi
if found_exe apt-get; then
    $SUDO apt-get install -y python3-pip wpasupplicant
else
    echo "Could not find package manager. Please install: pip3"
fi


find_virtualenv

if [ "$1" = "clean" ]; then
    remove_virtualenv
fi

create_virtualenv
activate_virtualenv

pip3 install -r requirements.txt
