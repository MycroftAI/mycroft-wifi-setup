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
import sys
import encodings.idna  # Needed to make pyinstaller install the encoding

from http.server import SimpleHTTPRequestHandler
from logging import getLogger
from os.path import abspath, dirname
from socketserver import TCPServer
from threading import Thread
from time import sleep

from wifisetup import config

LOG = getLogger(__name__)


class CaptiveHTTPRequestHandler(SimpleHTTPRequestHandler):
    """ Serve a single website, 303 redirecting all other requests to it """

    def do_HEAD(self):
        LOG.info("do_HEAD being called....")
        if not self.redirect():
            SimpleHTTPRequestHandler.do_HEAD(self)

    def do_GET(self):
        LOG.info("do_GET being called....")
        if not self.redirect():
            SimpleHTTPRequestHandler.do_GET(self)

    def redirect(self):
        try:
            LOG.info("***********************")
            LOG.info("**   HTTP Request   ***")
            LOG.info("***********************")
            LOG.info("Requesting: " + self.path)
            LOG.info("REMOTE_ADDR:" + self.client_address[0])
            LOG.info("SERVER_NAME:" + self.server.server_address[0])
            LOG.info("SERVER_PORT:" + str(self.server.server_address[1]))
            LOG.info("SERVER_PROTOCOL:" + self.request_version)
            LOG.info("HEADERS...")
            LOG.info(self.headers)
            LOG.info("***********************")

            # path = self.translate_path(self.path)
            if config.no_redirect_url in self.headers['host']:
                LOG.info("No redirect")
                return False
            else:
                LOG.info("303 redirect to " + config.server_url)
                self.send_response(303)
                self.send_header("Location", config.server_url)
                self.end_headers()
                return True
        except:
            LOG.exception("Exception:")
            return False


class WebServer(Thread):
    """ Web server for devices connected to the temporary access point """

    def __init__(self, host, port):
        super(WebServer, self).__init__()
        LOG.info("Creating TCPServer...")
        root = getattr(sys, '_MEIPASS', abspath(dirname(__file__) + '/..'))

        self.daemon = True
        self.dir = os.path.join(root, 'wifisetup', 'web')
        try:
            self.server = TCPServer((host, port), CaptiveHTTPRequestHandler)
        except OSError:
            raise RuntimeError('Could not create webserver! Port already in use.')

    def shutdown(self):
        Thread(target=self.server.shutdown, daemon=True).start()
        self.server.server_close()
        self.join(0.5)

    def run(self):
        LOG.info("Starting Web Server at %s:%s" % self.server.server_address)
        LOG.info("Serving from: %s" % self.dir)
        os.chdir(self.dir)
        self.server.serve_forever()
        LOG.info("Web Server stopped!")
