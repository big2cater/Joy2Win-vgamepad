import asyncio
import struct
import tempfile
import time
import unittest
import configparser
import contextlib
import io
from types import SimpleNamespace

import controller_command
import dsu_server
import main
from control_type.mouse_scroll import scroll_notches
from controller_manager import ControllerManager
from controllers.battery import battery_percentage_from_voltage
from gui import ControllerPairTab, persist_dsu_setting


class FakeCommandClient:
    def __init__(self, respond=False, response_status=0x01):
        self.respond = respond
        self.response_status = response_status
        self.writes = 0

    async def write_gatt_char(self, uuid, data, response=None):
        self.writes += 1
        if self.respond:
            response = bytes((data[0], self.response_status, data[2], data[3]))
            asyncio.get_running_loop().call_soon(
                controller_command.ControllerCommand().receive_response,
                self,
                response,
            )


class ScrollConversionTests(unittest.TestCase):
    """The wheel consumer used int(value / 32768), which truncates every value
    in -32767..32767 to zero, so scrolling never worked in either mouse mode."""

    def test_full_positive_tilt_scrolls_down(self):
        state = {}
        total = sum(scroll_notches(state, "acc", 32767) for _ in range(60))
        self.assertGreater(total, 0)

    def test_full_negative_tilt_scrolls_up(self):
        state = {}
        total = sum(scroll_notches(state, "acc", -32767) for _ in range(60))
        self.assertLess(total, 0)

    def test_slow_tilt_accumulates_instead_of_being_dropped(self):
        state = {}
        total = sum(scroll_notches(state, "acc", 4000) for _ in range(40))
        self.assertGreater(total, 0)

    def test_remainder_is_carried_between_reports(self):
        state = {}
        first = scroll_notches(state, "acc", 100000)
        second = scroll_notches(state, "acc", 100000)
        self.assertEqual((first, second), (0, 1))


class MouseModeTests(unittest.TestCase):
    """config.ini's mouse_mode (0/1/2) was parsed but never read by any code
    path; the GUI checkbox only ever passed a boolean."""

    def setUp(self):
        from control_type import duo_joycon, single_joycon
        self.duo = duo_joycon
        self.single = single_joycon

    def test_gui_toggle_maps_to_automatic_mode(self):
        self.duo.set_mouse_enabled(90, True)
        self.assertEqual(self.duo.mouse_mode(90), 1)
        self.assertTrue(self.duo.is_mouse_enabled(90))
        self.assertFalse(self.duo.is_mouse_always(90))

        self.duo.set_mouse_enabled(90, False)
        self.assertEqual(self.duo.mouse_mode(90), 0)
        self.assertFalse(self.duo.is_mouse_enabled(90))

    def test_unset_pair_follows_config(self):
        expected = self.duo._config_mouse_mode()
        self.assertEqual(self.duo.mouse_mode(91), expected)
        self.assertEqual(self.single.mouse_mode(91), expected)

    def test_always_mode_is_recognised(self):
        self.duo._pair_mouse_mode[92] = 2
        try:
            self.assertTrue(self.duo.is_mouse_enabled(92))
            self.assertTrue(self.duo.is_mouse_always(92))
        finally:
            self.duo._pair_mouse_mode.pop(92, None)


class MouseTuningTests(unittest.TestCase):
    """Sensitivity and lift-off distance were hard-coded (6 and 512) in both
    the duo and single paths, so the feel could not be adjusted at all."""

    def _with_config(self, sensitivity, threshold):
        from control_type import mouse_scroll
        saved = mouse_scroll.Config

        class Stub:
            mouse_sensitivity = sensitivity
            mouse_surface_threshold = threshold

        mouse_scroll.Config = Stub
        self.addCleanup(setattr, mouse_scroll, "Config", saved)
        return mouse_scroll

    def test_default_sensitivity_keeps_the_original_divisor(self):
        module = self._with_config(100, 512)
        self.assertEqual(module.mouse_divisor(), 6.0)

    def test_higher_sensitivity_moves_faster(self):
        module = self._with_config(200, 512)
        self.assertEqual(module.mouse_divisor(), 3.0)

    def test_out_of_range_values_are_clamped(self):
        module = self._with_config(9999, 99999)
        self.assertEqual(module.mouse_divisor(), 6.0 * 100.0 / 400)
        self.assertEqual(module.surface_threshold(), 4095)

    def test_threshold_reads_config(self):
        module = self._with_config(100, 1024)
        self.assertEqual(module.surface_threshold(), 1024)


