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
from controller_manager import ControllerManager
from controllers.battery import battery_percentage_from_voltage
from gui import ControllerPairTab, persist_dsu_setting


class FakeCommandClient:
    def __init__(self, respond=False, response_status=0x01):
        self.respond = respond
        self.response_status = response_status
        self.writes = 0

    async def write_gatt_char(self, uuid, data):
        self.writes += 1
        if self.respond:
            response = bytes((data[0], self.response_status, data[2], data[3]))
            asyncio.get_running_loop().call_soon(
                controller_command.ControllerCommand().receive_response,
                self,
                response,
            )


class CoreRegressionTests(unittest.TestCase):
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
        self.assertEqual(battery_percentage_from_voltage(3300), 0)
        self.assertEqual(battery_percentage_from_voltage(3750), 45)
        self.assertEqual(battery_percentage_from_voltage(4200), 100)
        self.assertIsNone(battery_percentage_from_voltage(0))

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
