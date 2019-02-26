#!/usr/bin/env python3
import sys

from signal import SIGINT

sys.path += ['.']  # noqa

import json
import traceback
import random
from os.path import join, dirname, realpath, isfile
from subprocess import call, Popen, PIPE, check_output
from threading import Thread, Timer, Event
from time import sleep
from websocket import WebSocketApp


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
    with open(get_resource(join('dialog', lang, name + '.dialog'))) as f:
        return random.choice(list(filter(bool, f.read().split('\n'))))


def speak_dialog(client, dialog_name):
    text = get_dialog(dialog_name)
    client.send(json.dumps({'type': 'speak', 'data': {'utterance': text}}))


def show_text(text):
    try:
        if isfile('/dev/ttyAMA0'):
            call('echo "mouth.text=' + text + '" > /dev/ttyAMA0 &>/dev/null',
                 shell=True)
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
        print('Notifying event:', event)
        if event == 'exit':
            notify.quit_event.set()
            show_text('')
            return
        if event not in all_events:
            return

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


def ntp_sync(*_):
    # Force the system clock to synchronize with internet time servers
    call('service ntp stop', shell=True)
    call('ntpd -gq', shell=True)
    call('service ntp start', shell=True)


def system_shutdown(*_):
    # Turn the system completely off (with no option to inhibit it)
    call('systemctl poweroff -i', shell=True)


def system_reboot(*_):
    # Shut down and restart the system
    call('systemctl reboot -i', shell=True)


def update_only_mycroft():
    call(['apt-get', 'update', '-o', 'Dir::Etc::sourcelist="sources.list.d/repo.mycroft.ai.list"',
          '-o', 'Dir::Etc::sourceparts="-"', '-o', 'APT::Get::List-Cleanup="0"'])


def get_mycroft_package(data):
    # Force a system package update.  Limited to "mycroft-" packages.
    package = "mycroft-core"
    if data and "platform" in data:
        # Support installing/updating "mycroft-XXX" meta packages,
        # but limit to know packages to prevent abuse.
        if data["platform"] == "mark-1":
            package = "mycroft-mark-1"
        elif data["platform"] == "picroft":
            package = "mycroft-picroft"
    return package


def system_update(client, data):
    client.send(json.dumps({'type': 'system.update.processing'}))
    update_only_mycroft()
    call(['apt-get', 'install', get_mycroft_package(data), '-y'])
    client.send(json.dumps({'type': 'system.update.complete'}))


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


def on_message(client, message):
    message = json.loads(message)
    print(message)

    # TODO: Retire the mycroft.XXX messages, keeping for backwards compat
    handler = {
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
    }.get(message['type'])
    if handler:
        handler(client, message['data'])


def main():
    sleep(0.5)

    # Connect to the default websocket used by mycroft-core
    url = 'ws://127.0.0.1:8181/core'
    print('Starting client on:', url)
    client = WebSocketApp(url=url, on_message=on_message)
    if mock:
        Thread(target=run_wifi_setup, args=[client, {}], daemon=True).start()
    client.run_forever()
    print('Client stopped.')


if __name__ == '__main__':
    # Run loop trying to reconnect if there are any issues starting
    # the websocket
    while True:
        try:
            main()
        except KeyboardInterrupt:
            raise
        except:
            traceback.print_exc()
