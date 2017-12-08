#!/usr/bin/env python3
import sys
sys.path += ['.']  # noqa

import json
import traceback
import random
from os.path import join, dirname, realpath, isfile
from subprocess import call, Popen, PIPE
from threading import Thread, Timer, Event
from time import sleep
from websocket import WebSocketApp


def get_resource(name):
    data_dir = dirname(realpath(sys.argv[0]))
    data_dir = getattr(sys, '_MEIPASS', data_dir)
    return join(data_dir, name)


lang = 'en-us'
run_in_progress = False
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
            call('echo "mouth.text=' + text + '" > /dev/ttyAMA0 &>/dev/null', shell=True)
    except OSError:
        pass


def run_wifi_setup(client, data):
    dialog_events = {
        'device.not.connected',
        'device.connected',
        'ap_device_connected',
        'ap_device_disconnected',
        'ap_down'
    }
    visual_events = {
        'device.not.connected': '12345678',
        'device.connected': 'start.mycroft.ai',
        'ap_connection_success': ''
    }
    event_transitions = {
        'ap_up': 'device.not.connected',
        'ap_device_connected': 'device.connected',
        'ap_device_disconnected': 'device.not.connected',
        'ap_connection_success': 'exit',
        'ap_down': 'exit'
    }
    all_events = set(list(dialog_events) +
                     list(visual_events) +
                     list(event_transitions))

    global lang
    lang = data.get('lang', lang)
    allow_timeout = data.get('allow_timeout', True)
    p = Popen([exe_file, 'wifi.run', str(allow_timeout)], stdout=PIPE)

    def notify(event):
        """Continuously show and speak a message to the user on an event"""
        print('Notifying event:', event)
        if event == 'exit':
            notify.quit_event.set()
            return
        if event not in all_events:
            return

        next_event = event_transitions.get(event, event)
        delay = 0.1 if next_event != event else 30

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
            notify('ap_down')

    Thread(target=parse_output, daemon=True).start()

    notify.quit_event = Event()
    notify.quit_event.set()
    notify.timer = Timer(10, speak_dialog, [client, 'ap_start_fail'])
    notify.timer.start()
    notify.timer.join()

    notify.quit_event.wait()
    sleep(5)  # Give the wifi setup process time to shutdown of it's own
    p.terminate()  # In case anything has gone bonkers, terminarte the process


def ssh_enable(*_):
    call('systemctl enable ssh.service', shell=True)
    call('systemctl start ssh.service', shell=True)


def ssh_disable(*_):
    call('systemctl stop ssh.service', shell=True)
    call('systemctl disable ssh.service', shell=True)


def on_message(client, message):
    global run_in_progress
    message = json.loads(message)
    print(message)

    handler = {
        'mycroft.wifi.start': run_wifi_setup,
        'mycroft.wifi.reset': lambda *_: call([exe_file, 'wifi.reset']),
        'mycroft.ssh.enable': ssh_enable,
        'mycroft.ssh.disable': ssh_disable,
    }.get(message['type'])
    if handler:
        if not run_in_progress:
            run_in_progress = True
            handler(client, message['data'])
            run_in_progress = False


def main():
    sleep(0.5)
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
