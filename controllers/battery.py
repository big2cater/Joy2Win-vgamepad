"""Joy-Con 2 battery helpers.

The 0-9 state-of-charge value in the power-info byte of report 0x07/0x08 is
authoritative. This module is only a fallback for controllers where that
report never arrives.

Input report 0x05 carries the battery voltage at offset 0x1F, but that reading
is roughly 0.6 V *below* the real cell voltage (community measurements:
~3.30 V reported = 75% on the console, ~3.60 V reported = 100%). The old
standard Li-ion curve (3.3 V = 0%, 4.2 V = 100%) therefore reported a full
Joy-Con as 5..20% -- see jacc/joy2con issue #1 on firmware 2.1.9.

The anchors below are the Nintendo Joy-Con thresholds (3.3 / 3.6 / 3.9 /
4.2 V) shifted down by 0.6 V. This is an estimate, not a fuel gauge.
"""

_VOLTAGE_CURVE = (
    (2700, 0),
    (3000, 10),
    (3300, 75),
    (3600, 100),
)


def battery_percentage_from_voltage(voltage_mv: int):
    """Convert a reported Joy-Con 2 voltage to an estimated 0-100 percent."""
    if not isinstance(voltage_mv, int) or not 2400 <= voltage_mv <= 4200:
        return None

    if voltage_mv <= _VOLTAGE_CURVE[0][0]:
        return 0
    if voltage_mv >= _VOLTAGE_CURVE[-1][0]:
        return 100

    for (low_mv, low_pct), (high_mv, high_pct) in zip(
        _VOLTAGE_CURVE, _VOLTAGE_CURVE[1:]
    ):
        if voltage_mv <= high_mv:
            fraction = (voltage_mv - low_mv) / (high_mv - low_mv)
            return round(low_pct + fraction * (high_pct - low_pct))

    return None
