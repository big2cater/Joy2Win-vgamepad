# -*- coding: utf-8 -*-
"""Pure-logic regression tests: no vgamepad / bleak / PyQt5 required.

Run with:  python -m unittest tests.test_calibration -v
"""
import unittest

from controllers.battery import battery_percentage_from_voltage
from controllers.stick_calibration import (
    StickCalibrator,
    normalized_pair,
    signed_pair,
    unpack_stick,
)
from dsu_server import incrementIdPacket, _slot_packet_ids


def pack(x, y):
    """Build the 3-byte packed 12-bit stick frame used by report 0x05."""
    return bytes((
        x & 0xFF,
        ((x >> 8) & 0x0F) | ((y & 0x0F) << 4),
        (y >> 4) & 0xFF,
    ))


class StickCalibrationTests(unittest.TestCase):
    def test_packed_stick_roundtrip(self):
        for x, y in ((0, 0), (2080, 2157), (3400, 3360), (4095, 4095)):
            self.assertEqual(unpack_stick(pack(x, y)), (x, y))
        self.assertIsNone(unpack_stick(b"\x00\x00"))
        self.assertEqual(normalized_pair(b"\x00\x00"), (0.5, 0.5))

    def test_centre_is_learned_from_a_still_window(self):
        calibrator = StickCalibrator()
        rest = pack(2080, 2157)  # measured rest values, not the 2048 midpoint
        for _ in range(35):
            calibrator.normalized(rest)
        self.assertTrue(calibrator.frozen)
        self.assertAlmostEqual(calibrator.center_x, 2080.0)
        self.assertAlmostEqual(calibrator.center_y, 2157.0)
        nx, ny = calibrator.normalized(rest)
        self.assertAlmostEqual(nx, 0.5)
        self.assertAlmostEqual(ny, 0.5)

    def test_full_deflection_reaches_both_limits(self):
        calibrator = StickCalibrator()
        rest = pack(2080, 2157)
        for _ in range(35):
            calibrator.normalized(rest)
        high = pack(3400, 3360)
        low = pack(900, 890)
        self.assertEqual(calibrator.normalized(high), (1.0, 1.0))
        self.assertEqual(calibrator.normalized(low), (0.0, 0.0))

    def test_stick_held_at_full_deflection_is_not_learned_as_centre(self):
        calibrator = StickCalibrator()
        held = pack(3350, 3350)
        for _ in range(35):
            calibrator.normalized(held)
        self.assertFalse(calibrator.frozen)
        self.assertAlmostEqual(calibrator.center_x, 2020.0)
        self.assertAlmostEqual(calibrator.center_y, 2035.0)

    def test_spans_only_grow(self):
        calibrator = StickCalibrator()
        calibrator.normalized(pack(2080, 2157))
        calibrator.normalized(pack(2800, 2800))
        span = calibrator.span_x_pos
        calibrator.normalized(pack(2080, 2157))
        self.assertGreaterEqual(calibrator.span_x_pos, span)

    def test_legacy_fallback_and_signed_output(self):
        frame = pack(2020, 2035)
        nx, ny = normalized_pair(frame)
        self.assertAlmostEqual(nx, (2020 - 780) / (3260 - 780), places=5)
        self.assertAlmostEqual(ny, (2035 - 820) / (3250 - 820), places=5)
        sx, sy = signed_pair(frame)
        self.assertAlmostEqual(sx, nx * 2 - 1)
        self.assertAlmostEqual(sy, ny * 2 - 1)


class BatteryCurveTests(unittest.TestCase):
    def test_full_controller_is_not_reported_as_empty(self):
        # jacc/joy2con issue #1: firmware 2.1.9, console shows full,
        # raw readings 3631 mV / 3460 mV were shown as 14% / 5%.
        self.assertEqual(battery_percentage_from_voltage(3631), 100)
        self.assertGreaterEqual(battery_percentage_from_voltage(3460), 80)

    def test_curve_anchors_and_invalid_values(self):
        self.assertEqual(battery_percentage_from_voltage(2700), 0)
        self.assertEqual(battery_percentage_from_voltage(3300), 75)
        self.assertEqual(battery_percentage_from_voltage(3600), 100)
        self.assertIsNone(battery_percentage_from_voltage(0))
        self.assertIsNone(battery_percentage_from_voltage(5000))
        self.assertIsNone(battery_percentage_from_voltage(None))


class DsuPacketIdTests(unittest.TestCase):
    def test_packet_ids_are_independent_per_slot(self):
        _slot_packet_ids[:] = [0] * len(_slot_packet_ids)
        self.assertEqual(incrementIdPacket(2), 1)
        self.assertEqual(incrementIdPacket(3), 1)
        self.assertEqual(incrementIdPacket(2), 2)
        self.assertEqual(incrementIdPacket(2), 3)


if __name__ == "__main__":
    unittest.main()