class DsuPacketTests(unittest.TestCase):
    def test_length_field_carries_the_payload_size(self):
        """Clients read this as "bytes after the header" and compute the total
        themselves. Sending the total instead made Eden stop discovering the
        controller, so this pins the observed-compatible value."""
        from dsu_server import _build_packet
        packet = _build_packet(bytes(12))
        declared = int.from_bytes(packet[6:8], "little")
        self.assertEqual(declared, 12)
        self.assertEqual(len(packet), 12 + 16)

    def test_crc_covers_header_and_payload_with_zeroed_field(self):
        import zlib
        from dsu_server import _build_packet
        packet = _build_packet(bytes(20))
        zeroed = bytearray(packet)
        zeroed[8:12] = b"\x00\x00\x00\x00"
        expected = zlib.crc32(bytes(zeroed)) & 0xFFFFFFFF
        self.assertEqual(int.from_bytes(packet[8:12], "little"), expected)


class MouseOutputTests(unittest.TestCase):
    """Raw Input needs a virtual HID mouse (WinUHid); SendInput must remain the
    fallback so the feature never hard-fails on a machine without the driver."""

    def tearDown(self):
        from control_type import virtual_mouse
        virtual_mouse.release_mouse_output()

    def test_button_indices_are_zero_based(self):
        # WinUHidMouse.h defines WUHM_BUTTON_LEFT as 0x01, but the implementation
        # does "1 << ButtonIndex", so callers must pass 0 for the left button.
        from control_type.virtual_mouse import (
            BTN_LEFT, BTN_MIDDLE, BTN_RIGHT,
        )
        self.assertEqual((BTN_LEFT, BTN_RIGHT, BTN_MIDDLE), (0, 1, 2))

    def test_scroll_unit_matches_wheel_delta(self):
        from control_type.virtual_mouse import SCROLL_UNITS_PER_NOTCH
        self.assertEqual(SCROLL_UNITS_PER_NOTCH, 120)

    def test_missing_driver_falls_back_to_sendinput(self):
        """With the driver absent the forced winuhid mode must still yield a
        working backend instead of raising."""
        from control_type import virtual_mouse
        saved_config = virtual_mouse.Config
        saved_api = virtual_mouse._WinUHidApi

        class Stub:
            mouse_output = "winuhid"

        class NoApi:
            def __init__(self):
                self.core = None
                self.devs = None
                self.version = 0

        virtual_mouse.Config = Stub
        virtual_mouse._WinUHidApi = NoApi
        self.addCleanup(setattr, virtual_mouse, "Config", saved_config)
        self.addCleanup(setattr, virtual_mouse, "_WinUHidApi", saved_api)
        self.assertEqual(virtual_mouse.get_mouse_output().name, "SendInput")

    def test_unknown_mode_falls_back_to_auto(self):
        """A typo in the config must not disable mouse output."""
        from control_type import virtual_mouse
        saved_config = virtual_mouse.Config
        saved_api = virtual_mouse._WinUHidApi

        class Stub:
            mouse_output = "nonsense"

        class NoApi:
            def __init__(self):
                self.core = None
                self.devs = None
                self.version = 0

        virtual_mouse.Config = Stub
        virtual_mouse._WinUHidApi = NoApi
        self.addCleanup(setattr, virtual_mouse, "Config", saved_config)
        self.addCleanup(setattr, virtual_mouse, "_WinUHidApi", saved_api)
        self.assertEqual(virtual_mouse.get_mouse_output().name, "SendInput")


