#!/usr/bin/env python3
from time import sleep


def event(name):
    print(name, flush=True)

sleep(3)
event('ap_up')
sleep(10)
event('ap_device_connected')
sleep(5)
event('ap_device_disconnected')
sleep(20)
event('ap_connection_success')
sleep(2)
