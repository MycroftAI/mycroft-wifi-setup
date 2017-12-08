#!/usr/bin/env bash
# Run by Jenkins to automatically build and publish packages
# Usage:
#     ./publish.sh [clean]

s3() {
    echo "s3 $@"
    if [ -z "$dry_run" ] && [ -z "$QUIET" ]; then
        s3cmd -c ${HOME}/.s3cfg.mycroft-artifact-writer $@
    fi
}

get_build_type() {
    if [ "$1" = "dev" ] || [ "$1" = "" ]; then
        echo "dev"
    elif [ "$1" = "release" ]; then
        echo "release"
    else
        echo "Usage: $0 [dev|release]" >&2
		echo "   If not specified, dev is chosen" >&2
		echo "Defaulting to dev" >&2
		echo "dev"
		return 1
	fi
}

generate_version() {
	if [ "$1" = "release" ]; then
		version=$(git describe --tags --abbrev=0 | tr -d 'v')
		echo ${version##*/}
	else
		date +%s
	fi
}

set -Ee
source ./utils.sh

if [ "$1" = "-d" ]; then
	dry_run="true"
	shift
fi

build_type=$(get_build_type $@)
version=$(generate_version $build_type)

if [ "$build_type" = "release" ]; then
    git checkout "release/v$version" -- wifisetup/
fi

if is_command apt-get; then
	sudo apt-get install -y python3-dev libc-bin binutils s3cmd
fi
./setup.sh  # install build requirements
./build.sh $@  # create pyinstall executable
./package_deb.sh $version  # create debian package

# upload to s3
[ "$build_type" = "release" ] && channel="release" || channel="daily"

package=$(cat dist/latest)
echo $version | tee build/latest
echo $channel

arch=$(find_arch)

s3 put --acl-public "dist/$package" "s3://bootstrap.mycroft.ai/artifacts/apt/$channel/$arch/mycroft-wifi-setup/$version/$package"
s3 put --acl-public build/latest "s3://bootstrap.mycroft.ai/artifacts/apt/$channel/$arch/mycroft-wifi-setup/latest"
