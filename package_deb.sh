#!/usr/bin/env sh

set -eE

version="0.1.0"  # Also change in deb_resources/control
init_script_name="mycroft-wifi-setup-client"
pkg_title="mycroft-wifi-setup"
install_dir="usr/local/bin"
init_script_location="etc/init.d"

arch="$(dpkg --print-architecture)"
pkg_name="${pkg_title}-${arch}_${version}-1"
root="build/$pkg_name"
control_file="$root/DEBIAN/control"

mkdir -p "$root/$install_dir"
mkdir -p "$root/$init_script_location"
mkdir -p "$root/DEBIAN"

cp dist/mycroft-wifi-setup-client "$root/$install_dir"
cd deb_resources
cp init-script "../$root/$init_script_location/$init_script_name"
cp control "../$control_file"
cp preinst postinst prerm postrm "../$root/DEBIAN"
cd ..

sed -i "s/%%VERSION%%/$version/g" $control_file
sed -i "s/%%ARCH%%/$arch/g" $control_file

dpkg-deb --build $root
mv build/$pkg_name.deb dist/
echo "Moved to dist/$pkg_name.deb"

