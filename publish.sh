#!/usr/bin/env bash

TOP=`pwd`

function _run() {
  if [ "$dry_run" ] || [ "$QUIET" ]; then
    echo "$*"
  else
    eval "$@"
  fi
}

set -Ee

source ./utils.sh



if [ "$1" = "-d" ]; then
	dry_run="true"
	shift
fi

check_args $@

# install build requirements
./build-host-setup_debian.sh

#get_version
get_arch

# create pyinstall executable
./build.sh $1


cd ${TOP}
# create debian package
./package_deb.sh $1

version=$(cat ./build/version)

# upload to s3
cd ./dist
echo ${version}

if [[ $1 == "release" ]]; then
	channel="release"
fi

if [[ $1 == "dev" ]]; then
	channel="daily"
fi

echo ${channel}
_run s3cmd -c ${HOME}/.s3cfg.mycroft-artifact-writer sync --acl-public *.deb s3://bootstrap.mycroft.ai/artifacts/apt/${channel}/$arch/mycroft-wifi-setup/$version/
echo $version > latest
_run s3cmd -c ${HOME}/.s3cfg.mycroft-artifact-writer put --acl-public ./latest s3://bootstrap.mycroft.ai/artifacts/apt/${channel}/$arch/mycroft-wifi-setup/latest

