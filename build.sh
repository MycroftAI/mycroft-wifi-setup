#!/usr/bin/env bash

set -eE

source ./utils.sh
check_args $@
get_version $@

if [ "$1" = "clean" ]; then
    rm -rf build/ dist/
    exit 0
fi

mkdir -p dist

if [ "$1" = "release" ]; then
    tag=release/v$version
    if ! git tag | grep -q $tag; then
        echo "WARNING: Could not find tag $tag. Continuing..."
        sleep 2
    else
        echo "Checking out tag $tag..."
        git checkout $tag -- wifisetup/
    fi
fi

VIRTUALENV_ROOT=${VIRTUALENV_ROOT:-"$HOME/.virtualenvs/mycroft-wifi-setup"}

# create virtualenv, consistent with virtualenv-wrapper conventions
if [ ! -d "${VIRTUALENV_ROOT}" ]; then
   mkdir -p $(dirname "${VIRTUALENV_ROOT}")
   virtualenv -p python2.7 "${VIRTUALENV_ROOT}"
fi

source $VIRTUALENV_ROOT/bin/activate
pip install pyinstaller
pip install -r requirements.txt

data_args=$(sed '/^ *#/ d' MANIFEST.in | sed -e 's/^\(recursive\-\)\?include \([^ \n]\+\).*$/--add-data="\2:\2"/gm' | sed -e 's/"\([^*]\+\)\(\*[^:]*\):\1\2"/"\1\2:\1"/gm' | tr '\n' ' ')
eval extra_data="${VIRTUALENV_ROOT}/lib/python*/site-packages/pyric/nlhelp/*.help"
for i in $extra_data; do
    data_args="$data_args --add-data=\"$i:pyric/nlhelp/\""
done

eval pyinstaller -y -n mycroft-wifi-setup wifisetup/main.py $data_args --add-data="$extra_data:pyric/nlhelp/"
eval pyinstaller -y -n mycroft-admin-service mycroft_admin_service.py --add-data="dialog/:dialog"

cp -R dist/mycroft-admin-service/* dist/mycroft-wifi-setup
rm -rf dist/mycroft-admin-service

echo "Wrote output executables to dist/mycroft-wifi-setup/"
echo ${version} > build/version

if [ "$1" = "release" ]; then
    git checkout HEAD -- wifisetup/
fi
