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
import os
import time
import json
from ast import literal_eval
from logging import getLogger

from threading import Thread
from time import sleep

from pyric import pyw
from websocket import WebSocketApp
from wifi import Cell

from wifisetup import config
from wifisetup.access_point import AccessPoint
from wifisetup.util import trigger_event, cli_no_output, cli, wpa
from wifisetup.web_server import WebServer

LOG = getLogger(__name__)


class WifiClient:
    """
    Class to manage entire wifi client

    Usage:
        >>> client = WifiClient()  # Starts client
        >>> client.join()
    """
    def __init__(self, allow_timeout=True):
        self.allow_timeout = allow_timeout
        self.running = False

        self.last_lease_mod = self.get_last_lease_mod()
        self.wiface = pyw.winterfaces()[0]
        self.ap = AccessPoint(self.wiface)
        self.client = WebSocketApp(url=config.websocket['url'], on_message=self.on_message)
        Thread(target=self.client.run_forever).start()
        self.run_thread = Thread(target=self.run, daemon=True)

        self.server = None
        try:
            self.server = WebServer(self.ap.ip, 80)
            self.server.start()
        except RuntimeError:
            self.close()
            raise

        self.run_thread.start()

    def get_last_lease_mod(self):
        """When a new user connects, the lease modification time changes"""
        return os.path.getmtime('/var/lib/misc/dnsmasq.leases')

    def join(self):
        """Waits for wifi setup to complete"""
        try:
            self.run_thread.join()
        except:
            LOG.exception('Error in wifi thread:')
            self.close()

    def notify_server(self, name, data=None):
        """Send a message to javascript"""
        self.client.send(json.dumps({'type': name, 'data': data or {}}))

    def on_message(self, _, message: str):
        """Handle communication from javascript"""
        message = json.loads(message)

        def invalid_message(**_):
            pass

        # Javascript events
        {
            'wifi.cancel': self.cancel,
            'wifi.stop': self.close,
            'wifi.scan': self.scan,
            'wifi.connect': self.connect
        }.get(message['type'], invalid_message)(**message.get('data', {}))

    def run(self):
        """
        Fire up the MYCROFT access point for the user to connect to
        with a phone or computer.
        """
        try:
            self.monitor_connection()
        except:
            LOG.exception('Error in wifi client:')
            self.close()

    def monitor_connection(self):
        trigger_event('ap_up')
        has_connected = False
        num_failures = 0
        start_time = time.time()
        self.running = True

        while self.running:
            # do our monitoring...
            mod_time = self.get_last_lease_mod()
            if self.last_lease_mod != mod_time:
                # Something changed in the dnsmasq lease file -
                # presumably a (re)new lease
                if not has_connected:
                    trigger_event('ap_device_connected')
                has_connected = True
                num_failures = 0
                self.last_lease_mod = mod_time
                start_time = time.time()  # reset start time after connection

            if time.time() - start_time > 60 * 5 and self.allow_timeout:
                # After 5 minutes, shut down the access point (unless the
                # system has never been setup, in which case we stay up
                # indefinitely)
                LOG.info("Auto-shutdown of access point after 5 minutes")
                self.cancel()
                continue

            if has_connected:
                # Flush the ARP entries associated with our access point
                # This will require all network hardware to re-register
                # with the ARP tables if still present.
                if num_failures == 0:
                    cli_no_output('ip', '-s', '-s', 'neigh', 'flush',
                                        self.ap.subnet + '.0/24')

                # now look at the hardware that has responded, if no entry
                # shows up on our access point after 2*5=10 seconds, the user
                # has disconnected
                if not self.is_ARP_filled():
                    num_failures += 1
                    LOG.info('Lost connection: ' + str(num_failures))
                    if num_failures > 5:
                        trigger_event('ap_device_disconnected')
                        has_connected = False
                else:
                    num_failures = 0
            sleep(2)  # wait a bit to prevent thread from hogging CPU

    def is_ARP_filled(self):
        out = cli_no_output('/usr/sbin/arp', '-n')["stdout"]
        if not out:
            return False
        # Parse output, skipping header
        for o in out.split("\n")[1:]:
            if o.startswith(self.ap.subnet):
                if "(incomplete)" in o:
                    # ping the IP to get the ARP table entry reloaded
                    ip_disconnected = o.split(" ")[0]
                    cli_no_output('/bin/ping', '-c', '1', '-W', '1',
                                  ip_disconnected)
                else:
                    return True  # something on subnet is connected!
        return False

    def scan(self):
        trigger_event('ap_scan')
        LOG.info("Scanning wifi connections...")
        networks = {}
        status = self.get_connection_info()

        for cell in Cell.all(self.wiface):
            if "x00" in cell.ssid:
                continue  # ignore hidden networks

            # Fix UTF-8 characters
            ssid = literal_eval("b'" + cell.ssid + "'").decode('utf8')
            quality = self.get_quality(cell.quality)

            # If there are duplicate network IDs (e.g. repeaters) only
            # report the strongest signal
            update = True
            if ssid in networks:
                update = networks[ssid]["quality"] < quality
            if update and ssid:
                networks[ssid] = {
                    'quality': quality,
                    'encrypted': cell.encrypted,
                    'connected': self.is_connected(ssid, status),
                    'demo': False
                }
        LOG.info("Found wifi networks: %s" % networks)
        self.notify_server('wifi.scanned', {'networks': networks})

    @staticmethod
    def get_quality(quality):
        values = quality.split("/")
        return float(values[0]) / float(values[1])

    def connect(self, ssid, password=None):
        LOG.info('Connecting to ' + ssid + '...')
        connected = self.is_connected(ssid)

        if connected:
            LOG.warning("Device is already connected to %s" % ssid)
        else:
            self.disconnect()
            LOG.info("Connecting to: %s" % ssid)
            nid = wpa(self.wiface, 'add_network')
            wpa(self.wiface, 'set_network', nid, 'ssid', '"' + ssid + '"')

            if password:
                psk = '"' + password + '"'
                wpa(self.wiface, 'set_network', nid, 'psk', psk)
            else:
                wpa(self.wiface, 'set_network', nid, 'key_mgmt', 'NONE')

            wpa(self.wiface, 'enable', nid)
            connected = self.get_connected(ssid)
            if connected:
                wpa(self.wiface, 'save_config')

        trigger_event('ap_connection_success' if connected else 'ap_connection_failed')
        self.notify_server('connection.status', {'connected': connected})
        LOG.info("Connection status for %s = %s" % (ssid, connected))

    def disconnect(self):
        """Disconnect from current SSID"""
        status = self.get_connection_info()
        nid = status.get("id")
        if nid:
            ssid = status.get("ssid")
            wpa(self.wiface, 'disable', nid)
            LOG.info("Disconnecting %s id: %s" % (ssid, nid))

    def get_connection_info(self):
        res = cli('wpa_cli', '-i', self.wiface, 'status')
        out = str(res["stdout"])
        if out:
            return dict(o.split("=") for o in out.split("\n")[:-1])
        return {}

    def get_connected(self, ssid, retry=5):
        connected = self.is_connected(ssid)
        while not connected and retry > 0:
            sleep(1)
            retry -= 1
            connected = self.is_connected(ssid)
        return connected

    def is_connected(self, ssid, status=None):
        status = status or self.get_connection_info()
        state = status.get("wpa_state")
        return status.get("ssid") == ssid and state == "COMPLETED"

    def cancel(self):
        trigger_event('ap_cancel')
        self.close()

    def close(self):
        trigger_event('ap_down')
        self.running = False
        LOG.info('Shutting down access point...')
        self.ap.close()
        LOG.info('Sending shutdown signal...')
        if self.server:
            self.server.shutdown()
        LOG.info('Closing websocket...')
        self.client.close()
        LOG.info("Wifi client stopped!")
