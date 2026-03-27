from controllers.JoyconL import JoyConLeft
from controllers.JoyconR import JoyConRight

from dsu_server import controller_update
from controller_command import ControllerCommand, UUID_CMD

from config import Config
from pynput.mouse import Controller, Button

import vgamepad

# Xbox 360 button mapping
Controls = {
    "Left": {
        "ZL": "LEFT_TRIGGER",
        "L": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_SHOULDER,
        "L3": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_THUMB,
        "Up": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_UP,
        "Down": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_DOWN,
        "Left": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_LEFT,
        "Right": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_RIGHT,
        "Minus": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_BACK,
        "Capture": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_GUIDE,
    },
    "Right": {
        "ZR": "RIGHT_TRIGGER",
        "R": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_SHOULDER,
        "R3": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_THUMB,
        "A": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_A,
        "B": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_B,
        "X": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_X,
        "Y": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_Y,
        "Plus": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_START,
        "Home": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_GUIDE,
    }
}
import threading
import time
import asyncio


# Initialize Joy-Con controllers
joyconLeft = JoyConLeft()
joyconRight = JoyConRight()

# Read the configuration from config.ini
config = Config().getConfig()

# Initialize vgamepad device (Xbox 360)
gamepad = vgamepad.VX360Gamepad()

# Store clients for vibration
vibration_clients = {}
# Store event loop for thread-safe callback
_event_loop = None

# Vibration callback function
async def send_vibration_to_client(client, large_motor, small_motor):
    """Send vibration command to a specific Joy-Con client"""
    try:
        # Convert 0-255 motor values to Joy-Con vibration format
        left_intensity = min(255, max(0, large_motor))
        right_intensity = min(255, max(0, small_motor))
        
        # Add deadzone to ignore very small vibration values
        # This prevents constant micro-vibrations from gyro noise or game idle states
        DEADZONE = 5  # Ignore values below 5
        if left_intensity < DEADZONE:
            left_intensity = 0
        if right_intensity < DEADZONE:
            right_intensity = 0
        
        # Build rumble data according to joycon2-connector format
        # Format: 11 bytes
        # [0] = 0x10 (report ID)
        # [1] = 0x00 (timer)
        # [2] = 0x01 (enable vibration)
        # [3-5] = left motor (amp low, amp high, freq)
        # [6-8] = right motor (amp low, amp high, freq)
        # [9-10] = padding
        
        if left_intensity == 0 and right_intensity == 0:
            # Stop vibration - send zeros
            vibration_data = bytes.fromhex("0a000000000000000000000000")
        else:
            print(f"[DEBUG] Sending vibration: left={left_intensity}, right={right_intensity}")
            
            # Joy-Con 2 only accepts fixed vibration values
            # Use the working JOY2_CONNECTED_VIBRATION format with fixed values
            # Format: 0A 91 01 02 00 [right] 00 00 [left] 00 00 00
            vibration_data = bytes.fromhex("0A9101020004000001000000")
            print(f"[DEBUG] Vibration data: {vibration_data.hex()}")
        
        await client.write_gatt_char(UUID_CMD, vibration_data)
        if left_intensity > 0 or right_intensity > 0:
            print("[DEBUG] Vibration sent successfully")
    except Exception as e:
        print(f"[DEBUG] Vibration error: {e}")

async def send_vibration(large_motor, small_motor):
    """Send vibration to all connected Joy-Con clients"""
    tasks = []
    for side, client in vibration_clients.items():
        if client:
            tasks.append(send_vibration_to_client(client, large_motor, small_motor))
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)

def vibration_callback(client, target, large_motor, small_motor, led_number, user_data):
    """Callback for gamepad vibration feedback from vgamepad"""
    print(f"[DEBUG] Vibration callback: large={large_motor}, small={small_motor}")
    global _event_loop
    if _event_loop is not None:
        try:
            asyncio.run_coroutine_threadsafe(send_vibration(large_motor, small_motor), _event_loop)
        except Exception as e:
            print(f"[DEBUG] Vibration callback error: {e}")
    else:
        print("[DEBUG] No event loop available")

def register_vibration(client, side):
    """Register a client for vibration"""
    vibration_clients[side] = client
    # Only register the callback once
    if len(vibration_clients) == 1:
        gamepad.register_notification(vibration_callback)

# Initialize mouse loop at the start
firstCall = False

# Mouse movement variables
mouse = Controller()

targetX, targetY = 0, 0
previousMouseX, previousMouseY = 0, 0
leftPressed = False
rightPressed = False
joyconMouseMode = None

def mouse_loop():
    global targetX, targetY
    while True:
        stepX = targetX // 6
        stepY = targetY // 6
        if stepX != 0 or stepY != 0:
            mouse.move(stepX, stepY)
            targetX -= stepX
            targetY -= stepY
        time.sleep(0.006)  # 60 ms