class GuiSlotTests(unittest.TestCase):
    """Slots run inside Qt's event loop. An uncaught exception there makes
    PyQt5 call qFatal() and the window disappears with no traceback, so these
    call the real handlers instead of trusting review."""

    @classmethod
    def setUpClass(cls):
        import sys as _sys
        from PyQt5.QtWidgets import QApplication
        # Qt only allows one QApplication per process.
        cls.app = QApplication.instance() or QApplication(_sys.argv)

    def test_strength_and_sensitivity_slots_do_not_raise(self):
        from config import Config
        from gui import ControllerPairTab

        saved = Config.set_and_save
        Config.set_and_save = lambda self, key, value: True
        self.addCleanup(setattr, Config, "set_and_save", saved)

        tab = ControllerPairTab(0)
        self.addCleanup(tab.deleteLater)
        # Regression: controller_tabs is a list. Calling .values() on it raised
        # AttributeError inside valueChanged, which aborted the whole process.
        tab.on_rumble_strength_changed(50)
        tab.on_mouse_sensitivity_changed(120)


class CoreRegressionTests(unittest.TestCase):
    def test_feature_select_leaves_phantom_trigger_bits_clear(self):
        """FEATSEL 0xFF makes the Joy-Con emit extra report fields that show up
        as continuously pressed ZL/ZR (Switch2Connect records this against its
        0.10.1 build). Bits 0x08 and 0x40 must stay clear, the rest unchanged.
        """
        for name in ("JOY2_INIT_SENSOR_DATA", "JOY2_FINALIZE_SENSOR_DATA",
                     "JOY2_START_SENSOR_DATA"):
            data = bytes.fromhex(controller_command.COMMAND_TYPE[name]["data"])
            self.assertEqual(len(data), 12, name)
            featsel = data[8]
            self.assertEqual(featsel, 0xB7, name)
            self.assertFalse(featsel & 0x08, f"{name}: bit 0x08 must stay off")
            self.assertFalse(featsel & 0x40, f"{name}: bit 0x40 must stay off")
            self.assertTrue(featsel & 0x04, f"{name}: motion must stay on")

    def test_side_from_advertisement_reads_the_product_id(self):
        """The advertisement carries the product ID right after the 5-byte
        prefix, so the scan can tell the halves apart before connecting."""
        prefix = main.manufact["data-prefix"]

        def advertisement(pid):
            return prefix + pid.to_bytes(2, "little") + b"\x00" * 8

        self.assertEqual(main.side_from_advertisement(advertisement(0x2067)), "Left")
        self.assertEqual(main.side_from_advertisement(advertisement(0x2066)), "Right")
        self.assertEqual(main.side_from_advertisement(advertisement(0x2069)), "Pro")
        self.assertEqual(main.side_from_advertisement(advertisement(0x1234)), "Unknown")
        self.assertEqual(main.side_from_advertisement(b"\x01\x00"), "Unknown")

    def test_side_detection_uses_the_vibration_characteristic(self):
        """A Joy-Con 2 advertisement carries no L/R mark, so the connect log
        said "(None)" and the user had to choose a mode by hand. The GATT table
        differs per half and settles it after connecting."""
        from controllers.hd_rumble import UUID_RUMBLE_LEFT, UUID_RUMBLE_RIGHT

        def client_with(*uuids):
            table = {u: SimpleNamespace(uuid=u) for u in uuids}
            return SimpleNamespace(
                services=SimpleNamespace(get_characteristic=table.get)
            )

        self.assertEqual(
            main._detect_side_from_gatt(client_with(UUID_RUMBLE_LEFT)), "Left")
        self.assertEqual(
            main._detect_side_from_gatt(client_with(UUID_RUMBLE_RIGHT)), "Right")
        self.assertIsNone(main._detect_side_from_gatt(client_with()))
        self.assertIsNone(main._detect_side_from_gatt(
            SimpleNamespace(services=None)))

    def test_controller_command_retries_and_times_out(self):
        command = controller_command.ControllerCommand()
        old_timeout = command.RESPONSE_TIMEOUT
        command.RESPONSE_TIMEOUT = 0.02
        try:
            client = FakeCommandClient(respond=False)
            with contextlib.redirect_stdout(io.StringIO()):
                result = asyncio.run(command.send_command(client, "JOY2_CONNECTED_VIBRATION"))
            self.assertFalse(result)
            self.assertEqual(client.writes, command.MAX_ATTEMPTS)
        finally:
            command.RESPONSE_TIMEOUT = old_timeout

    def test_controller_command_accepts_matching_response(self):
        client = FakeCommandClient(respond=True)
        result = asyncio.run(
            controller_command.ControllerCommand().send_command(
                client, "JOY2_CONNECTED_VIBRATION"
            )
        )
        self.assertTrue(result)
        self.assertEqual(client.writes, 1)

    def test_controller_command_rejects_error_response(self):
        command = controller_command.ControllerCommand()
        old_timeout = command.RESPONSE_TIMEOUT
        command.RESPONSE_TIMEOUT = 0.02
        try:
            client = FakeCommandClient(respond=True, response_status=0x00)
            with contextlib.redirect_stdout(io.StringIO()):
                result = asyncio.run(command.send_command(client, "JOY2_CONNECTED_VIBRATION"))
            self.assertFalse(result)
            self.assertEqual(client.writes, command.MAX_ATTEMPTS)
        finally:
            command.RESPONSE_TIMEOUT = old_timeout

    def test_dsu_info_is_one_packet_per_slot(self):
        original = dsu_server._get_slot_info
        dsu_server._get_slot_info = lambda slot: (slot == 2, 5 if slot == 2 else 0)
        try:
            packet = asyncio.run(dsu_server.responseInfoController(2))
        finally:
            dsu_server._get_slot_info = original
        self.assertEqual(len(packet), 32)
        # 16 = payload length, which is what DSU clients actually expect here.
        # Eden loses the controller entirely if this carries the total instead.
        self.assertEqual(struct.unpack_from('<H', packet, 6)[0], 16)
        self.assertEqual(packet[16:20], bytes.fromhex('01001000'))
        self.assertEqual(packet[20], 2)
        self.assertEqual(packet[21], 2)
        self.assertEqual(packet[31], 1)

    def test_dsu_stale_client_is_pruned(self):
        with dsu_server._state_lock:
            dsu_server._clients.clear()
            dsu_server._clients[("127.0.0.1", 12345)] = (
                1, 0, bytes(6), time.monotonic() - dsu_server.DSU_CLIENT_TIMEOUT - 1
            )
            dsu_server._prune_clients_locked()
            self.assertFalse(dsu_server._clients)

    def test_invalid_power_level_is_ignored(self):
        calls = []
        original = main.get_controller_manager
        main.get_controller_manager = lambda: type(
            "Manager", (), {"update_battery": lambda self, *a, **kw: calls.append((a, kw))}
        )()
        try:
            main.handle_power_report("AABB", bytes((0, 0x3C)))  # level bits = 15
        finally:
            main.get_controller_manager = original
        self.assertEqual(calls, [])

    def test_native_battery_capture_is_stopped_before_main_input(self):
        class FakeClient:
            def __init__(self):
                self.stopped = []

            async def start_notify(self, uuid, callback):
                callback(0, bytes((1, 7 << 2)))

            async def stop_notify(self, uuid):
                self.stopped.append(uuid)

        calls = []
        original = main.get_controller_manager
        main.get_controller_manager = lambda: type(
            "Manager", (), {"update_battery": lambda self, *a, **kw: calls.append((a, kw))}
        )()
        client = FakeClient()
        try:
            captured = asyncio.run(
                main.capture_power_level(client, "Left", "AABB", timeout=0.1)
            )
        finally:
            main.get_controller_manager = original

        self.assertTrue(captured)
        self.assertEqual(calls[0][0][1], 78)
        self.assertEqual(client.stopped, [controller_command.UUID_POWER_LEFT])

    def test_battery_voltage_curve(self):
        # Joy-Con 2 reports ~0.6 V below the cell voltage. A full controller
        # reads about 3.6 V, which the old 3.3-4.2 V curve called ~20%.
        self.assertEqual(battery_percentage_from_voltage(2700), 0)
        self.assertEqual(battery_percentage_from_voltage(3300), 75)
        self.assertEqual(battery_percentage_from_voltage(3600), 100)
        self.assertEqual(battery_percentage_from_voltage(3631), 100)
        self.assertGreaterEqual(battery_percentage_from_voltage(3460), 80)
        self.assertIsNone(battery_percentage_from_voltage(0))
        self.assertIsNone(battery_percentage_from_voltage(5000))

    def test_controller_command_keeps_response_payload(self):
        client = FakeCommandClient(respond=True)
        result = asyncio.run(
            controller_command.ControllerCommand().send_command(
                client, "JOY2_GET_BATTERY_VOLTAGE"
            )
        )
        self.assertTrue(result)
        self.assertEqual(
            controller_command.ControllerCommand().lastResponse[:4],
            bytes((0x0B, 0x01, 0x00, 0x03)),
        )

    def test_player_led_values_are_bitmasks(self):
        self.assertEqual([main.get_player_led_value(i) for i in range(4)], ['1', '2', '4', '8'])

    def test_battery_display_marks_charging(self):
        class FakeProgressBar:
            def setValue(self, value):
                self.value = value

            def setFormat(self, value):
                self.format = value

            def setStyleSheet(self, value):
                self.style = value

        bar = FakeProgressBar()
        ControllerPairTab._set_battery_display(bar, 78, True, True)
        self.assertEqual(bar.value, 78)
        self.assertEqual(bar.format, '充电中 %p%')
        self.assertIn('#2196F3', bar.style)

    def test_battery_update_accepts_different_mac_formats(self):
        manager = ControllerManager()
        pair_id = asyncio.run(
            manager.assign_joycon(
                SimpleNamespace(), "Left", "BC:89:A6:2A:D4:5A", preferred_pair=0
            )
        )
        manager.update_battery("BC89A62AD45A", 45)
        self.assertEqual(pair_id, 0)
        self.assertEqual(manager.get_pair(0).left.battery_level, 45)
        self.assertIs(
            manager.get_pair_by_mac("bc-89-a6-2a-d4-5a"), manager.get_pair(0)
        )

    def test_connection_timeout_cleans_ble_resources(self):
        class FakeClient:
            instance = None

            def __init__(self, *args, **kwargs):
                FakeClient.instance = self
                self.is_connected = False
                self.stopped = []
                self.disconnected = False

            async def connect(self):
                self.is_connected = True
                raise asyncio.TimeoutError()

            async def stop_notify(self, uuid):
                self.stopped.append(uuid)

            async def disconnect(self):
                self.is_connected = False
                self.disconnected = True

        class FakeManager:
            def __init__(self):
                self.removed = []

            def get_pair_by_mac(self, mac):
                return None

            async def remove_joycon(self, mac):
                self.removed.append(mac)

        manager = FakeManager()
        old_client = main.BleakClient
        old_manager = main.get_controller_manager
        main.BleakClient = FakeClient
        main.get_controller_manager = lambda: manager
        try:
            device = SimpleNamespace(name='Joy-Con 2', address='00:11:22:33:44:55')
            result = asyncio.run(main.connect_joycon(device, 'Left', '001122334455'))
        finally:
            main.BleakClient = old_client
            main.get_controller_manager = old_manager

        self.assertFalse(result)
        self.assertTrue(FakeClient.instance.disconnected)
        self.assertEqual(manager.removed, ['001122334455'])

    def test_dsu_setting_preserves_other_sections(self):
        with tempfile.NamedTemporaryFile(suffix='.ini', delete=False) as tmp:
            path = tmp.name
        try:
            parser = configparser.ConfigParser()
            parser['Controller'] = {'enable_dsu': '0', 'orientation': '1'}
            parser['Bluetooth'] = {'mac_address': 'AABBCCDDEEFF'}
            parser['Pair_2'] = {'sll_mapping': 'XUSB_GAMEPAD_A'}
            with open(path, 'w', encoding='utf-8') as stream:
                parser.write(stream)

            persist_dsu_setting(True, path)
            result = configparser.ConfigParser()
            result.read(path, encoding='utf-8')
            self.assertEqual(result['Controller']['enable_dsu'], '1')
            self.assertEqual(result['Controller']['orientation'], '1')
            self.assertEqual(result['Bluetooth']['mac_address'], 'AABBCCDDEEFF')
            self.assertEqual(result['Pair_2']['sll_mapping'], 'XUSB_GAMEPAD_A')
        finally:
            import os
            os.unlink(path)


if __name__ == '__main__':
    unittest.main()
