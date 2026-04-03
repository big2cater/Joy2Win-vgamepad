from controllers.JoyconL import JoyConLeft
from controllers.JoyconR import JoyConRight

from dsu_server import controller_update
from controller_command import ControllerCommand, UUID_CMD

from config import Config
from pynput.mouse import Controller, Button
from logger_config import info, warning, error, debug

import vgamepad
import copy

# Xbox button name to vgamepad mapping
XBOX_BUTTON_MAP = {
    "": None,
    "XUSB_GAMEPAD_A": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_A,
    "XUSB_GAMEPAD_B": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_B,
    "XUSB_GAMEPAD_X": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_X,
    "XUSB_GAMEPAD_Y": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_Y,
    "XUSB_GAMEPAD_LEFT_SHOULDER": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_SHOULDER,
    "XUSB_GAMEPAD_RIGHT_SHOULDER": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_SHOULDER,
    "XUSB_GAMEPAD_LEFT_THUMB": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_THUMB,
    "XUSB_GAMEPAD_RIGHT_THUMB": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_THUMB,
    "XUSB_GAMEPAD_BACK": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_BACK,
    "XUSB_GAMEPAD_START": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_START,
    "XUSB_GAMEPAD_GUIDE": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_GUIDE,
    "XUSB_GAMEPAD_DPAD_UP": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_UP,
    "XUSB_GAMEPAD_DPAD_DOWN": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_DOWN,
    "XUSB_GAMEPAD_DPAD_LEFT": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_LEFT,
    "XUSB_GAMEPAD_DPAD_RIGHT": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_RIGHT,
}


def get_default_controls():
    """Get default control mapping"""
    return {
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
            "SLL": None,
            "SRL": None,
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
            "SLR": None,
            "SRR": None,
        }
    }


# Per-pair control mappings
pair_controls = {}


def get_pair_controls(pair_id: int):
    """Get or create control mapping for a pair, loading from config if available"""
    if pair_id not in pair_controls:
        # Start with default controls
        controls = get_default_controls()
        
        # Try to load SL/SR mappings from config for this pair
        try:
            import configparser
            import os
            
            parser = configparser.ConfigParser()
            if os.path.exists('config.ini'):
                parser.read('config.ini')
                
                section = f'Pair_{pair_id}'
                if section in parser:
                    # Load SL/SR mappings from config
                    sll = parser[section].get('sll_mapping', '')
                    srl = parser[section].get('srl_mapping', '')
                    slr = parser[section].get('slr_mapping', '')
                    srr = parser[section].get('srr_mapping', '')
                    
                    # Update mappings
                    controls["Left"]["SLL"] = XBOX_BUTTON_MAP.get(sll, None)
                    controls["Left"]["SRL"] = XBOX_BUTTON_MAP.get(srl, None)
                    controls["Right"]["SLR"] = XBOX_BUTTON_MAP.get(slr, None)
                    controls["Right"]["SRR"] = XBOX_BUTTON_MAP.get(srr, None)
                    
                    
        except Exception as e:
            pass  # Silent fail if config not found
        
        pair_controls[pair_id] = controls
    
    return pair_controls[pair_id]


def update_sl_sr_mappings_for_pair(pair_id: int, sll: str, srl: str, slr: str, srr: str):
    """Update SL/SR button mappings for a specific pair"""
    try:
        controls = get_pair_controls(pair_id)
        controls["Left"]["SLL"] = XBOX_BUTTON_MAP.get(sll, None)
        controls["Left"]["SRL"] = XBOX_BUTTON_MAP.get(srl, None)
        controls["Right"]["SLR"] = XBOX_BUTTON_MAP.get(slr, None)
        controls["Right"]["SRR"] = XBOX_BUTTON_MAP.get(srr, None)
    except Exception as e:
        pass  # Silent fail


import threading
import time
import asyncio


# Initialize Joy-Con controllers
joyconLeft = JoyConLeft()
joyconRight = JoyConRight()

def reset_joycon_instances():
    """Reset Joy-Con controller instances (called when reconnecting)"""
    global joyconLeft, joyconRight
    joyconLeft = JoyConLeft()
    joyconRight = JoyConRight()

# Read the configuration from config.ini
config = Config().getConfig()

# Store clients for vibration
vibration_clients = {}
# Store event loop for thread-safe callback
_event_loop = None
# Control whether vibration is enabled
_vibration_enabled = True  # Default to enabled

