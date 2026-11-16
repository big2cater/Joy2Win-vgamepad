# -*- coding: utf-8 -*-
"""Joy-Con 2 HD Rumble BLE output encoding. Pure module, no third-party deps.

The previous implementation wrote firmware *stored effects* (a fixed ~1 s
buzz, sample 0x01) to the command characteristic, with a stop frame whose
second byte was 0x00 instead of 0x91 -- i.e. not a valid command at all.
This module builds the real LRA output report instead.

Sources:
  - ndeadly/switch2_controller_research: hid_reports.md (output report 0x01),
    bluetooth_interface.md (GATT characteristic table).
  - JoeGeC/joycon2android docs/protocol.md: BLE packet layout, 12 ms cadence,
    amplitude cap (~44% = 0x1C4). Its ~20% (0x060) figure is a *user-facing
    strength setting*, not the protocol ceiling -- using it as the default made
    the default buzz far weaker than every other implementation.
  - SDL 3.4.20 src/joystick/hidapi/SDL_hidapi_switch2.c: EncodeHDRumble(),
    frequency codes 0x187 / 0x112, RUMBLE_INTERVAL 12, RUMBLE_MAX 29000.
  - DS4Windows Switch 2 codec notes: 40-bit subframe field layout, and the
    fill-forward rule (repeat one sustained state in all three subframes).

Note: this is scalar-to-waveform *synthesis*, not pass-through of a game's
original HD Rumble waveform. XInput / SDL rumble only deliver two motor
intensities; frequency, left/right position and the temporal envelope are
already lost upstream in every emulator.
"""

# Vibration (HD Rumble) GATT characteristics, write without response.
UUID_RUMBLE_LEFT = "289326cb-a471-485d-a8f4-240c14f18241"
UUID_RUMBLE_RIGHT = "fa19b0fb-cd1f-46a7-84a1-bbb09e00c149"

# Frequency codes used by SDL's Switch 2 driver. jacc/joy2con derives the same
# two codes from 320 Hz / 160 Hz (freq_code(): 0x112 + 117*log2(hz/160)) and
# keeps them while stopping -- its Rumbler sends (0x187, 0, 0x112, 0) as the
# final packet. Stopping is amplitude-only on Joy-Con 2; do not substitute the
# neutral carrier codes used by the *Pro Controller 2* implementations.
FREQ_HIGH = 0x187
FREQ_LOW = 0x112

# Resend period while either motor is on.
#
# 12 ms (SDL's value) exists for *waveform pass-through*: consecutive packets
# reconstruct a changing HD Rumble envelope. This project synthesises from two
# XInput scalars, so the envelope is constant -- one packet holds that state
# until the next arrives, and 30 ms maintains it just as well.
#
# It also has to fit the link. Measured on a throughput-optimised Windows BLE
# connection: a write returns in ~0.7 ms but the real limit is one packet per
# connection event, which showed up as 16 ms stalls and a hard ceiling of
# ~44 fps. Pacing at 12 ms could never be met, so the queue stayed full and the
# zero-amplitude stop packet waited behind it -- the "rumble off but still
# buzzing" symptom. 30 ms sits below that ceiling, so the queue stays empty and
# a stop takes effect on the next event.
RUMBLE_INTERVAL = 0.030
# No update for this long -> send a zero-amplitude packet and stop the stream.
# Kept short on purpose: a game that stops sending rumble must not leave the
# actuator buzzing.
RUMBLE_IDLE_TIMEOUT = 1.5

# 10-bit packed amplitude. Full scale (0x3FF) is strong enough to hurt; the
# Linux kernel driver caps at 450/1024 and notes the actuator can be damaged.
# Every reference implementation lands on the same ceiling:
#   jacc/joy2con   RUMBLE_MAX = 450
#   JoeGeC         SAFE_AMPLITUDE = 0x3FF * 29000 / 65535 ~= 452
#   SDL            RUMBLE_MAX = 29000 of 65535 -> ~452
# The previous default of 0x060 (96, ~9%) was far below all of them: at that
# level the buzz is barely perceptible and its on/off transition is too small
# to read as a stop, which is what "it keeps rumbling" felt like.
AMPLITUDE_DEFAULT = 0x1C4
AMPLITUDE_SDL_MAX = 0x1C4
AMPLITUDE_BALANCED = 0x1F4
AMPLITUDE_HARD_MAX = 0x3FF
MOTOR_MAX = 255

