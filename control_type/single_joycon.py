from controllers.JoyconL import JoyConLeft
from controllers.JoyconR import JoyConRight

from dsu_server import controller_update
from controller_command import ControllerCommand, UUID_CMD

from config import Config
from pynput.mouse import Controller, Button

import vgamepad

# Xbox 360 button mapping for single Joy-Con
Controls = {
    "Left": {
        "0": {  # Vertical
            "ZL": "LEFT_TRIGGER",
            "L3": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_THUMB,
            "Up": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_UP,
            "Down": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_DOWN,
            "Left": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_LEFT,
            "Right": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_RIGHT,
            "Minus": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_BACK,
            "SLL": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_SHOULDER,
            "SRL": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_SHOULDER,
            "Capture": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_GUIDE,
        },
        "1": {  # Horizontal
            "ZL": "LEFT_TRIGGER",
            "L3": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_THUMB,
            "Up": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_LEFT,
            "Down": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_RIGHT,
            "Left": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_DOWN,
            "Right": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_UP,
            "Minus": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_START,
            "SLL": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_SHOULDER,
            "SRL": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_SHOULDER,
            "Capture": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_GUIDE,
        },
    },
    "Right": {
        "0": {  # Vertical
            "ZR": "RIGHT_TRIGGER",
            "R3": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_THUMB,
            "A": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_A,
            "B": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_B,
            "X": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_X,
            "Y": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_Y,
            "Plus": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_START,
            "SRR": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_SHOULDER,
            "SLR": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_SHOULDER,
            "Home": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_GUIDE,
        },
        "1": {  # Horizontal
            "ZR": "RIGHT_TRIGGER",
            "R3": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_THUMB,
            "A": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_B,
            "B": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_Y,
            "X": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_X,
            "Y": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_A,
            "Plus": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_START,
            "SRR": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_SHOULDER,
            "SLR": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_SHOULDER,
            "Home": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_GUIDE,
        },
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
        left_intensity = min(255, max(0, large_motor))
        right_intensity = min(255, max(0, small_motor))
        
        if left_intensity > 0 or right_intensity > 0:
            left_hex = format(left_intensity, '02x')
            right_hex = format(right_intensity, '02x')
            vibration_data = bytes.fromhex(f"0a91010200{right_hex}0000{left_hex}000000")
            await client.write_gatt_char(UUID_CMD, vibration_data)
    except Exception as e:
        print(f"Vibration error: {e}")

def vibration_callback(client, target, large_motor, small_motor, led_number, user_data):
    """Callback for gamepad vibration feedback"""
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
    gamepad.register_notification(lambda client, target, large_motor, small_motor, led_number, user_data: vibration_callback(client, target, large_motor, small_motor, led_number, user_data))

# Initialize mouse loop at the start
firstCall = False

# Mouse movement variables
mouse = Controller()

targetX, targetY = 0, 0
previousMouseX, previousMouseY = 0, 0
leftPressed = False
rightPressed = False

#Calculating latency
lastTime = time.time()

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

async def update(joycon, side, orientation, isInMouse):
    for btnName, btnValue in Controls[side][str(orientation)].items():
        pressed = joycon.buttons.get(btnName, False) and not isInMouse
        
        # Handle analog triggers (ZL/ZR) separately
        if btnValue == "LEFT_TRIGGER":
            if pressed:
                gamepad.left_trigger(255)
            else:
                gamepad.left_trigger(0)
        elif btnValue == "RIGHT_TRIGGER":
            if pressed:
                gamepad.right_trigger(255)
            else:
                gamepad.right_trigger(0)
        else:
            # Regular buttons
            if pressed:
                gamepad.press_button(btnValue)
            else:
                gamepad.release_button(btnValue)

    if not isInMouse:
        # Convert 0-32767 (Joy-Con format) to -32768-32767 (Xbox format)
        stick_x_raw = min(joycon.analog_stick["X"], 32767)
        stick_y_raw = min(joycon.analog_stick["Y"], 32767)
        stick_x = int((stick_x_raw - 16384) * 2)
        stick_y = int((stick_y_raw - 16384) * 2)
        # Clamp values to valid range
        stick_x = max(-32768, min(32767, stick_x))
        stick_y = max(-32768, min(32767, stick_y))
        # Xbox 360: negative Y = up, positive Y = down
        gamepad.left_joystick(stick_x, stick_y)
        
    if config["enable_dsu"] == True:
        await controller_update(joycon.motionTimestamp, joycon.accelerometer, joycon.gyroscope)
    
    gamepad.update()


async def controller_traitement(joycon, side, orientation, data):
    global firstCall, previousMouseX, previousMouseY, targetX, targetY, lastTime, leftPressed, rightPressed

    isMouseMode = joycon.mouse["distance"] == "00" or joycon.mouse["distance"] == "01" # Check if mouse mode is active based on mouse distance

    # Initialize mouse mode if not already done
    if firstCall == False and (config['mouse_mode'] == 2 or config["mouse_mode"] == 1 and isMouseMode == True):
        threading.Thread(target=mouse_loop, daemon=True).start()
        firstCall = True

    # Update controller orientation
    if joycon.orientation != orientation:
        joycon.orientation = orientation

    await joycon.update(data) # Update Joy-Con state with received data

    await update(joycon, side, orientation, isMouseMode) # Update vJoy buttons and axes

    if config['mouse_mode'] == 2 or config["mouse_mode"] == 1 and isMouseMode == True:
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

        mouse.scroll(joycon.mouseBtn["scrollX"] / 32768, joycon.mouseBtn["scrollY"] / 32768)

    # Latency calculation
    currentTime = time.time()
    elapsedTime = (currentTime - lastTime) * 1000  # Convert to milliseconds
    lastTime = currentTime
    #print(f"Latency: {elapsedTime:.4f} milliseconds")


async def notify_single_joycons(client, side, orientation, data):
    # Register vibration callback on first connection
    if side not in vibration_clients:
        register_vibration(client, side)
    
    if(side == "Left"):
        await controller_traitement(joyconLeft, side, orientation, data)
    elif(side == "Right"):
        await controller_traitement(joyconRight, side, orientation, data)
    return client