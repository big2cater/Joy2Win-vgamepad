# -*- coding: utf-8 -*-
"""HD Rumble encoding + stream tests. No vgamepad / bleak / PyQt5 required.

Run with:  python -m unittest tests.test_rumble -v
"""
import asyncio
import types
import unittest

from controller_command import UUID_CMD
from controllers.hd_rumble import (
    AMPLITUDE_DEFAULT,
    AMPLITUDE_HARD_MAX,
    FREQ_HIGH,
    FREQ_LOW,
    LEGACY_EFFECT_OFF,
    LEGACY_EFFECT_ON,
    RUMBLE_PACKET_LENGTH,
    UUID_RUMBLE_LEFT,
    UUID_RUMBLE_RIGHT,
    amplitude_from_intensity,
    build_frame,
    encode_group,
    encode_subframe,
    get_rumble_uuid,
)
from control_type.rumble_stream import STOP_REPEAT, RumbleStream


def sdl_reference_encode(hi_freq, hi_amp16, lo_freq, lo_amp16):
    """SDL 3.4.20 EncodeHDRumble() byte packing (zlib reference)."""
    return bytes((
        hi_freq & 0xFF,
        ((hi_amp16 >> 4) & 0xFC) | ((hi_freq >> 8) & 0x03),
        ((hi_amp16 >> 12) | (lo_freq << 4)) & 0xFF,
        (lo_amp16 & 0xC0) | ((lo_freq >> 4) & 0x3F),
        (lo_amp16 >> 8) & 0xFF,
    ))


