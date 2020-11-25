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
import threading
import subprocess

logging.basicConfig(level=logging.INFO)

PULSE = pulsectl.Pulse(__name__, threading_lock=False)
MAIN_EVENT = threading.Event()
EX_CODE = os.EX_OK

VOL_STEP = 0.03


def _exec_notify_send(urg, body, event):
    cmd = ["notify-send", "-u", urg, __name__, body]
    subprocess.check_output(cmd)
    event.set()


def _send_notify(urg, body, block=False):
    event = threading.Event()
    try:
        thread = threading.Thread(target=_exec_notify_send(urg, body, event))
        thread.name = __name__
        thread.start()
        if block:
            thread.join(timeout=10)
            return event.is_set()
        return event
    except Exception:
        logging.exception("Unhandled exception for sending notification.")
        raise


def log_warn(msg: str):
    logging.warn(msg)
    _send_notify("critical", msg)


def notify_info(msg: str):
    _send_notify("low", msg)


def _exit_error(msg):
    logging.error(msg)
    global EX_CODE
    EX_CODE = os.EX_SOFTWARE
    _send_notify("critical", msg)
    MAIN_EVENT.set()


def print_events(ev):
    pass
    # en = pulsectl.PulseEventFacilityEnum
    # if ev.facility == en.sink_input:
    # print('Pulse event: fac=%s, index=%s, t=%s' % (ev.facility, ev.index, ev.t))
    ### Raise PulseLoopStop for event_listen() to return before timeout (if any)
    # raise pulsectl.PulseLoopStop


def _on_switch_sink():
    srv_info = PULSE.server_info()
    def_sink_name = srv_info.default_sink_name
    notify_info("switching from %s" % def_sink_name)
    sink_list = PULSE.sink_list()
    next_sink = None
    for sink in sink_list:
        if sink.name == def_sink_name:
            continue
        next_sink = sink
    if next_sink == None:
        log_warn("no different sink from default")
        return
    logging.info("default sink name: %s" % def_sink_name)
    logging.info("next sink: %s" % next_sink.name)
    PULSE.sink_default_set(next_sink)

    sink_input_list = PULSE.sink_input_list()
    for sink_input in sink_input_list:
        try:
            PULSE.sink_input_move(sink_input.index, next_sink.index)
        except pulsectl.pulsectl.PulseOperationFailed:
            log_warn("unable to move sink_input, %s" % (sink_input))
    logging.info("moved all sink")
    for i in range(0, 2):
        playsound("/usr/share/sounds/freedesktop/stereo/dialog-warning.oga")
    notify_info("sink switched: %s" % next_sink.name)


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


def _on_toggle_mic_mute():
    srv_info = PULSE.server_info()
    def_source_name = srv_info.default_source_name
    default_source = PULSE.get_source_by_name(def_source_name)
    if default_source.mute == 0:
        PULSE.mute(default_source, True)
    elif default_source.mute == 1:
        PULSE.mute(default_source, False)
    else:
        logging.error("unknown mute state, '%d", default_source.mute)


def _on_release(key):
    key_dec = "{0}".format(key)
    try:
        if "269025043" in key_dec:
            logging.info("volume up")
            _on_volume_up()
        elif "269025041" in key_dec:
            logging.info("volume down")
            _on_volume_down()
        elif "269025042" in key_dec:
            logging.info("toggle mute")
            _on_toggle_mute()
        elif "269025202" in key_dec:
            logging.info("toggle mic mute")
            _on_toggle_mic_mute()
    except:
        _exit_error("key error")


def main():
    hotkey_listener = keyboard.GlobalHotKeys(
        {"<cmd>+<shift>+a": _on_switch_sink})
    hotkey_listener.start()

    key_listener = keyboard.Listener(on_release=_on_release)
    key_listener.start()
    # TODO: listen on pulse events and move newly created sink inputs
    # to default if not targetting default
    # PULSE.event_mask_set('all')
    # PULSE.event_callback_set(print_events)
    # PULSE.event_listen()
    # key_listener.join()
    _send_notify("low", "started")
    MAIN_EVENT.wait()
    logging.info("main event set")

    PULSE.close()
    sys.exit(EX_CODE)
