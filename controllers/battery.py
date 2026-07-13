"""Joy-Con 2 battery helpers."""


# Approximate Li-ion discharge curve. Joy-Con 2 report 0x05 exposes battery
# voltage in millivolts, but does not expose the 0-9 state-of-charge value used
# by the alternate 0x07/0x08 report. Interpolation is substantially more useful
# than treating the 12-bit millivolt value as a raw percentage.
_VOLTAGE_CURVE = (
    (3300, 0),
    (3450, 5),
    (3550, 10),
    (3650, 25),
    (3750, 45),
    (3850, 65),
    (3950, 82),
    (4050, 93),
    (4150, 98),
    (4200, 100),
)


def battery_percentage_from_voltage(voltage_mv: int):
    """Convert a plausible Joy-Con 2 battery voltage to 0-100 percent."""
    if not 2500 <= voltage_mv <= 5000:
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
