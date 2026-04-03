from controllers.JoyconL import JoyConLeft
from controllers.JoyconR import JoyConRight

from dsu_server import controller_update
from controller_command import ControllerCommand, UUID_CMD
from controller_manager import get_controller_manager

from config import Config
from pynput.mouse import Controller, Button

import vgamepad
import threading
import time
import asyncio
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
    """Get default control mapping for single Joy-Con"""
    return {
        "Left": {
            "0": {  # Vertical
                "ZL": "LEFT_TRIGGER",
                "L": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_SHOULDER,  # Add L button mapping
                "L3": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_THUMB,
                "Up": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_UP,
                "Down": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_DOWN,
                "Left": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_LEFT,
                "Right": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_RIGHT,
                "Minus": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_BACK,
                "SLL": None,
                "SRL": None,
                "Capture": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_GUIDE,
            },
            "1": {  # Horizontal
                "ZL": "LEFT_TRIGGER",
                "L": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_SHOULDER,  # Add L button mapping
                "L3": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_THUMB,
                "Up": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_LEFT,
                "Down": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_RIGHT,
                "Left": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_DOWN,
                "Right": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_UP,
                "Minus": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_START,
                "SLL": None,
                "SRL": None,
                "Capture": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_GUIDE,
            },
        },
        "Right": {
            "0": {  # Vertical
                "ZR": "RIGHT_TRIGGER",
                "R": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_SHOULDER,  # Add R button mapping
                "R3": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_THUMB,
                "A": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_A,
                "B": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_B,
                "X": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_X,
                "Y": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_Y,
                "Plus": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_START,
                "SRR": None,
                "SLR": None,
                "Home": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_GUIDE,
            },
            "1": {  # Horizontal
                "ZR": "RIGHT_TRIGGER",
                "R": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_SHOULDER,  # Add R button mapping
                "R3": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_THUMB,
                "A": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_B,
                "B": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_Y,
                "X": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_X,
                "Y": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_A,
                "Plus": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_START,
                "SRR": None,
                "SLR": None,
                "Home": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_GUIDE,
            },
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
                    
                    # Update mappings for both orientations
                    for orientation in ["0", "1"]:
                        controls["Left"][orientation]["SLL"] = XBOX_BUTTON_MAP.get(sll, None)
                        controls["Left"][orientation]["SRL"] = XBOX_BUTTON_MAP.get(srl, None)
                        controls["Right"][orientation]["SLR"] = XBOX_BUTTON_MAP.get(slr, None)
                        controls["Right"][orientation]["SRR"] = XBOX_BUTTON_MAP.get(srr, None)
                            
        except Exception as e:
            pass
                
        pair_controls[pair_id] = controls
    
    return pair_controls[pair_id]


def update_sl_sr_mappings_for_pair(pair_id: int, sll: str, srl: str, slr: str, srr: str):
    """Update SL/SR button mappings for a specific pair"""
    try:
        controls = get_pair_controls(pair_id)
        for orientation in ["0", "1"]:
            controls["Left"][orientation]["SLL"] = XBOX_BUTTON_MAP.get(sll, None)
            controls["Left"][orientation]["SRL"] = XBOX_BUTTON_MAP.get(srl, None)
            controls["Right"][orientation]["SLR"] = XBOX_BUTTON_MAP.get(slr, None)
            controls["Right"][orientation]["SRR"] = XBOX_BUTTON_MAP.get(srr, None)
    except Exception as e:
        pass


# Per-pair state
pair_state = {}

# Per-pair mouse enabled state (set from GUI)
pair_mouse_enabled = {}


def set_mouse_enabled(pair_id: int, enabled: bool):
    """Set mouse control enabled for a specific pair (called from GUI)"""
    pair_mouse_enabled[pair_id] = enabled


def is_mouse_enabled(pair_id: int) -> bool:
    """Check if mouse control is enabled for a specific pair"""
    return pair_mouse_enabled.get(pair_id, False)


def get_pair_state(pair_id: int):
    """Get or create state for a pair"""
    if pair_id not in pair_state:
        pair_state[pair_id] = {
            'joycon': None,
            'side': None,
            'mouse': Controller(),
            'targetX': 0,
            'targetY': 0,
            'previousMouseX': 0,
            'previousMouseY': 0,
            'leftPressed': False,
            'rightPressed': False,
            'firstCall': False,
            'lastTime': time.time(),
        }
    return pair_state[pair_id]


def reset_pair_state(pair_id: int):
    """Reset state for a pair (called when reconnecting)"""
    if pair_id in pair_state:
        pair_state[pair_id] = {
            'joycon': None,
            'side': None,
            'mouse': Controller(),
            'targetX': 0,
            'targetY': 0,
            'previousMouseX': 0,
            'previousMouseY': 0,
            'leftPressed': False,
            'rightPressed': False,
            'firstCall': False,
            'lastTime': time.time(),
        }


# Control whether vibration is enabled
_vibration_enabled = True


def set_vibration_enabled(enabled):
    """Set whether vibration feedback is enabled"""
    global _vibration_enabled
    _vibration_enabled = enabled


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
        print(f"Vibration error: {e}")


# Global event loop for vibration callbacks
_vibration_event_loop = None
_vibration_thread = None

def _init_vibration_loop():
    """Initialize a dedicated event loop for vibration callbacks"""
    global _vibration_event_loop, _vibration_thread
    
    if _vibration_event_loop is None:
        # Create a new event loop in a background thread
        import threading
        
        def run_event_loop():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            global _vibration_event_loop
            _vibration_event_loop = loop
            loop.run_forever()
        
        _vibration_thread = threading.Thread(target=run_event_loop, daemon=True)
        _vibration_thread.start()
        
        # Wait a bit for the loop to be ready
        import time
        while _vibration_event_loop is None:
            time.sleep(0.01)

def vibration_callback(client, target, large_motor, small_motor, led_number, user_data):
    """Callback for gamepad vibration feedback from vgamepad"""
    if not _vibration_enabled:
        return

    pair_id = user_data if user_data is not None else 0
    
    # Ensure vibration event loop is initialized
    _init_vibration_loop()

    manager = get_controller_manager()
    pair = manager.get_pair(pair_id)
    if not pair:
        return
    
    # In single Joy-Con mode, check which Joy-Con is connected
    target_client = None
    if pair.left.is_connected and pair.left.client:
        target_client = pair.left.client
    elif pair.right.is_connected and pair.right.client:
        target_client = pair.right.client
    
    if target_client:
        try:
            # Use the dedicated vibration event loop
            asyncio.run_coroutine_threadsafe(
                send_vibration_to_client(target_client, large_motor, small_motor),
                _vibration_event_loop
            )
        except Exception as e:
            pass  # Silent fail


def register_vibration(pair_id: int):
    """Register vibration callback for a pair"""
    manager = get_controller_manager()
    pair = manager.get_pair(pair_id)
    if pair and pair.gamepad:
        pair.gamepad.register_notification(lambda client, target, large_motor, small_motor, led_number, user_data: vibration_callback(client, target, large_motor, small_motor, led_number, pair_id))


def mouse_loop(pair_id: int):
    """Mouse movement loop for a pair"""
    state = get_pair_state(pair_id)
    while True:
        stepX = state['targetX'] // 6
        stepY = state['targetY'] // 6
        if stepX != 0 or stepY != 0:
            state['mouse'].move(stepX, stepY)
            state['targetX'] -= stepX
            state['targetY'] -= stepY
        time.sleep(0.006)


async def update(joycon, side, orientation, isInMouse, pair_id: int):
    """Update gamepad state for a specific pair"""
    state = get_pair_state(pair_id)
    controls = get_pair_controls(pair_id)
    manager = get_controller_manager()
    pair = manager.get_pair(pair_id)

    if not pair:
        return

    gamepad = pair.gamepad
    config = Config().getConfig()
    
    for btnName, btnValue in controls[side][str(orientation)].items():
        pressed = joycon.buttons.get(btnName, False) and not isInMouse

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

    if not isInMouse:
        stick_x_raw = min(joycon.analog_stick["X"], 32767)
        stick_y_raw = min(joycon.analog_stick["Y"], 32767)
        stick_x = int((stick_x_raw - 16384) * 2)
        stick_y = int((stick_y_raw - 16384) * 2)
        stick_x = max(-32768, min(32767, stick_x))
        stick_y = max(-32768, min(32767, stick_y))
        
        # Apply deadzone to prevent drift
        DEADZONE = 3000  # Increased deadzone to prevent drift
        if abs(stick_x) < DEADZONE:
            stick_x = 0
        if abs(stick_y) < DEADZONE:
            stick_y = 0
        
        gamepad.left_joystick(stick_x, stick_y)

    if config.get("enable_dsu", False):
        await controller_update(joycon.motionTimestamp, joycon.accelerometer, joycon.gyroscope, slot=pair_id * 2)

    gamepad.update()


async def controller_traitement(joycon, side, orientation, data, pair_id: int):
    """Process controller data for single Joy-Con mode"""
    state = get_pair_state(pair_id)

    isMouseMode = joycon.mouse["distance"] == "00" or joycon.mouse["distance"] == "01"
    # Check if mouse control is enabled for this pair
    mouse_enabled = is_mouse_enabled(pair_id)

    if mouse_enabled and state['firstCall'] == False and isMouseMode == True:
        threading.Thread(target=mouse_loop, args=(pair_id,), daemon=True).start()
        state['firstCall'] = True

    if joycon.orientation != orientation:
        joycon.orientation = orientation

    await joycon.update(data)
    await update(joycon, side, orientation, isMouseMode and mouse_enabled, pair_id)

    if mouse_enabled and isMouseMode:
        deltaX = (joycon.mouse["X"] - state['previousMouseX'] + 32768) % 65536 - 32768
        deltaY = (joycon.mouse["Y"] - state['previousMouseY'] + 32768) % 65536 - 32768
        state['previousMouseX'] = joycon.mouse["X"]
        state['previousMouseY'] = joycon.mouse["Y"]

        state['targetX'] += deltaX
        state['targetY'] += deltaY

        if joycon.mouseBtn["Left"] == True:
            if not state['leftPressed']:
                state['mouse'].press(Button.left)
            state['leftPressed'] = True
        else:
            if state['leftPressed']:
                state['mouse'].release(Button.left)
            state['leftPressed'] = False

        if joycon.mouseBtn["Right"] == True:
            if not state['rightPressed']:
                state['mouse'].press(Button.right)
            state['rightPressed'] = True
        else:
            if state['rightPressed']:
                state['mouse'].release(Button.right)
            state['rightPressed'] = False

        state['mouse'].scroll(joycon.mouseBtn["scrollX"] / 32768, joycon.mouseBtn["scrollY"] / 32768)

    # Latency calculation
    currentTime = time.time()
    elapsedTime = (currentTime - state['lastTime']) * 1000
    state['lastTime'] = currentTime


async def notify_single_joycons(client, side, orientation, data, pair_id: int):
    """Handle notifications for single Joy-Con mode"""
    state = get_pair_state(pair_id)
    manager = get_controller_manager()

    # Initialize joycon object if needed
    if state['joycon'] is None:
        if side == "Left":
            state['joycon'] = JoyConLeft()
        else:
            state['joycon'] = JoyConRight()
        state['side'] = side
        register_vibration(pair_id)

    mac = client.address.replace(":", "").replace("-", "").upper()

    await controller_traitement(state['joycon'], side, orientation, data, pair_id)

    # Update battery
    manager.update_battery(mac, int(state['joycon'].battery_level))

    return client
