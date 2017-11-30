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
import sys
from logging import getLogger
from subprocess import Popen, PIPE

LOG = getLogger(__name__)


def trigger_event(name):
    """Send a message to the caller"""
    print(name, file=sys.stdout, flush=True)


def cli_no_output(*args):
    """ Invoke a command line and return result """
    LOG.info("Command: %s" % list(args))
    proc = Popen(args=args, stdout=PIPE, stderr=PIPE)
    stdout, stderr = proc.communicate()
    return {'code': proc.returncode, 'stdout': stdout.decode(), 'stderr': stderr.decode()}


def cli(*args):
    """ Invoke a command line, then log and return result """
    LOG.info("Command: %s" % list(args))
    proc = Popen(args=args, stdout=PIPE, stderr=PIPE)
    stdout, stderr = proc.communicate()
    result = {'code': proc.returncode, 'stdout': stdout.decode(), 'stderr': stderr.decode()}
    LOG.info("Command result: %s" % result)
    return result


def wpa(*args):
    idx = 0
    result = cli('wpa_cli', '-i', *args)
    out = result["stdout"]
    if 'interface' in out:
        idx = 1
    if result['code'] != 0:
        LOG.error('WPA command failed: ' + result['stdout'] + result['stderr'])
    return str(out.split("\n")[idx])


def sysctrl(*args):
    return cli('systemctl', *args)