async def update(controllerSide, joycon):
    global targetX, targetY, previousMouseX, previousMouseY, leftPressed, rightPressed, joyconMouseMode, firstCall

    isMouseMode = joycon.mouse["distance"] == "00" or joycon.mouse["distance"] == "01"
    if joyconMouseMode is None and isMouseMode is True and config['mouse_mode'] != 0:
        joyconMouseMode = controllerSide
    elif isMouseMode is False and joyconMouseMode == controllerSide:
        joyconMouseMode = None

    if firstCall == False and isMouseMode == True:
        threading.Thread(target=mouse_loop, daemon=True).start()
        firstCall = True

    # Handle buttons
    for side in ["Left", "Right"]:
        for btnName, btnValue in Controls[side].items():
            pressed = (joyconLeft.buttons.get(btnName, False) if side == "Left" else joyconRight.buttons.get(btnName, False)) if side != joyconMouseMode else False
            
            # Handle analog triggers (ZL/ZR) separately
            if btnValue == "LEFT_TRIGGER":
                if pressed:
                    gamepad.left_trigger(255)  # Full press
                else:
                    gamepad.left_trigger(0)
            elif btnValue == "RIGHT_TRIGGER":
                if pressed:
                    gamepad.right_trigger(255)  # Full press
                else:
                    gamepad.right_trigger(0)
            else:
                # Regular buttons
                if pressed:
                    gamepad.press_button(btnValue)
                else:
                    gamepad.release_button(btnValue)

    if joyconMouseMode != "Left":
        # Convert 0-32767 (Joy-Con format) to -32768-32767 (Xbox format)
        left_x_raw = min(joyconLeft.analog_stick["X"], 32767)
        left_y_raw = min(joyconLeft.analog_stick["Y"], 32767)
        left_x = int((left_x_raw - 16384) * 2)
        left_y = int((left_y_raw - 16384) * 2)
        # Clamp values to valid range
        left_x = max(-32768, min(32767, left_x))
        left_y = max(-32768, min(32767, left_y))
        # Xbox 360: negative Y = up, positive Y = down (same as Joy-Con after conversion)
        gamepad.left_joystick(left_x, left_y)
        
        if controllerSide == "Left" and config["enable_dsu"] == True:
            await controller_update(joyconLeft.motionTimestamp, joyconLeft.accelerometer, joyconLeft.gyroscope, slot=0)
    
    if joyconMouseMode != "Right":
        # Convert 0-32767 (Joy-Con format) to -32768-32767 (Xbox format)
        right_x_raw = min(joyconRight.analog_stick["X"], 32767)
        right_y_raw = min(joyconRight.analog_stick["Y"], 32767)
        right_x = int((right_x_raw - 16384) * 2)
        right_y = int((right_y_raw - 16384) * 2)
        # Clamp values to valid range
        right_x = max(-32768, min(32767, right_x))
        right_y = max(-32768, min(32767, right_y))
        # Right stick Y needs inversion
        gamepad.right_joystick(right_x, -right_y)

        if controllerSide == "Right" and config["enable_dsu"] == True:
            await controller_update(joyconRight.motionTimestamp, joyconRight.accelerometer, joyconRight.gyroscope, slot=1)

    gamepad.update()

    if isMouseMode == True and joyconMouseMode == controllerSide:
        deltaX = (joycon.mouse["X"] - previousMouseX + 32768) % 65536 - 32768 # Normalize mouse X movement
        deltaY = (joycon.mouse["Y"] - previousMouseY + 32768) % 65536 - 32768 # Normalize mouse Y movement
        previousMouseX = joycon.mouse["X"]
        previousMouseY = joycon.mouse["Y"]

        targetX += deltaX
        targetY += deltaY

        if joycon.mouseBtn["Left"] == True:
            if not leftPressed:
                mouse.press(Button.left)
            leftPressed = True
        else:
            if leftPressed:
                mouse.release(Button.left)
            leftPressed = False

        if joycon.mouseBtn["Right"] == True:
            if not rightPressed:
                mouse.press(Button.right)
            rightPressed = True
        else:
            if rightPressed:
                mouse.release(Button.right)
            rightPressed = False

        mouse.scroll(joycon.mouseBtn["scrollX"] / 32768, joycon.mouseBtn["scrollY"] / 32768)  # Scroll vertically


async def notify_duo_joycons(client, side, data):
    global _event_loop
    # Store event loop for thread-safe vibration callback
    if _event_loop is None:
        _event_loop = asyncio.get_running_loop()
    
    # Register vibration callback on first connection
    if side not in vibration_clients:
        register_vibration(client, side)
    
    if side == "Left":
        await joyconLeft.update(data)
        await update(side, joyconLeft)
    elif side == "Right":
        await joyconRight.update(data)
        await update(side, joyconRight)
    else:
        print("Unknown controller side.")
    
    return client