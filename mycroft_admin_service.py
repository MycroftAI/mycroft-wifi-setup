#!/usr/bin/env python3
"""Perform system administration tasks that require root access.

The Mycroft admin service is built-in to Mycroft device images.  It is
installed on devices as a service that starts at boot time.  This service
communicates with the message bus in mycroft-core to perform tasks like wifi
setup, clock setting and rebooting.

Log messages emitted by this service can be found in
    /var/log/mycroft_admin_service.log
"""
import sys

from signal import SIGINT

sys.path += ['.']  # noqa

import json
import random
import traceback
from logging import Formatter, getLogger, DEBUG, StreamHandler
from os.path import join, dirname, realpath, isfile
from subprocess import call, Popen, PIPE, check_output
from threading import Thread, Timer, Event
from time import sleep

from websocket import WebSocketApp

LOG = getLogger('mycroft_admin_service')


def get_resource(name):
    data_dir = dirname(realpath(sys.argv[0]))
    data_dir = getattr(sys, '_MEIPASS', data_dir)
    return join(data_dir, name)


lang = 'en-us'
exe_file = get_resource('mycroft-wifi-setup')
exe_file = exe_file if isfile(exe_file) else get_resource('wifisetup/main.py')

mock = len(sys.argv) > 1 and sys.argv[1] == 'mock'
if mock:
    exe_file = 'wifisetup/mock_main.py'


def get_dialog(name):
    """Get the dialog to be spoken by the device.

    Dialog files often contain more than one entry that say basically the same
    thing.  Read them all and pick one at random.  After all, variety is the
    spice of life!
    """
    dialog_path = join('dialog', lang, name + '.dialog')
    with open(get_resource(dialog_path)) as dialog_file:
        dialog_records = [
            rec.strip() for rec in dialog_file.readlines() if rec.strip()
        ]
        return random.choice(dialog_records)


def speak_dialog(client, dialog_name):
    """Instruct the device to speak a dialog by issuing a "speak" event."""
    dialog = get_dialog(dialog_name)
    message = dict(type='speak', data=dict(utterance=dialog))
    client.send(json.dumps(message))


def show_text(text):
    try:
        if isfile('/dev/ttyAMA0'):
            command = 'echo "mouth.text=\'{}\'" > /dev/ttyAMA0 &>/dev/null'
            call(command.format(text), shell=True)
    except OSError:
        pass


def run_wifi_setup(client, data):
    dialog_events = {
        'device.not.connected',
        'device.connected',
        'ap_device_connected',
        'ap_device_disconnected',
        'ap_cancel',
        'ap_error'
    }
    visual_events = {
        'device.not.connected': '12345678',
        'device.connected': 'start.mycroft.ai',
    }
    event_transitions = {
        'ap_up': 'device.not.connected',
        'ap_device_connected': 'device.connected',
        'ap_device_disconnected': 'device.not.connected',
        'ap_connection_success': 'exit',
        'ap_down': 'exit',
        'ap_error': 'exit'
    }
    all_events = set(list(dialog_events) +
                     list(visual_events) +
                     list(event_transitions))

    global lang
    lang = data.get('lang', lang)
    allow_timeout = data.get('allow_timeout', True)
    p = Popen([exe_file, 'wifi.run', str(allow_timeout)],
              stdout=PIPE, stderr=sys.stderr.buffer)

    def notify(event):
        """Continuously show and speak a message to the user on an event"""
        LOG.debug('Notifying event: ' + event)
        if event == 'exit':
            notify.quit_event.set()
            show_text('')
            return
        if event not in all_events:
            return
        if event in event_transitions:
            client.send(json.dumps({'type': 'system.wifi.{}'.format(event)}))

        next_event = event_transitions.get(event, event)
        delay = 0.1 if next_event != event else 45

        notify.quit_event.clear()
        notify.timer.cancel()
        notify.timer = Timer(delay, notify, [next_event])
        notify.timer.start()

        if event in dialog_events:
            speak_dialog(client, event)
        if event in visual_events:
            show_text(visual_events[event])

    def parse_output():
        for line in p.stdout:
            event = line.decode().strip()
            notify(event)
        if not notify.quit_event.is_set():
            notify('exit')

    Thread(target=parse_output, daemon=True).start()

    notify.quit_event = Event()
    notify.quit_event.set()
    notify.timer = Timer(10, speak_dialog, [client, 'ap_error'])
    notify.timer.start()
    notify.timer.join()

    notify.quit_event.wait()
    p.send_signal(SIGINT)
    sleep(10)  # Give the wifi setup process time to shutdown of it's own
    p.terminate()  # In case anything has gone bonkers, terminate the process
    LOG.debug('Wifi setup complete.')


def ntp_sync(client, data):
    # Force the system clock to synchronize with internet time servers
    call('service ntp stop', shell=True)
    call('ntpd -gq', shell=True)
    call('service ntp start', shell=True)
    client.send(json.dumps({'type': 'system.ntp.sync.complete'}))


def system_shutdown(*_):
    # Turn the system completely off (with no option to inhibit it)
    call('systemctl poweroff -i', shell=True)


