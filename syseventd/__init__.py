#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
import os.path
import math
import signal
import logging
import pulsectl
import dasbus
from playsound import playsound
from dasbus.loop import EventLoop
from dasbus.server.interface import dbus_interface
from dasbus.identifier import DBusServiceIdentifier
from dasbus.connection import SessionMessageBus
from gi.repository import GLib


logging.basicConfig(level=logging.INFO)

PULSE = pulsectl.Pulse(__name__, threading_lock=False)
EX_CODE = os.EX_OK

VOL_STEP = 0.03

SESSION_BUS = SessionMessageBus()

SYSEVENTD = DBusServiceIdentifier(
    namespace=("net", "cephalopo", "Syseventd"),
    message_bus=SESSION_BUS
)

NOTIFICATION_PROXY = SESSION_BUS.get_proxy(
    "org.freedesktop.Notifications",
    "/org/freedesktop/Notifications"
)

LOOP = EventLoop()

XOB_FILE = os.path.join(os.environ['XDG_RUNTIME_DIR'], 'xob')
WOB_FILE = os.path.join(os.environ['XDG_RUNTIME_DIR'], 'wob.sock')


def term_handler(signum, frame):
    print('Signal handler called with signal', signum)
    if LOOP:
        LOOP.quit()
    else:
        print("no loop to quit")


signal.signal(signal.SIGTERM, term_handler)
signal.signal(signal.SIGINT, term_handler)


# icon names without URI path should be according to
# https://specifications.freedesktop.org/icon-naming-spec/icon-naming-spec-latest.html
def _send_notify(icon_name, urgency_level, body):
    id = NOTIFICATION_PROXY.Notify(
        "syseventd",            # application name
        0,                      # 'id_num_to_repl'
        icon_name,              # icon name
        "syseventd",            # title
        body,                   # message
        [],                     # action list
        {"urgency": GLib.Variant.new_byte(urgency_level)},  # hints
        2000                    # notification wait in milliseconds
    )
    logging.info("send notify. got id %d" % (id))


def log_warn(msg: str):
    logging.warn(msg)
    _send_notify("dialog-warning", 2, msg)


def notify_info(msg: str):
    _send_notify("dialog-information", 0, msg)


def print_events(ev):
    pass
    # en = pulsectl.PulseEventFacilityEnum
    # if ev.facility == en.sink_input:
    # print('Pulse event: fac=%s, index=%s, t=%s' % (ev.facility, ev.index, ev.t))
    # Raise PulseLoopStop for event_listen() to return before timeout (if any)
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
    if next_sink is None:
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


# ignore volume attempts on: alsa_output.pci-0000_0b_00.4.analog-stereo
# it should handle volume via hardware
ignored_device_names = ('alsa_output.pci-0000_0b_00.4.analog-stereo')


def _volume(up):
    srv_info = PULSE.server_info()
    def_sink_name = srv_info.default_sink_name
    default_sink = PULSE.get_sink_by_name(def_sink_name)

    # for sink in PULSE.sink_list():
    if default_sink.name in ignored_device_names:
        logging.info("ignoring device, %s" % (default_sink.name))
    else:
        default_sink_vols = PULSE.volume_get_all_chans(default_sink)
        if up:
            new_vol = default_sink_vols + VOL_STEP
        else:
            new_vol = default_sink_vols - VOL_STEP

        if new_vol > 1.000:
            new_vol = 1.000
        if new_vol < 0.000:
            new_vol = 0.000
        PULSE.volume_set_all_chans(default_sink, new_vol)
        if os.path.exists(XOB_FILE):
            with open(XOB_FILE, "w") as f:
                f.write("%d\n" % (math.floor(new_vol * 100)))
        elif os.path.exists(WOB_FILE):
            with open(WOB_FILE, "w") as f:
                f.write("%d\n" % (math.floor(new_vol * 100)))
        else:
            logging.info("no xob file '%s' or wob file '%s'", XOB_FILE, WOB_FILE)
        playsound("/usr/share/sounds/freedesktop/stereo/audio-volume-change.oga")


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


@dbus_interface(SYSEVENTD.interface_name)
class Syseventd(object):
    """The DBus interface"""

    def Volume(self, change: int):
        if change == 1:
            logging.info("volume up")
            _volume(True)
        elif change == 0:
            logging.info("toggle mute")
            _on_toggle_mute()
        elif change == -1:
            logging.info("volume down")
            _volume(False)
        else:
            logging.warn("unknown volume signal: %d" % (change))

    def MicrophoneToggle(self):
        logging.info("toggle mic mute")
        _on_toggle_mic_mute()

    def SwitchSoundCard(self):
        logging.info("switch sound card")
        _on_switch_sink()


def main():
    # print(XMLGenerator.prettify_xml(Syseventd.__dbus_xml__))

    try:
        hello_world = Syseventd()

        # Publish the instance
        SESSION_BUS.publish_object(SYSEVENTD.object_path, hello_world)

        # Register the service
        SESSION_BUS.register_service(SYSEVENTD.service_name)
        try:
            notify_info("started")
        except dasbus.error.DBusError as err:
            logging.error("DBUS error, '%s'", err)
            sys.exit(16)
        # _send_notify("dialog-info", 1, "started")
        # Start the event loop.
        LOOP.run()
    finally:
        # Unregister the DBus service and objects.
        SESSION_BUS.disconnect()
        PULSE.close()
