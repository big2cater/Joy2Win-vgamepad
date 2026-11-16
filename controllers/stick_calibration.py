# -*- coding: utf-8 -*-
"""Adaptive calibration for Joy-Con 2 analog sticks.

The packed 12-bit stick values are neither centred on 2048 nor do they span
0x000..0xFFF. Rest position and travel differ per controller and per axis
(community measurements: rest around 2000..2160, full travel roughly
900..3400), so the fixed 780/3260 and 820/3250 constants left a permanent
offset at rest and clipped full deflection.

This follows the community approach used by joycon2android's StickCalibrator:
learn the centre from an early *still* window, then widen each of the four
directional spans independently. Spans only ever grow, so full deflection
works from the first packets and improves as the stick is exercised.

No third-party imports: this module is deliberately pure so it can be unit
tested without vgamepad, bleak or PyQt5 installed.
"""

import threading

# Seeds are just below the smallest measured travel. They let the very first
# packets reach close to full deflection before any learning has happened.
SEED_CENTER_X = 2020.0
SEED_CENTER_Y = 2035.0
SEED_SPAN = 1180.0
MIN_SPAN = 900.0
MAX_SPAN = 1900.0

STILL_WINDOW = 30
STILL_TOLERANCE = 60          # max spread (LSB) inside a still window
CENTER_TOLERANCE = 350        # a still window far from the seed is a held stick
MAX_UNFROZEN_FRAMES = 400     # ~6 s at 66 Hz, then force a fallback freeze


def unpack_stick(data):
    """Decode the packed 12-bit X/Y pair, or return None for a short frame."""
    if data is None or len(data) != 3:
        return None
    x = ((data[1] & 0x0F) << 8) | data[0]
    y = (data[2] << 4) | ((data[1] & 0xF0) >> 4)
    return x, y


class StickCalibrator:
    """Per-controller, per-stick calibration state."""

    def __init__(self, seed_center_x=SEED_CENTER_X, seed_center_y=SEED_CENTER_Y,
                 seed_span=SEED_SPAN):
        self._lock = threading.RLock()
        self._seed_center_x = float(seed_center_x)
        self._seed_center_y = float(seed_center_y)
        self.reset(seed_span)

    def reset(self, seed_span=SEED_SPAN):
        with self._lock:
            self.center_x = self._seed_center_x
            self.center_y = self._seed_center_y
            span = min(MAX_SPAN, max(MIN_SPAN, float(seed_span)))
            self.span_x_pos = span
            self.span_x_neg = span
            self.span_y_pos = span
            self.span_y_neg = span
            self._samples = []
            self._frames = 0
            self.frozen = False

    def _observe(self, x, y):
        """Learn the centre and widen directional spans. Spans never shrink."""
        with self._lock:
            if not self.frozen:
                self._frames += 1
                self._samples.append((x, y))
                if len(self._samples) >= STILL_WINDOW:
                    xs = [sample[0] for sample in self._samples]
                    ys = [sample[1] for sample in self._samples]
                    cx = sum(xs) / len(xs)
                    cy = sum(ys) / len(ys)
                    still = (max(xs) - min(xs) <= STILL_TOLERANCE
                             and max(ys) - min(ys) <= STILL_TOLERANCE)
                    # A stick held at full deflection is perfectly still too.
                    # Reject such a window rather than learning a wrong centre.
                    plausible = (abs(cx - self._seed_center_x) <= CENTER_TOLERANCE
                                 and abs(cy - self._seed_center_y) <= CENTER_TOLERANCE)
                    if still and plausible:
                        self.center_x = cx
                        self.center_y = cy
                        self.frozen = True
                        self._samples = []
                    else:
                        # Keep half the window so a still period spanning two
                        # windows is still detectable.
                        self._samples = self._samples[-STILL_WINDOW // 2:]
                if self._frames >= MAX_UNFROZEN_FRAMES:
                    # Never leave a controller permanently uncalibrated just
                    # because it was moving during startup.
                    self.frozen = True
                    self._samples = []

            dx = x - self.center_x
            dy = y - self.center_y
            if dx >= 0:
                self.span_x_pos = min(MAX_SPAN, max(self.span_x_pos, dx))
            else:
                self.span_x_neg = min(MAX_SPAN, max(self.span_x_neg, -dx))
            if dy >= 0:
                self.span_y_pos = min(MAX_SPAN, max(self.span_y_pos, dy))
            else:
                self.span_y_neg = min(MAX_SPAN, max(self.span_y_neg, -dy))

    def normalized(self, data):
        """Return (x, y) in 0.0..1.0 with a learned 0.5 rest position."""
        raw = unpack_stick(data)
        if raw is None:
            return 0.5, 0.5
        x, y = raw
        self._observe(x, y)
        dx = x - self.center_x
        dy = y - self.center_y
        sx = self.span_x_pos if dx >= 0 else self.span_x_neg
        sy = self.span_y_pos if dy >= 0 else self.span_y_neg
        nx = 0.5 + dx / (2.0 * sx)
        ny = 0.5 + dy / (2.0 * sy)
        return min(1.0, max(0.0, nx)), min(1.0, max(0.0, ny))

    def signed(self, data):
        """Return (x, y) in -1.0..1.0, for scroll/mouse style consumers."""
        nx, ny = self.normalized(data)
        return nx * 2.0 - 1.0, ny * 2.0 - 1.0


# Legacy fixed range, kept as a fallback for callers that do not own a
# StickCalibrator instance (e.g. older scripts importing joystick_decoder).
LEGACY_X_MIN, LEGACY_X_MAX = 780.0, 3260.0
LEGACY_Y_MIN, LEGACY_Y_MAX = 820.0, 3250.0


def normalized_pair(data, calibrator=None):
    """Return (x, y) in 0.0..1.0 for a packed stick frame."""
    if unpack_stick(data) is None:
        return 0.5, 0.5
    if calibrator is not None:
        return calibrator.normalized(data)
    x, y = unpack_stick(data)
    nx = min(1.0, max(0.0, (x - LEGACY_X_MIN) / (LEGACY_X_MAX - LEGACY_X_MIN)))
    ny = min(1.0, max(0.0, (y - LEGACY_Y_MIN) / (LEGACY_Y_MAX - LEGACY_Y_MIN)))
    return nx, ny


def signed_pair(data, calibrator=None):
    """Return (x, y) in -1.0..1.0 for a packed stick frame."""
    nx, ny = normalized_pair(data, calibrator)
    return nx * 2.0 - 1.0, ny * 2.0 - 1.0