def system_reboot(*_):
    # Shut down and restart the system
    call('systemctl reboot -i', shell=True)


def update_only_mycroft():
    call(['apt-get', 'update', '-o', 'Dir::Etc::sourcelist=sources.list.d/repo.mycroft.ai.list',
          '-o', 'Dir::Etc::sourceparts=-', '-o', 'APT::Get::List-Cleanup=0'])


def get_core_version():
    lines = check_output(['dpkg', '--list']).decode().split('\n')
    try:
        line = next(i for i in lines if 'mycroft-core' in i)
        status, name, version, arch, desc = line.split()
        return version
    except StopIteration:
        return ''


def get_mycroft_package(data):
    # Force a system package update.  Limited to "mycroft-" packages.
    # Support installing/updating "mycroft-XXX" meta packages,
    # but limit to know packages to prevent abuse.
    platform = (data or {}).get('platform')
    if platform == "mark-1":
        return "mycroft-mark-1"
    elif platform == "picroft":
        return "mycroft-picroft"
    return "mycroft-core"


APT_PLATFORMS = ['mycroft_mark_1']

def system_update(client, data):
    if data.get('platform', 'unknown') in APT_PLATFORMS:
        client.send(json.dumps({'type': 'system.update.processing'}))
        update_only_mycroft()
        version_before = get_core_version()
        call(['apt-get', 'install', get_mycroft_package(data), '-y'])
        version_after = get_core_version()
        has_updated = version_before != version_after
        if has_updated:
            call(['service', 'mycroft-skills', 'stop'])
            call(['mycroft-msm', 'default'])
            call(['service', 'mycroft-skills', 'start'])
        client.send(json.dumps({
            'type': 'system.update.complete',
            'data': {'has_updated': has_updated}
        }))


def ssh_enable(*_):
    # Permanently allow SSH access
    call('systemctl enable ssh.service', shell=True)
    call('systemctl start ssh.service', shell=True)


def ssh_disable(*_):
    # Permanently block SSH access from the outside
    call('systemctl stop ssh.service', shell=True)
    call('systemctl disable ssh.service', shell=True)


def reset_system(*_):
    # Remove all skills except Pairing (which is needed after wipe)
    call("""mkdir -p /opt/mycroft/safety &&
    mv /opt/mycroft/skills/mycroft-pairing.mycroftai /opt/mycroft/safety &&
    rm -rf /opt/mycroft/skills/* &&
    mv /opt/mycroft/safety/mycroft-pairing.mycroftai /opt/mycroft/skills &&
    rm -rf /opt/mycroft/safety &&
    rm -f /opt/mycroft/skills/mycroft-pairing.mycroftai/settings.json
    """, shell=True)

    # Zap the MSM info and cache files
    call("rm -rf /opt/mycroft/.skills-repo", shell=True)
    call("rm -f /opt/mycroft/skills/.msm", shell=True)

    # Zap user data
    call("rm -rf /home/mycroft/.mycroft", shell=True)

    # Reset network settings
    call([exe_file, 'wifi.reset'])


# TODO: Retire the mycroft.XXX events when core versions using them are retired
event_handlers = {
    'system.wifi.setup': run_wifi_setup,
    'mycroft.wifi.start': run_wifi_setup,
    'system.wifi.reset': reset_system,
    'mycroft.wifi.reset': reset_system,
    'system.ssh.enable': ssh_enable,
    'mycroft.enable.ssh': ssh_enable,
    'system.ssh.disable': ssh_disable,
    'mycroft.disable.ssh': ssh_disable,
    'system.ntp.sync': ntp_sync,
    'system.reboot': system_reboot,
    'system.shutdown': system_shutdown,
    'system.update': system_update,
}


def on_message(client, message):
    """Execute event handler if one is defined for the event type."""
    LOG.debug('Event message: ' + message)
    message = json.loads(message)
    event_type = message['type']
    event_handler = event_handlers.get(event_type)
    if event_handler is not None:
        event_handler(client, message['data'])


def main():
    # Connect to the default websocket used by mycroft-core
    url = 'ws://127.0.0.1:8181/core'
    LOG.info('Starting message bus client on: ' + url)
    client = WebSocketApp(url=url, on_message=on_message)
    if mock:
        Thread(target=run_wifi_setup, args=[client, {}], daemon=True).start()
    client.run_forever()
    LOG.info('Message bus client stopped.')


def configure_logger():
    """Configure logger to write messages to console.

    The admin service writes all STDOUT to /var/log/mycroft_admin_service.log.
    So writing logs to STDOUT will result in log messages being written there.
    """
    LOG.setLevel(DEBUG)
    log_msg_formatter = Formatter(
        '{asctime} | {levelname:8} | {process:5} | {name} | {message}',
        style='{'
    )
    log_handler = StreamHandler()
    log_handler.setLevel(DEBUG)
    log_handler.setFormatter(log_msg_formatter)
    LOG.addHandler(log_handler)


if __name__ == '__main__':
    configure_logger()
    # Loop until a successful connection to the websocket.
    success = False
    while not success:
        try:
            main()
        except KeyboardInterrupt:
            raise
        except:
            traceback.print_exc()
        else:
            success = True
