# -*- coding: utf-8 -*-
"""Dependency-free behaviour verification for the connection/lifecycle fixes.

The project normally needs vgamepad, bleak, PyQt5 and pynput on Windows.
This script injects minimal stubs so the same behaviour can be checked on any
machine (CI, Linux, or a fresh Windows box before drivers are installed).

Run from anywhere:  python tests/verify_lifecycle.py

It is intentionally NOT named test_*.py so unittest discovery never mixes
these stubs into tests/test_core.py, which must run against the real modules.
"""
import asyncio
import os
import sys
import threading
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


class _Stub:
    def __getattr__(self, name):
        return 0

    def __call__(self, *args, **kwargs):
        return _Stub()


def make_module(name):
    module = types.ModuleType(name)
    module.__getattr__ = lambda attr: _Stub()
    sys.modules[name] = module
    return module


make_module("vgamepad")
make_module("bleak")
pynput = make_module("pynput")
pynput.mouse = make_module("pynput.mouse")

import main
import controller_command
import dsu_server
import control_type.duo_joycon as duo
import control_type.single_joycon as single

results = []


def check(label, condition):
    results.append((label, bool(condition)))
    print(("PASS " if condition else "FAIL ") + label)


# ---- connection layer -------------------------------------------------
check(
    "MAC formats normalise to the same key",
    main._normalize_mac("BC:89:A6:2A:D4:5A")
    == main._normalize_mac("bc-89-a6-2a-d4-5a")
    == "BC89A62AD45A",
)


class FakeScanner:
    last = None

    def __init__(self, callback):
        self.callback = callback
        self.started = False
        self.stopped = False
        FakeScanner.last = self

    async def start(self):
        self.started = True

    async def stop(self):
        self.stopped = True


main.BleakScanner = FakeScanner
check("scan times out with None",
      asyncio.run(main.scan_for_joycons(timeout=0.05)) is None)
check("scanner.stop() runs on timeout", FakeScanner.last.stopped is True)

stop_event = threading.Event()
stop_event.set()
check("external stop event ends scan",
      asyncio.run(main.scan_for_joycons_with_side(
          timeout=5.0, stop_event=stop_event)) == (None, "Unknown"))
check("scanner.stop() runs on cancellation", FakeScanner.last.stopped is True)


class BareClient:
    services = None
    address = "AABBCCDDEEFF"


try:
    asyncio.run(main._tune_report_rate(BareClient()))
    check("report-rate tuning degrades without exception", True)
except Exception as exc:
    check(f"report-rate tuning degrades without exception: {exc!r}", False)

command = controller_command.ControllerCommand()
left, right = object(), object()
command.clientSending = left
command.expectedResponse = (0x0B, 0x00, 0x03)
command.receive_response(left, bytes.fromhex("0b01000300000000000e00"))
command.clientSending = right
command.receive_response(right, bytes.fromhex("0b01000300000000000800"))
check("command responses are isolated per client",
      command.get_last_response(left).endswith(b"\x0e\x00")
      and command.get_last_response(right).endswith(b"\x08\x00"))
check("consumed response does not leak",
      command.get_last_response(left) is None)


# ---- low battery alert ------------------------------------------------
warnings = []
original_warning = main.warning
main.warning = lambda msg: warnings.append(msg)
main._low_battery_counts.clear()
main._low_battery_alerted.clear()
MAC = "AABBCCDDEEFF"
low = bytes((0, 1 << 2))    # level 1/9 -> 11%, not charging
full = bytes((0, 9 << 2))   # level 9/9 -> 100%
for _ in range(5):
    main.handle_power_report(MAC, low, "Left")
check("low battery warns exactly once", len(warnings) == 1)
for _ in range(3):
    main.handle_power_report(MAC, full, "Left")
for _ in range(5):
    main.handle_power_report(MAC, low, "Left")
check("alert re-arms after recovery", len(warnings) == 2)
main.warning = original_warning


# ---- mouse loop shutdown ----------------------------------------------
duo._mouse_stop.clear()
duo_thread = threading.Thread(target=duo.mouse_loop, daemon=True)
duo._mouse_loop_thread = duo_thread
duo_thread.start()
duo.stop_mouse_loop()
check("duo mouse loop exits on stop", not duo_thread.is_alive())

single_stop = threading.Event()
single._mouse_stop_events[7] = single_stop
single._mouse_events[7] = threading.Event()
single_thread = threading.Thread(
    target=single.mouse_loop, args=(7, single_stop), daemon=True
)
single._mouse_threads[7] = single_thread
single_thread.start()
single.stop_mouse_loops()
check("single mouse loops exit on stop", not single_thread.is_alive())
check("single stop flag is set", single_stop.is_set())


# ---- shutdown ---------------------------------------------------------
called = {"stop": 0}
original_stop = dsu_server.stop_dsu
dsu_server.stop_dsu = lambda: called.__setitem__("stop", called["stop"] + 1)
main._connected_devices.clear()
asyncio.run(main.shutdown())
dsu_server.stop_dsu = original_stop
check("shutdown() calls stop_dsu()", called["stop"] == 1)


class BusySocket:
    def __init__(self, *a, **k):
        pass

    def bind(self, addr):
        raise OSError("port 26760 in use")

    def settimeout(self, value):
        pass


original_socket = dsu_server.socket.socket
dsu_server.socket.socket = BusySocket
dsu_server.sock = None
try:
    check("main_dsu() handles port conflict", dsu_server.main_dsu() is False)
finally:
    dsu_server.socket.socket = original_socket
    dsu_server.sock = None

failed = [label for label, ok in results if not ok]
print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
sys.exit(1 if failed else 0)
