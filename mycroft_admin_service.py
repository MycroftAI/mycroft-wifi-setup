#!/usr/bin/env python3
import sys

import random
sys.path += ['.']  # noqa

import json
from os.path import join, dirname, realpath
from subprocess import call, Popen, PIPE
from threading import Thread
from time import sleep
from websocket import WebSocketApp
from wifisetup import config


def get_resource(name):
    data_dir = dirname(realpath(sys.argv[0]))
    data_dir = getattr(sys, '_MEIPASS', data_dir)
    return join(data_dir, name)


lang = 'en-us'
run_in_progress = False
exe_file = get_resource('mycroft-wifi-setup')


def get_dialog(name):
    with open(get_resource(join('dialog', lang, name + '.dialog'))) as f:
        return random.choice(list(filter(bool, f.read().split('\n'))))


def speak_dialog(client, dialog_name):
    text = get_dialog(dialog_name)
    client.send(json.dumps({'type': 'speak', 'data': {'utterance': text}}))


def show_text(text):
    try:
        call('echo "mouth.text=' + text + '" > /dev/ttyAMA0', shell=True)
    except OSError:
        pass


def run_wifi_setup(client, data):
    global lang
    if 'lang' in data:
        lang = data['lang']
    allow_timeout = data.get('allow_timeout', True)
    p = Popen([exe_file, 'wifi.run', str(allow_timeout)], stdout=PIPE)

    def parse_output():
        for line in p.stdout:
            line = line.decode().strip()
            dialog_events = {
                'ap_up', 'ap_device_connected', 'ap_device_disconnected', 'ap_down'
            }
            visual_events = {
                'ap_up': '12345678',
                'ap_device_connected': 'start.mycroft.ai',
                'ap_device_disconnected': '12345678'
            }
            if line in dialog_events:
                speak_dialog(client, line)
            if line in visual_events:
                show_text(visual_events[line])
            if line == 'ap_up':
                parse_output.is_up = True
            if line == 'ap_connection_success':
                break
    parse_output.is_up = False
    t = Thread(target=parse_output)
    t.daemon = True
    t.start()
    sleep(0.5)
    if p.poll():
        speak_dialog(client, 'ap_init_fail')
        if p.stderr:
            print(p.stderr.read())
        return p.poll()
    try:
        sleep(3.5)
        if not parse_output.is_up:
            speak_dialog(client, 'ap_start_fail')
        else:
            p.wait()
    except:
        p.terminate()


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
        'ssh.enable': ssh_enable,
        'ssh.disable': ssh_disable,
    }.get(message['type'])
    if handler:
        if not run_in_progress:
            run_in_progress = True
            handler(client, message['data'])
            run_in_progress = False


def main():
    url = 'ws://127.0.0.1:8181/core'
    print('Starting client on:', url)
    client = WebSocketApp(url=url, on_message=on_message)
    client.run_forever()
    print('Client stopped.')


if __name__ == '__main__':
    main()