def set_vibration_enabled(enabled):
    """Set whether vibration feedback is enabled"""
    global _vibration_enabled
    _vibration_enabled = enabled

# Vibration callback function
async def send_vibration_to_client(client, large_motor, small_motor):
    """Send vibration command to a specific Joy-Con client"""
    try:
        left_intensity = min(255, max(0, large_motor))
        right_intensity = min(255, max(0, small_motor))

        DEADZONE = 5
        if left_intensity < DEADZONE:
            left_intensity = 0
        if right_intensity < DEADZONE:
            right_intensity = 0

        if left_intensity == 0 and right_intensity == 0:
            vibration_data = bytes.fromhex("0a000000000000000000000000")
        else:
            vibration_data = bytes.fromhex("0A9101020004000001000000")

        await client.write_gatt_char(UUID_CMD, vibration_data)
    except Exception as e:
        pass  # Silent fail

async def send_vibration(large_motor, small_motor):
    """Send vibration to all connected Joy-Con clients"""
    tasks = []
    combined_intensity = max(large_motor, small_motor)

    for side in ['Left', 'Right']:
        if side in vibration_clients and vibration_clients[side]:
            tasks.append(send_vibration_to_client(vibration_clients[side], combined_intensity, combined_intensity))

    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)

def vibration_callback(client, target, large_motor, small_motor, led_number, user_data):
    """Callback for gamepad vibration feedback from vgamepad"""
    if not _vibration_enabled:
        return

    global _event_loop
    if _event_loop is not None:
        try:
            asyncio.run_coroutine_threadsafe(send_vibration(large_motor, small_motor), _event_loop)
        except Exception as e:
            pass  # Silent fail

def register_vibration(client, side, pair_id: int = 0):
    """Register a client for vibration"""
    vibration_clients[side] = client
    if len(vibration_clients) == 1:
        from controller_manager import get_controller_manager
        manager = get_controller_manager()
        pair = manager.get_pair(pair_id)
        if pair and pair.gamepad:
            pair.gamepad.register_notification(vibration_callback)


# Per-pair state for duo mode
pair_state = {}

# Per-pair mouse enabled state (set from GUI)
pair_mouse_enabled = {}


def get_pair_state(pair_id: int):
    """Get or create state for a pair"""
    if pair_id not in pair_state:
        pair_state[pair_id] = {
            'targetX': 0,
            'targetY': 0,
            'previousMouseX': 0,
            'previousMouseY': 0,
            'leftPressed': False,
            'rightPressed': False,
            'joyconMouseMode': None,
            'firstCall': False,
        }
    return pair_state[pair_id]


def set_mouse_enabled(pair_id: int, enabled: bool):
    """Set mouse control enabled for a specific pair (called from GUI)"""
    pair_mouse_enabled[pair_id] = enabled


def is_mouse_enabled(pair_id: int) -> bool:
    """Check if mouse control is enabled for a specific pair"""
    return pair_mouse_enabled.get(pair_id, False)


def mouse_loop():
    """Global mouse loop - handles all pairs"""
    while True:
        for pair_id, state in pair_state.items():
            stepX = state['targetX'] // 6
            stepY = state['targetY'] // 6
            if stepX != 0 or stepY != 0:
                mouse.move(stepX, stepY)
                state['targetX'] -= stepX
                state['targetY'] -= stepY
        time.sleep(0.006)


mouse = Controller()


