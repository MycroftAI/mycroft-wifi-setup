#!/usr/bin/env bash

set -eE

source ./utils.sh

check_args $@

version=$(cat ./build/version)

get_version $@
init_script_name="mycroft-admin-service"
pkg_title="mycroft-wifi-setup"
init_script_location="etc/init.d"

data_folder="mycroft-wifi-setup"
data_place="usr/local/mycroft"
install_bin_dir="usr/local/bin"
bin_to_data="../../../$data_place/$data_folder"

get_arch
depends="dnsmasq"
pkg_name="${pkg_title}-${arch}_${version}-1"
root="build/$pkg_name"
control_file="$root/DEBIAN/control"

mkdir -p "$root/$data_place"
mkdir -p "$root/$install_bin_dir"
mkdir -p "$root/$init_script_location"
mkdir -p "$root/DEBIAN"

cp -R "dist/$data_folder" "$root/$data_place"
cd deb_resources
cp init-script "../$root/$init_script_location/$init_script_name"
cp control "../$control_file"
cp preinst postinst prerm postrm "../$root/DEBIAN"
cd ..

cd "$root/$install_bin_dir"
ln -s "$bin_to_data/mycroft-wifi-setup" mycroft-wifi-setup
ln -s "$bin_to_data/mycroft-admin-service" mycroft-admin-service
cd -

sed -i "s/%%VERSION%%/${version}/g" ${control_file}
sed -i "s/%%ARCH%%/${arch}/g" ${control_file}
sed -i "s/%%DEPENDS%%/${depends}/g" ${control_file}

dpkg-deb --build $root
mv build/$pkg_name.deb dist/
echo "Moved to dist/${pkg_name}.deb"

