#!/usr/bin/env python3
# Copyright 2017 Mycroft AI, Inc.
#
# This file is part of Mycroft Wifi Setup.
#
# Mycroft Core is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Mycroft Core is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Mycroft Core.  If not, see <http://www.gnu.org/licenses/>.

"""
This module implements a mechanism that allows the wifi connection of
a Linux system to be selected by end users.  This is achieved by:
  * creating a websocket for communication between the pieces of this
    mechanism
  * temporarilly creating a virtual access point
  * directing the end user to connect to that access point with another device
    (phone or tablet or laptop)
  * having them open a captive portal in that device's web browser
  * selecting the desired wifi within that browser
  * configuring this device based on that selection
"""
import sys
sys.path += ['.']  # noqa

import logging
from subprocess import call
from wifisetup.wifi_client import WifiClient
from wifisetup import config

root = logging.getLogger()
root.setLevel(logging.DEBUG)

ch = logging.StreamHandler(sys.stderr)
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
root.addHandler(ch)

LOG = logging.getLogger(__name__)


WPA_SUPPLICANT = '''# p2p_start
ctrl_interface=/var/run/wpa_supplicant
driver_param=p2p_device=1
update_config=1
device_name=''' + config.device_name + '''
device_type=1-0050F204-1
p2p_go_intent=10
p2p_go_ht40=1

network={
    ssid="''' + config.ssid + '''"
    psk="''' + config.password + '''"
    proto=RSN
    key_mgmt=WPA-PSK
    pairwise=CCMP
    auth_alg=OPEN
    mode=3
    disabled=2
}
# p2p_end'''


def run_wifi(allow_timeout='True'):
    client = WifiClient(allow_timeout != 'False')
    client.join()


def reset_wifi():
    """Reset the unit to the factory defaults"""
    LOG.info("Resetting the WPA_SUPPLICANT File")
    call("echo '" + WPA_SUPPLICANT +
         "'> /etc/wpa_supplicant/wpa_supplicant.conf",
         shell=True)


def main():
    options = {
        'wifi.run': run_wifi,
        'wifi.reset': reset_wifi
    }

    def print_usage(*_):
        print('Usage:', sys.argv[0], list(options))
        sys.exit(1)

    action = sys.argv[1] if len(sys.argv) > 1 else 'wifi.run'
    try:
        options.get(action, print_usage)(*sys.argv[2:])
    except (SystemExit, KeyboardInterrupt):
        raise
    except:
        LOG.exception('Exception in ' + action)
        sys.exit(1)


if __name__ == "__main__":
    main()