async def update(pair_id: int = 0):
    from controller_manager import get_controller_manager
    manager = get_controller_manager()
    pair = manager.get_pair(pair_id)
    if not pair or not pair.gamepad:
        return

    gamepad = pair.gamepad
    state = get_pair_state(pair_id)
    controls = get_pair_controls(pair_id)

    # Check if mouse control is enabled for this pair
    mouse_enabled = is_mouse_enabled(pair_id)

    # Check mouse mode from both Joy-Cons
    isMouseModeLeft = joyconLeft.mouse["distance"] == "00" or joyconLeft.mouse["distance"] == "01"
    isMouseModeRight = joyconRight.mouse["distance"] == "00" or joyconRight.mouse["distance"] == "01"
    
    if mouse_enabled and state['joyconMouseMode'] is None and (isMouseModeLeft or isMouseModeRight):
        state['joyconMouseMode'] = "Left" if isMouseModeLeft else "Right"
    elif not mouse_enabled or (not isMouseModeLeft and not isMouseModeRight):
        state['joyconMouseMode'] = None

    if state['firstCall'] == False and mouse_enabled and (isMouseModeLeft or isMouseModeRight):
        threading.Thread(target=mouse_loop, daemon=True).start()
        state['firstCall'] = True

    # Handle buttons
    # Left side buttons from joyconLeft
    for btnName, btnValue in controls["Left"].items():
        pressed = joyconLeft.buttons.get(btnName, False) if state.get('joyconMouseMode') != "Left" else False

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
        elif btnValue is None:
            pass
        else:
            if pressed:
                gamepad.press_button(btnValue)
            else:
                gamepad.release_button(btnValue)
    
    # Right side buttons from joyconRight
    for btnName, btnValue in controls["Right"].items():
        pressed = joyconRight.buttons.get(btnName, False) if state.get('joyconMouseMode') != "Right" else False

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
        elif btnValue is None:
            pass
        else:
            if pressed:
                gamepad.press_button(btnValue)
            else:
                gamepad.release_button(btnValue)

    if state['joyconMouseMode'] != "Left":
        # Convert 0-32767 (Joy-Con format) to -32768-32767 (Xbox format)
        left_x_raw = min(joyconLeft.analog_stick["X"], 32767)
        left_y_raw = min(joyconLeft.analog_stick["Y"], 32767)
        left_x = int((left_x_raw - 16384) * 2)
        left_y = int((left_y_raw - 16384) * 2)
        # Clamp values to valid range
        left_x = max(-32768, min(32767, left_x))
        left_y = max(-32768, min(32767, left_y))
        gamepad.left_joystick(left_x, left_y)
        
        # Debug: Print left stick values
        if config["enable_dsu"] == True:
            await controller_update(joyconLeft.motionTimestamp, joyconLeft.accelerometer, joyconLeft.gyroscope, slot=pair_id * 2)

    if state['joyconMouseMode'] != "Right":
        # Convert 0-32767 (Joy-Con format) to -32768-32767 (Xbox format)
        right_x_raw = min(joyconRight.analog_stick["X"], 32767)
        right_y_raw = min(joyconRight.analog_stick["Y"], 32767)
        right_x = int((right_x_raw - 16384) * 2)
        right_y = int((right_y_raw - 16384) * 2)
        right_x = max(-32768, min(32767, right_x))
        right_y = max(-32768, min(32767, right_y))
        gamepad.right_joystick(right_x, right_y)

        if config["enable_dsu"] == True:
            await controller_update(joyconRight.motionTimestamp, joyconRight.accelerometer, joyconRight.gyroscope, slot=pair_id * 2 + 1)

    gamepad.update()

    # Handle mouse movement based on which Joy-Con is in mouse mode
    if state['joyconMouseMode'] == "Left":
        joycon = joyconLeft
    elif state['joyconMouseMode'] == "Right":
        joycon = joyconRight
    else:
        joycon = None
    
    if joycon is not None:
        deltaX = (joycon.mouse["X"] - state['previousMouseX'] + 32768) % 65536 - 32768
        deltaY = (joycon.mouse["Y"] - state['previousMouseY'] + 32768) % 65536 - 32768
        state['previousMouseX'] = joycon.mouse["X"]
        state['previousMouseY'] = joycon.mouse["Y"]

        state['targetX'] += deltaX
        state['targetY'] += deltaY

        if joycon.mouseBtn["Left"] == True:
            if not state['leftPressed']:
                mouse.press(Button.left)
            state['leftPressed'] = True
        else:
            if state['leftPressed']:
                mouse.release(Button.left)
            state['leftPressed'] = False

        if joycon.mouseBtn["Right"] == True:
            if not state['rightPressed']:
                mouse.press(Button.right)
            state['rightPressed'] = True
        else:
            if state['rightPressed']:
                mouse.release(Button.right)
            state['rightPressed'] = False

        mouse.scroll(joycon.mouseBtn["scrollX"] / 32768, joycon.mouseBtn["scrollY"] / 32768)


async def notify_duo_joycons(client, side, data, pair_id: int = 0):
    global _event_loop
    if _event_loop is None:
        _event_loop = asyncio.get_running_loop()

    if side not in vibration_clients:
        register_vibration(client, side)

    if side == "Left":
        
        await joyconLeft.update(data)
        await update(pair_id)
    elif side == "Right":
        
        await joyconRight.update(data)
        await update(pair_id)
    else:
        warning("Unknown controller side.")

    return client
