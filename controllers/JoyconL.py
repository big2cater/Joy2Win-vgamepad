import sys
import struct

from controllers.stick_calibration import (
    StickCalibrator,
    normalized_pair,
    signed_pair,
)


class JoyConLeft:
    def __init__(self):
        self.name = "Joy-Con"
        self.side = "Left"
        self.orientation = 0  # Default orientation is vertical
        self.mac_address = ""

        self.buttons = {
            # these buttons are mapped to upright usage (invert for sideways)
            "ZL": False,
            "L": False,
            "Minus": False,
            "SLL": False,
            "SRL": False,
            "Left": False,
            "Down": False,
            "Up": False,
            "Right": False,
            "L3": False,
            "Capture": False,
        }
        self.analog_stick = {"X": 0, "Y": 0}

        self.accelerometer = {"X": 0.0, "Y": 0.0, "Z": 0.0}
        self.gyroscope = {"X": 0.0, "Y": 0.0, "Z": 0.0}  # Pitch / Roll / Yaw

        self.mouse = {"X": 0.0, "Y": 0.0, "distance": "0C", "distance_raw": 0xFFFF}

        self.mouseBtn = {
            "Left": False,
            "Right": False,
            "scrollX": 0.0,
            "scrollY": 0.0,
        }

        self.timestamp = bytes.fromhex("00000000")
        # Motion timestamp is an unsigned 32-bit microsecond counter.
        self.motionTimestamp = 0
        # Battery data from input report 0x05 (offsets 0x1F / 0x21).
        self.battery_voltage_mv = None
        self.charging_state = None
        self.battery_level = None
        self.is_connected = False

        # One calibrator per physical stick: rest positions differ per unit.
        self.stick_calibrator = StickCalibrator()

    async def update(self, datas):
        # Button/stick/mouse fields end at byte 23. IMU fields are optional
        # and occupy the final 18 bytes of the 63-byte report 0x05.
        if len(datas) < 24:
            print(f"[WARNING] Data too short: {len(datas)} bytes (expected at least 24)")
            return

        btnDatas = datas[5] << 8 | datas[6]
        JoystickDatas = datas[10:13]
        mouseDatas = datas[16:24]

        self.mouse["X"], self.mouse["Y"] = struct.unpack("<hh", mouseDatas[:4])
        # Report 0x05 offset 0x16 is a little-endian uint16 lift-off distance:
        # ~117-158 while on a surface, ~3083-3321 when lifted (community
        # measurements). Keeping the legacy hex string for compatibility while
        # exposing the numeric value for a robust surface test.
        self.mouse["distance_raw"] = struct.unpack_from("<H", mouseDatas, 6)[0]
        self.mouse["distance"] = mouseDatas[7:8].hex()

        self.timestamp = bytes.fromhex(datas[0:4].hex())

        if len(datas) >= 0x22:
            self.battery_voltage_mv = int.from_bytes(datas[0x1F:0x21], "little")
            self.charging_state = datas[0x21]

        if len(datas) >= 0x3C:
            # "<i" wrapped negative after ~35 minutes and DSU then turned it
            # into a huge 64-bit timestamp. The field is an unsigned counter.
            self.motionTimestamp = struct.unpack("<I", datas[0x2A:0x2E])[0]
            accel_x_raw, accel_y_raw, accel_z_raw = struct.unpack("<3h", datas[0x30:0x36])
            gyro_x_raw, gyro_y_raw, gyro_z_raw = struct.unpack("<3h", datas[0x36:0x3C])

            # ndeadly/switch2_controller_research, hid_reports.md (2026-09-08):
            # default FSR is +/-8 G (8.0/32767 G/LSB) and +/-2000 dps
            # (2000.0/32767 dps/LSB).
            accel_factor = 8.0 / 32767.0
            gyro_factor = 2000.0 / 32767.0

            # NOTE: this axis remap is shared with JoyConRight. Physical
            # orientation differs between the two halves; SDL uses separate
            # transforms. Needs a hardware pass before changing.
            self.accelerometer["X"] = -accel_x_raw * accel_factor
            self.accelerometer["Y"] = -accel_z_raw * accel_factor
            self.accelerometer["Z"] = accel_y_raw * accel_factor

            self.gyroscope["X"] = gyro_x_raw * gyro_factor
            self.gyroscope["Y"] = -gyro_z_raw * gyro_factor
            self.gyroscope["Z"] = gyro_y_raw * gyro_factor

        self.buttons["SLL"] = bool(btnDatas & 0x0020)
        self.buttons["SRL"] = bool(btnDatas & 0x0010)
        self.buttons["Minus"] = bool(btnDatas & 0x0100)
        self.buttons["L"] = bool(btnDatas & 0x0040)
        self.buttons["ZL"] = bool(btnDatas & 0x0080)
        self.buttons["Left"] = bool(btnDatas & 0x0008)
        self.buttons["Down"] = bool(btnDatas & 0x0001)
        self.buttons["Up"] = bool(btnDatas & 0x0002)
        self.buttons["Right"] = bool(btnDatas & 0x0004)
        self.buttons["L3"] = bool(btnDatas & 0x0800)
        self.buttons["Capture"] = bool(btnDatas & 0x2000)

        self.analog_stick["X"], self.analog_stick["Y"] = joystick_decoder(
            JoystickDatas, self.orientation, self.stick_calibrator
        )

        self.mouseBtn["Left"] = bool(btnDatas & 0x0040)  # L
        self.mouseBtn["Right"] = bool(btnDatas & 0x0080)  # ZL
        self.mouseBtn["scrollX"], self.mouseBtn["scrollY"] = scroll_decoder(
            JoystickDatas, self.stick_calibrator
        )

        self.is_connected = True

    def print_status(self, datas):
        sys.stdout.write(f"\033[2;0H")
        print(f"JoyCon Left Status:")
        print(f"  Buttons: {self.buttons}                    ")
        print(f"  Analog Stick: {self.analog_stick}                    ")
        print(f"  Battery Level: {self.battery_level}%                    ")
        print(f"  Connected: {self.is_connected}                    ")

    def setMacAddress(self, mac_address):
        self.mac_address = mac_address


# Return stick values from 0 to 32768, centred on 16384.
def joystick_decoder(data, orientation, calibrator=None):
    if len(data) != 3:
        return 4096 * 4, 4096 * 4

    nx, ny = normalized_pair(data, calibrator)
    x = int(nx * 32768)
    y = int(ny * 32768)

    if orientation == 1:  # Horizontal: rotate 90 degrees counterclockwise
        x_new = 32768 - y
        y_new = x
        x, y = x_new, y_new

    return x, y


def scroll_decoder(data, calibrator=None):
    if len(data) != 3:
        return 0, 0

    sx, sy = signed_pair(data, calibrator)
    x = int(sx * 32767)
    y = int(sy * 32767)

    if -3000 < x < 3000:
        x = 0
    if -3000 < y < 3000:
        y = 0

    return x, y
