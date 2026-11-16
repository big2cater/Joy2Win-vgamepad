# -*- coding: utf-8 -*-
"""Shared mouse helpers for the duo and single Joy-Con modes.

Three things live here because both modes need them and had drifted apart:

* ``scroll_notches`` -- wheel conversion. ``scroll_decoder`` reports a signed
  axis in -32767..32767 per input report, and the original consumer did
  ``int(value / 32768)``, which truncates every value in that range to 0 (only
  an exact -32768 became -1), so the wheel never turned in either mode.
* ``mouse_divisor`` -- pointer speed, driven by ``mouse_sensitivity``.
* ``surface_threshold`` -- lift-off distance, driven by
  ``mouse_surface_threshold``.
"""

from config import Config

# One notch per this much accumulated tilt. At ~60 reports/s a full tilt gives
# roughly 15 notches/s, which feels like a fast wheel flick.
SCROLL_NOTCH = 131072

# Defaults used when config.ini is missing or holds an unusable value.
DEFAULT_SENSITIVITY = 100
DEFAULT_SURFACE_THRESHOLD = 512


def scroll_notches(state, accumulator_key, value):
    """Return whole wheel notches for one report, carrying the remainder."""
    state[accumulator_key] = state.get(accumulator_key, 0) + value
    notches = int(state[accumulator_key] / SCROLL_NOTCH)
    if notches:
        state[accumulator_key] -= notches * SCROLL_NOTCH
    return notches


def mouse_divisor():
    """Accumulated motion units consumed per 6 ms tick.

    Sensitivity 100 reproduces the original 6-frame smoothing so existing
    installs feel identical; 200 halves the divisor (twice as fast), 50 doubles
    it (half speed).
    """
    try:
        sensitivity = int(Config().mouse_sensitivity)
    except Exception:
        sensitivity = DEFAULT_SENSITIVITY
    sensitivity = max(10, min(400, sensitivity))
    return 6.0 * 100.0 / sensitivity


def surface_threshold():
    """Lift-off distance for automatic mouse mode, from config.ini."""
    try:
        value = int(Config().mouse_surface_threshold)
    except Exception:
        value = DEFAULT_SURFACE_THRESHOLD
    return max(8, min(4095, value))

