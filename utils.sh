#!/usr/bin/env bash
# Utilities used by multiple scripts
# Usage:
#     source ./utils.sh

find_arch() {
	dpkg --print-architecture
}

is_command() {
    hash $1 2>/dev/null
}

find_venv() {
	echo ${VIRTUALENV_ROOT:-${WORKON_HOME:-$HOME/.virtualenvs}/mycroft-wifi-setup}
}

activate_venv() {
    echo "Activating $1..."
    source "$1/bin/activate"
}
