#!/usr/bin/env bash

find_virtualenv() {
	VIRTUALENV_ROOT="${VIRTUALENV_ROOT:-${WORKON_HOME:-$HOME/.virtualenvs}/mycroft-wifi-setup}"
}

find_virtualenv

sudo "$VIRTUALENV_ROOT/bin/python3" ./wifisetup/main.py "$@"

