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

# Vibration callback function
async def send_vibration(client, large_motor, small_motor):
    """Send vibration command to Joy-Con based on gamepad feedback"""
    try:
        # Convert 0-255 motor values to Joy-Con vibration format
        # Scale to 0-255 range for Joy-Con
        left_intensity = min(255, max(0, large_motor))
        right_intensity = min(255, max(0, small_motor))
        
        if left_intensity > 0 or right_intensity > 0:
            # Create vibration packet (simplified format)
            # Joy-Con 2 uses a specific format for vibration
            left_hex = format(left_intensity, '02x')
            right_hex = format(right_intensity, '02x')
            # Send vibration command
            vibration_data = bytes.fromhex(f"0a91010200{right_hex}0000{left_hex}000000")
            await client.write_gatt_char(UUID_CMD, vibration_data)
    except Exception as e:
        print(f"Vibration error: {e}")

def vibration_callback(client, target, large_motor, small_motor, led_number, user_data):
    """Callback for gamepad vibration feedback"""
    # Schedule the async vibration in the event loop
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(send_vibration(client, large_motor, small_motor))
    except:
        pass

# Store clients for vibration
vibration_clients = {}

def register_vibration(client, side):
    """Register vibration callback for a client"""
    vibration_clients[side] = client
    # Register the callback with vgamepad
    gamepad.register_notification(lambda client, target, large_motor, small_motor, led_number, user_data: vibration_callback(client, target, large_motor, small_motor, led_number, user_data))

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