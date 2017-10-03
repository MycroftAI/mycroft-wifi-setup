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

# create pyinstall executable
./build.sh $1


cd ${TOP}
# create debian package
./package_deb.sh $1


get_version
get_arch

# upload to s3
cd ./dist
_run s3cmd -c ${HOME}/.s3cfg.mycroft-artifact-writer sync --acl-public . s3://bootstrap.mycroft.ai/artifacts/apt/daily/$arch/mycroft-wifi-setup/$version/
echo $version > latest
_run s3cmd -c ${HOME}/.s3cfg.mycroft-artifact-writer put --acl-public ./latest s3://bootstrap.mycroft.ai/artifacts/apt/daily/$arch/mycroft-wifi-setup/latest

