import sys
import struct

from controllers.stick_calibration import (
    StickCalibrator,
    normalized_pair,
    signed_pair,
)


class JoyConRight:
    def __init__(self):
        self.name = "Joy-Con"
        self.side = "Right"
        self.orientation = 0  # Default orientation is vertical
        self.mac_address = ""

        self.buttons = {
            # these buttons are mapped to upright usage (invert for sideways)
            "ZR": False,
            "R": False,
            "Plus": False,
            "SLR": False,
            "SRR": False,
            "Y": False,
            "B": False,
            "X": False,
            "A": False,
            "R3": False,
            "Home": False,
            "GameChat": False,
        }

        self.analog_stick = {"X": 0, "Y": 0}
        self.accelerometer = {"X": 0.0, "Y": 0.0, "Z": 0.0}
        self.gyroscope = {"X": 0.0, "Y": 0.0, "Z": 0.0}  # Roll / Pitch / Yaw

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
        self.battery_voltage_mv = None
        self.charging_state = None
        self.battery_level = None
        self.is_connected = False

        self.stick_calibrator = StickCalibrator()

    async def update(self, datas):
        # Button/stick/mouse fields end at byte 23. IMU fields are optional
        # and occupy the final 18 bytes of the 63-byte report 0x05.
        if len(datas) < 24:
            print(f"[WARNING] Data too short: {len(datas)} bytes (expected at least 24)")
            return

        btnDatas = datas[4] << 8 | datas[5]
        JoystickDatas = datas[13:16]
        mouseDatas = datas[16:24]

        self.mouse["X"], self.mouse["Y"] = struct.unpack("<hh", mouseDatas[:4])
        self.mouse["distance_raw"] = struct.unpack_from("<H", mouseDatas, 6)[0]
        self.mouse["distance"] = mouseDatas[7:8].hex()

        self.timestamp = bytes.fromhex(datas[0:4].hex())

        if len(datas) >= 0x22:
            self.battery_voltage_mv = int.from_bytes(datas[0x1F:0x21], "little")
            self.charging_state = datas[0x21]

        if len(datas) >= 0x3C:
            # Unsigned microsecond counter; see JoyConLeft.update().
            self.motionTimestamp = struct.unpack("<I", datas[0x2A:0x2E])[0]
            accel_x_raw, accel_y_raw, accel_z_raw = struct.unpack("<3h", datas[0x30:0x36])
            gyro_x_raw, gyro_y_raw, gyro_z_raw = struct.unpack("<3h", datas[0x36:0x3C])

            accel_factor = 8.0 / 32767.0
            gyro_factor = 2000.0 / 32767.0

            # NOTE: shared with JoyConLeft; needs a hardware pass to split.
            self.accelerometer["X"] = -accel_x_raw * accel_factor
            self.accelerometer["Y"] = -accel_z_raw * accel_factor
            self.accelerometer["Z"] = accel_y_raw * accel_factor

            self.gyroscope["X"] = gyro_x_raw * gyro_factor
            self.gyroscope["Y"] = -gyro_z_raw * gyro_factor
            self.gyroscope["Z"] = gyro_y_raw * gyro_factor

        self.buttons["ZR"] = bool(btnDatas & 0x8000)
        self.buttons["R"] = bool(btnDatas & 0x4000)
        self.buttons["Plus"] = bool(btnDatas & 0x0002)
        self.buttons["SLR"] = bool(btnDatas & 0x2000)
        self.buttons["SRR"] = bool(btnDatas & 0x1000)
        self.buttons["Y"] = bool(btnDatas & 0x0100)
        self.buttons["B"] = bool(btnDatas & 0x0400)
        self.buttons["X"] = bool(btnDatas & 0x0200)
        self.buttons["A"] = bool(btnDatas & 0x0800)
        self.buttons["R3"] = bool(btnDatas & 0x0004)
        self.buttons["Home"] = bool(btnDatas & 0x0010)
        self.buttons["GameChat"] = bool(btnDatas & 0x0040)

        self.analog_stick["X"], self.analog_stick["Y"] = joystick_decoder(
            JoystickDatas, self.orientation, self.stick_calibrator
        )

        self.mouseBtn["Left"] = bool(btnDatas & 0x4000)  # R
        self.mouseBtn["Right"] = bool(btnDatas & 0x8000)  # ZR
        self.mouseBtn["scrollX"], self.mouseBtn["scrollY"] = scroll_decoder(
            JoystickDatas, self.stick_calibrator
        )

        self.is_connected = True

    def setMacAddress(self, mac_address):
        self.mac_address = mac_address


# Return stick values from 0 to 32768, centred on 16384.
def joystick_decoder(data, orientation, calibrator=None):
    if len(data) != 3:
        return 4096 * 4, 4096 * 4

    nx, ny = normalized_pair(data, calibrator)
    x = int(nx * 32768)
    y = int(ny * 32768)

    if orientation == 1:  # Horizontal: rotate 90 degrees clockwise
        x_new = y
        y_new = 32768 - x
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
