#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
import pulsectl
import logging
from pprint import pprint
from playsound import playsound
from pynput import keyboard
import inspect

logging.basicConfig(level=logging.INFO)

PULSE = pulsectl.Pulse(__name__, threading_lock=True)

VOL_STEP = 0.03

def _on_switch_sink():
    srv_info = PULSE.server_info()
    def_sink_name = srv_info.default_sink_name
    sink_list = PULSE.sink_list()
    next_sink = None
    for sink in sink_list:
        if sink.name == def_sink_name:
            continue
        next_sink = sink
    if next_sink == None:
        logging.warning("no different sink from default")
        return
    logging.info("default sink name: %s" % def_sink_name)
    logging.info("next sink: %s" % next_sink.name)
    PULSE.sink_default_set(next_sink)

    sink_input_list = PULSE.sink_input_list()
    for sink_input in sink_input_list:
        PULSE.sink_input_move(sink_input.index, next_sink.index)
    logging.info("moved all sink")
    for i in range(0,2):
        playsound("/usr/share/sounds/freedesktop/stereo/dialog-warning.oga")


def _on_volume_up():
    srv_info = PULSE.server_info()
    def_sink_name = srv_info.default_sink_name
    default_sink = PULSE.get_sink_by_name(def_sink_name)
    default_sink_vols = PULSE.volume_get_all_chans(default_sink)
    new_vol = default_sink_vols + VOL_STEP
    if new_vol > 1.000:
        new_vol = 1.000
    PULSE.volume_set_all_chans(default_sink, new_vol)


def _on_volume_down():
    srv_info = PULSE.server_info()
    def_sink_name = srv_info.default_sink_name
    default_sink = PULSE.get_sink_by_name(def_sink_name)
    default_sink_vols = PULSE.volume_get_all_chans(default_sink)
    new_vol = default_sink_vols - VOL_STEP
    if new_vol < 0.000:
        new_vol = 0.000
    PULSE.volume_set_all_chans(default_sink, new_vol)


def _on_toggle_mute():
    srv_info = PULSE.server_info()
    def_sink_name = srv_info.default_sink_name
    default_sink = PULSE.get_sink_by_name(def_sink_name)
    if default_sink.mute == 0:
        PULSE.mute(default_sink, True)
    elif default_sink.mute == 1:
        PULSE.mute(default_sink, False)
    else:
        logging.error("unknown mute state, '%d", default_sink.mute)


def _on_release(key):
    key_dec = "{0}".format(key)

    if "269025043" in key_dec:
        logging.info("volume up")
        _on_volume_up()
    elif "269025041" in key_dec:
        logging.info("volume down")
        _on_volume_down()
    elif "269025042" in key_dec:
        logging.info("toggle mute")
        _on_toggle_mute()


def main():
    key_listener = keyboard.Listener(on_release=_on_release)
    key_listener.start()

    hotkey_listener = keyboard.GlobalHotKeys(
        {"<cmd>+<shift>+a": _on_switch_sink})
    hotkey_listener.start()

    key_listener.join()
    hotkey_listener.join()

    # TODO: listen on pulse events and move newly created sink inputs
    # to default if not targetting default

    PULSE.close()

    return 0