GROUP_HEADER = 0x50
SUBFRAME_COUNT = 3
REPORT_ID_BLE = 0x00

# jacc/joy2con (Linux, raw L2CAP/ATT) pads every rumble packet with zeros to 42
# bytes before a Write Command. The meaningful payload is only 17 bytes, so the
# padding is not data -- but matching the observed-on-hardware length avoids
# firmware handling short write commands differently. Capped at MTU-3 at runtime.
RUMBLE_PACKET_LENGTH = 42

# Fallback stored effects. Sample 0x00 = silence / stop a playing sample.
# The old stop frame ("0a0000...") had 0x00 where the 0x91 request marker
# belongs and was not a legal command.
LEGACY_EFFECT_ON = bytes.fromhex("0A9101020004000001000000")
LEGACY_EFFECT_OFF = bytes.fromhex("0A9101020004000000000000")


def get_rumble_uuid(side):
    if side == "Left":
        return UUID_RUMBLE_LEFT
    if side == "Right":
        return UUID_RUMBLE_RIGHT
    raise ValueError(f"Unknown Joy-Con side: {side}")


def amplitude_from_intensity(intensity, ceiling=AMPLITUDE_DEFAULT, strength=100):
    """Map an XInput motor intensity (0..255) to a 10-bit LRA amplitude."""
    if intensity is None:
        return 0
    value = max(0, min(MOTOR_MAX, int(intensity)))
    scale = max(0, min(100, int(strength))) / 100.0
    ceiling = max(0, min(AMPLITUDE_HARD_MAX, int(ceiling)))
    return max(0, min(AMPLITUDE_HARD_MAX, int(round(value / MOTOR_MAX * ceiling * scale))))


def encode_subframe(hi_freq=FREQ_HIGH, hi_amp=0, lo_freq=FREQ_LOW, lo_amp=0):
    """Pack one 40-bit little-endian subframe into 5 bytes.

    Bit layout (SDL / DS4Windows codec):
      bits  0.. 9  oscillator 0 control code (high frequency)
      bits 10..19  oscillator 0 amplitude
      bits 20..29  oscillator 1 control code (low frequency)
      bits 30..39  oscillator 1 amplitude
    """
    value = (
        (hi_freq & 0x3FF)
        | ((hi_amp & 0x3FF) << 10)
        | ((lo_freq & 0x3FF) << 20)
        | ((lo_amp & 0x3FF) << 30)
    )
    return value.to_bytes(5, "little")


def encode_group(counter, hi_amp, lo_amp, hi_freq=FREQ_HIGH, lo_freq=FREQ_LOW):
    """Build a 16-byte actuator group: header + three subframes.

    A source that only has one sustained motor state repeats that state in
    all three subframes (SDL / Switch2Connect fill-forward behaviour), rather
    than turning a continuous rumble into a single 4 ms pulse.
    """
    subframe = encode_subframe(hi_freq, hi_amp, lo_freq, lo_amp)
    return bytes((GROUP_HEADER | (counter & 0x0F),)) + subframe * SUBFRAME_COUNT


def build_frame(counter, large_motor, small_motor,
                ceiling=AMPLITUDE_DEFAULT, strength=100):
    """Build a 17-byte BLE output packet from the two XInput motor values.

    XInput: large motor = low frequency, small motor = high frequency.
    With both motors at 0 this is also the stop packet (0x187/0x112 carriers,
    zero amplitude), which is what joy2con sends to silence a Joy-Con 2.
    """
    hi_amp = amplitude_from_intensity(small_motor, ceiling, strength)
    lo_amp = amplitude_from_intensity(large_motor, ceiling, strength)
    return bytes((REPORT_ID_BLE,)) + encode_group(counter, hi_amp, lo_amp)
