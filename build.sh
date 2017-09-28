#!/usr/bin/env bash

set -eE

rm -rf build/ dist/

[ "$1" = "clean" ] && exit 0

mkdir dist
git clone https://github.com/MycroftAI/mycroft-core build --single-branch --depth 1
cp -r wifisetup build/mycroft/client/
cd build

< ../requirements.txt >> requirements.txt
< ../MANIFEST.in >> mycroft-base-MANIFEST.in

VIRTUALENV_ROOT=${VIRTUALENV_ROOT:-"$HOME/.virtualenvs/mycroft"}
source $VIRTUALENV_ROOT/bin/activate
pip2 install pyinstaller

data_args=$(sed '/^ *#/ d' mycroft-base-MANIFEST.in | sed -e 's/^\(recursive\-\)\?include \([^ \n]\+\).*$/--add-data="\2:\2"/gm' | sed -e 's/"\([^*]\+\)\(\*[^:]*\):\1\2"/"\1\2:\1"/gm' | tr '\n' ' ')
eval extra_data="~/.virtualenvs/mycroft/lib/python2.7/site-packages/pyric/nlhelp/*.help"
for i in $extra_data; do
	data_args="$data_args --add-data=\"$i:pyric/nlhelp/\""
done

eval pyinstaller -y -n mycroft-wifi-setup-client mycroft/client/wifisetup/main.py $data_args --add-data="$extra_data:pyric/nlhelp/" -F

mv dist/mycroft-wifi-setup-client ../dist
echo "Wrote output executable to dist/mycroft-wifi-setup-client"