class EncodingTests(unittest.TestCase):
    def test_stop_packet_keeps_the_carrier_frequencies(self):
        """joy-con 2 stops on zero amplitude alone; the carriers stay 0x187 /
        0x112. (The neutral-carrier frame belongs to the Pro Controller 2.)"""
        frame = build_frame(0, 0, 0)
        value = int.from_bytes(frame[2:7], "little")
        self.assertEqual(value & 0x3FF, FREQ_HIGH)
        self.assertEqual((value >> 10) & 0x3FF, 0)
        self.assertEqual((value >> 20) & 0x3FF, FREQ_LOW)
        self.assertEqual((value >> 30) & 0x3FF, 0)

    def test_subframe_40bit_field_layout(self):
        hi_freq, hi_amp, lo_freq, lo_amp = FREQ_HIGH, 0x123, FREQ_LOW, 0x0AB
        raw = encode_subframe(hi_freq, hi_amp, lo_freq, lo_amp)
        self.assertEqual(len(raw), 5)
        value = int.from_bytes(raw, "little")
        self.assertEqual(value & 0x3FF, hi_freq)
        self.assertEqual((value >> 10) & 0x3FF, hi_amp)
        self.assertEqual((value >> 20) & 0x3FF, lo_freq)
        self.assertEqual((value >> 30) & 0x3FF, lo_amp)

    def test_subframe_matches_sdl_byte_packing(self):
        hi_amp, lo_amp = 0x123, 0x0AB
        self.assertEqual(
            encode_subframe(FREQ_HIGH, hi_amp, FREQ_LOW, lo_amp),
            sdl_reference_encode(FREQ_HIGH, hi_amp << 6, FREQ_LOW, lo_amp << 6),
        )

    def test_group_is_16_bytes_with_three_repeated_subframes(self):
        group = encode_group(7, 0x060, 0x030)
        self.assertEqual(len(group), 16)
        self.assertEqual(group[0], 0x50 | 7)
        self.assertEqual(group[1:6], group[6:11])
        self.assertEqual(group[6:11], group[11:16])
        # Counter only uses the low nibble.
        self.assertEqual(encode_group(0x1F, 0, 0)[0], 0x5F)

    def test_ble_frame_shape_and_zero_amplitude_stop(self):
        frame = build_frame(3, 255, 128)
        self.assertEqual(len(frame), 17)
        self.assertEqual(frame[0], 0x00)
        self.assertEqual(frame[1] & 0xF0, 0x50)

        zero = build_frame(4, 0, 0)
        value = int.from_bytes(zero[2:7], "little")
        self.assertEqual((value >> 10) & 0x3FF, 0)
        self.assertEqual((value >> 30) & 0x3FF, 0)
        # Frequency codes remain so the packet is still a valid stop frame.
        self.assertEqual(value & 0x3FF, FREQ_HIGH)

    def test_amplitude_scaling_and_clamping(self):
        self.assertEqual(amplitude_from_intensity(0), 0)
        self.assertEqual(amplitude_from_intensity(255), AMPLITUDE_DEFAULT)
        self.assertEqual(amplitude_from_intensity(999), AMPLITUDE_DEFAULT)
        self.assertLess(amplitude_from_intensity(64), amplitude_from_intensity(200))
        self.assertEqual(amplitude_from_intensity(255, strength=0), 0)
        self.assertEqual(amplitude_from_intensity(255, strength=50),
                         AMPLITUDE_DEFAULT // 2)
        self.assertLessEqual(amplitude_from_intensity(255, ceiling=99999),
                             AMPLITUDE_HARD_MAX)
        self.assertEqual(amplitude_from_intensity(None), 0)

    def test_side_uuids_and_legacy_frames(self):
        self.assertEqual(get_rumble_uuid("Left"), UUID_RUMBLE_LEFT)
        self.assertEqual(get_rumble_uuid("Right"), UUID_RUMBLE_RIGHT)
        with self.assertRaises(ValueError):
            get_rumble_uuid("Middle")
        # The old stop frame ("0a0000...") was not a legal command.
        self.assertEqual(len(LEGACY_EFFECT_OFF), 12)
        self.assertEqual(LEGACY_EFFECT_OFF[1], 0x91)
        self.assertEqual(LEGACY_EFFECT_OFF[8], 0x00)
        self.assertNotEqual(LEGACY_EFFECT_ON, LEGACY_EFFECT_OFF)


class _FakeServices:
    """Minimal GATT service table: every characteristic has the same props."""

    def __init__(self, properties):
        self._properties = list(properties)

    def get_characteristic(self, uuid):
        return types.SimpleNamespace(properties=self._properties)


class FakeClient:
    def __init__(self, failing=False, fail_limit=None,
                 properties=("write-without-response", "write"), mtu_size=247):
        self.is_connected = True
        self.writes = []
        self.write_modes = []
        # Windows negotiates a large MTU; small-MTU behaviour is covered by the
        # padding test passing mtu_size explicitly.
        self.mtu_size = mtu_size
        self.services = _FakeServices(properties)
        self.failing = failing
        # fail_limit=None means "fail forever while failing=True"; an integer
        # makes only the first N attempts fail, to model a transient error.
        self.fail_limit = fail_limit
        self.attempts = 0

    async def write_gatt_char(self, uuid, data, response=None):
        self.writes.append((uuid, data))
        self.write_modes.append(response)
        self.attempts += 1
        if self.fail_limit is not None:
            should_fail = self.attempts <= self.fail_limit
        else:
            should_fail = self.failing
        if should_fail:
            raise OSError("GATT write failed")


class StreamTests(unittest.TestCase):
    def test_stream_sends_frames_and_stops_cleanly(self):
        async def scenario():
            client = FakeClient()
            stream = RumbleStream(interval=0.005, idle_timeout=0.5)
            await stream.update(0, "Left", client, 200, 100)
            await asyncio.sleep(0.035)
            await stream.update(0, "Left", client, 0, 0)
            await asyncio.sleep(0.02)
            await stream.shutdown()
            return client.writes

        writes = asyncio.run(scenario())
        self.assertGreaterEqual(len(writes), 3)
        self.assertTrue(all(uuid == UUID_RUMBLE_LEFT for uuid, _ in writes))
        # Packets are padded to the length real implementations send, so only
        # the meaningful 17-byte prefix is structural.
        self.assertTrue(all(len(data) >= 17 and data[0] == 0 for _, data in writes))
        counters = [data[1] & 0x0F for _, data in writes]
        self.assertEqual((counters[1] - counters[0]) % 16, 1)
        last = writes[-1][1]
        value = int.from_bytes(last[2:7], "little")
        self.assertEqual((value >> 10) & 0x3FF, 0)
        self.assertEqual((value >> 30) & 0x3FF, 0)

    def test_idle_timeout_sends_stop_without_an_explicit_zero(self):
        async def scenario():
            client = FakeClient()
            stream = RumbleStream(interval=0.005, idle_timeout=0.02)
            await stream.update(0, "Right", client, 255, 0)
            await asyncio.sleep(0.06)
            await stream.shutdown()
            return client.writes

        writes = asyncio.run(scenario())
        self.assertTrue(all(uuid == UUID_RUMBLE_RIGHT for uuid, _ in writes))
        last = writes[-1][1]
        value = int.from_bytes(last[2:7], "little")
        self.assertEqual((value >> 10) & 0x3FF, 0)

    def test_repeated_zero_updates_do_not_restart_the_stream(self):
        async def scenario():
            client = FakeClient()
            stream = RumbleStream(interval=0.005, idle_timeout=1.0)
            await stream.update(0, "Left", client, 0, 0)
            # Let the stop burst finish before measuring, otherwise the
            # still-running burst is counted as "new" traffic.
            await asyncio.sleep(0.3)
            before = len(client.writes)
            for _ in range(10):
                await stream.update(0, "Left", client, 0, 0)
            await asyncio.sleep(0.05)
            after = len(client.writes)
            await stream.shutdown()
            return before, after

        before, after = asyncio.run(scenario())
        # Repeated (0, 0) updates must not restart a stream that already
        # stopped; the actuator is already quiet.
        self.assertEqual(after, before)

    def test_set_strength_updates_the_live_stream(self):
        """The GUI slider calls set_strength; it must clamp and take effect on
        the next packet without recreating the stream."""
        stream = RumbleStream(strength=100)
        stream.set_strength(40)
        self.assertEqual(stream._strength, 40)
        stream.set_strength(999)
        self.assertEqual(stream._strength, 100)
        stream.set_strength(-5)
        self.assertEqual(stream._strength, 0)

    def test_update_sync_requires_a_live_stream(self):
        """The hot path must decline when no sender is running, so the caller
        falls back to the async path that can create one."""
        stream = RumbleStream()
        self.assertFalse(stream.update_sync(0, "Left", FakeClient(), 200, 0))

    def test_update_sync_updates_targets_without_scheduling(self):
        """Regression: a loop hop per vibration callback starved the 12 ms
        sender (measured 12 fps with 0.7 ms writes)."""
        async def scenario():
            client = FakeClient()
            stream = RumbleStream(interval=0.005, idle_timeout=5.0)
            await stream.update(0, "Left", client, 200, 0)
            await asyncio.sleep(0.02)
            accepted = stream.update_sync(0, "Left", client, 120, 60)
            state = stream._states[(0, "Left")]
            targets = (state.large, state.small)
            await stream.shutdown()
            return accepted, targets

        accepted, targets = asyncio.run(scenario())
        self.assertTrue(accepted)
        self.assertEqual(targets, (120, 60))

    def test_silence_all_quiets_every_stream(self):
        """The tray menu escape hatch must stop all sides, not just one."""
        async def scenario():
            client = FakeClient()
            stream = RumbleStream(interval=0.005, idle_timeout=5.0)
            await stream.update(0, "Left", client, 200, 0)
            await stream.update(0, "Right", client, 0, 180)
            await asyncio.sleep(0.02)
            await stream.silence_all()
            return client.writes

        writes = asyncio.run(scenario())
        self.assertTrue(writes)
        # Whatever the tail is, every packet in it must be zero amplitude.
        tail = writes[-2:]
        for _, data in tail:
            value = int.from_bytes(data[2:7], "little")
            self.assertEqual((value >> 10) & 0x3FF, 0)
            self.assertEqual((value >> 30) & 0x3FF, 0)

    def test_stop_sends_a_burst_of_zero_packets(self):
        """One fire-and-forget zero packet can be lost in the BLE queue; the
        stop must be repeated or the actuator keeps running."""
        async def scenario():
            client = FakeClient()
            stream = RumbleStream(interval=0.005, idle_timeout=0.5)
            await stream.update(0, "Left", client, 200, 0)
            await asyncio.sleep(0.02)
            before = len(client.writes)
            await stream.update(0, "Left", client, 0, 0)
            await asyncio.sleep(0.3)
            await stream.shutdown()
            return client.writes[before:]

        stop_writes = asyncio.run(scenario())
        zero_frames = 0
        for _, data in stop_writes:
            if len(data) < 17 or data[0] != 0:
                continue
            value = int.from_bytes(data[2:7], "little")
            if ((value >> 10) & 0x3FF) == 0 and ((value >> 30) & 0x3FF) == 0:
                zero_frames += 1
        self.assertGreaterEqual(
            zero_frames, STOP_REPEAT,
            f"expected a burst of >= {STOP_REPEAT} zero frames, got {zero_frames}"
        )

    def test_rumble_packets_match_the_wire_length(self):
        """jacc/joy2con pads to 42 bytes; short Write Commands may be handled
        differently by the controller firmware."""
        async def scenario():
            client = FakeClient()
            stream = RumbleStream(interval=0.005, idle_timeout=0.5)
            await stream.update(0, "Left", client, 200, 0)
            await asyncio.sleep(0.02)
            await stream.shutdown()
            return client.writes

        writes = asyncio.run(scenario())
        self.assertTrue(writes)
        self.assertTrue(
            all(len(data) == RUMBLE_PACKET_LENGTH for _, data in writes),
            f"expected {RUMBLE_PACKET_LENGTH}-byte packets, "
            f"got {sorted({len(d) for _, d in writes})}",
        )

    def test_padding_respects_the_negotiated_mtu(self):
        async def scenario():
            client = FakeClient(mtu_size=23)
            stream = RumbleStream(interval=0.005, idle_timeout=0.5)
            await stream.update(0, "Left", client, 200, 0)
            await asyncio.sleep(0.02)
            await stream.shutdown()
            return client.writes

        writes = asyncio.run(scenario())
        self.assertTrue(writes)
        # MTU 23 leaves no room for the 42-byte packet, so the frame goes out
        # as encoded (17 bytes) rather than a half-padded variant.
        self.assertTrue(all(len(data) <= 20 for _, data in writes))

    def test_rumble_uses_write_without_response(self):
        """Regression: acknowledged writes cannot sustain a 12 ms cadence and
        let the stop packet queue up behind stale frames."""
        async def scenario():
            client = FakeClient()
            stream = RumbleStream(interval=0.005, idle_timeout=0.5)
            await stream.update(0, "Left", client, 200, 100)
            await asyncio.sleep(0.04)
            # Only the cadence frames matter here; the stop burst may
            # legitimately ask for an acknowledgement on its first packet.
            cadence_modes = list(client.write_modes)
            await stream.shutdown()
            return cadence_modes

        modes = asyncio.run(scenario())
        self.assertTrue(modes)
        self.assertTrue(all(mode is False for mode in modes),
                        f"expected no-response writes, got {modes}")

    def test_characteristic_with_only_write_falls_back_to_acknowledged(self):
        async def scenario():
            client = FakeClient(properties=("write",))
            stream = RumbleStream(interval=0.005, idle_timeout=0.5)
            await stream.update(0, "Right", client, 200, 0)
            await asyncio.sleep(0.02)
            await stream.shutdown()
            return client.write_modes

        modes = asyncio.run(scenario())
        self.assertTrue(modes)
        self.assertTrue(all(mode is True for mode in modes),
                        f"expected acknowledged writes, got {modes}")

    def test_write_failures_fall_back_to_stored_effect(self):
        async def scenario():
            client = FakeClient(failing=True)
            stream = RumbleStream(interval=0.005, idle_timeout=1.0)
            await stream.update(1, "Right", client, 200, 0)
            # Poll instead of sleeping a fixed 40 ms: the tick period depends
            # on how fast the fake GATT call returns, and a fixed window can
            # expire right after the third failure, before the fallback write
            # is attempted.
            loop = asyncio.get_running_loop()
            deadline = loop.time() + 2.0
            while loop.time() < deadline:
                if any(u == UUID_CMD and d == LEGACY_EFFECT_ON
                       for u, d in client.writes):
                    break
                await asyncio.sleep(0.01)
            await stream.shutdown()
            return client.writes

        writes = asyncio.run(scenario())
        self.assertTrue(any(
            uuid == UUID_CMD and data == LEGACY_EFFECT_ON
            for uuid, data in writes
        ))
        self.assertTrue(any(
            uuid == UUID_CMD and data == LEGACY_EFFECT_OFF
            for uuid, data in writes
        ))

    def test_legacy_write_is_retried_until_it_succeeds(self):
        """A transient failure on the fallback write must not silence rumble."""
        async def scenario():
            # Attempts 1-3 are HD frames (triggering the fallback), attempt 4
            # is the first legacy write and fails, attempt 5 succeeds.
            client = FakeClient(failing=True, fail_limit=4)
            stream = RumbleStream(interval=0.005, idle_timeout=2.0)
            await stream.update(2, "Left", client, 180, 0)
            loop = asyncio.get_running_loop()
            deadline = loop.time() + 2.0
            while loop.time() < deadline:
                legacy_tries = sum(
                    1 for u, d in client.writes
                    if u == UUID_CMD and d == LEGACY_EFFECT_ON
                )
                if legacy_tries >= 2:
                    break
                await asyncio.sleep(0.01)
            await stream.shutdown()
            return client.writes

        writes = asyncio.run(scenario())
        legacy_on = [
            d for u, d in writes if u == UUID_CMD and d == LEGACY_EFFECT_ON
        ]
        # First attempt failed, so a second one proves the retry happened.
        self.assertGreaterEqual(len(legacy_on), 2)


if __name__ == "__main__":
    unittest.main()
