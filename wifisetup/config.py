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
no_redirect_url = "mycroft.ai"
server_url = "http://start.mycroft.ai"
ssid = "MYCROFT"
password = "12345678"
device_name = "mycroft-holmes-i"

websocket = {
    'protocol': 'ws://',
    'host': '172.24.1.1',
    'port': 8181,
    'route': '/core'
}


def generate_url():
    return (websocket['protocol'] + websocket['host'] + ':'
            + str(websocket['port']) + websocket['route'])


websocket['url'] = generate_url()
