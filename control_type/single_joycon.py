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
_pair_state_lock = threading.RLock()
_mouse_threads = {}
_mouse_events = {}

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
    with _pair_state_lock:
        if pair_id not in pair_state:
            pair_state[pair_id] = _new_pair_state()
        return pair_state[pair_id]


def _new_pair_state():
    return {
        'joycon': None,
        'side': None,
        'mouse': Controller(),
        'targetX': 0,
        'targetY': 0,
        'previousMouseX': 0,
        'previousMouseY': 0,
        'leftPressed': False,
        'rightPressed': False,
        'mouse_mode_active': False,
        'lastTime': time.time(),
    }


def reset_pair_state(pair_id: int):
    """Reset state for a pair (called when reconnecting)"""
    with _pair_state_lock:
        if pair_id in pair_state:
            old_state = pair_state[pair_id]
            if old_state['leftPressed']:
                old_state['mouse'].release(Button.left)
            if old_state['rightPressed']:
                old_state['mouse'].release(Button.right)
            pair_state[pair_id] = _new_pair_state()
            _mouse_events.setdefault(pair_id, threading.Event()).set()


# Per-pair vibration setting
_pair_vibration_enabled = {}


def set_vibration_enabled(enabled, pair_id: int = 0):
    """Set whether vibration feedback is enabled for one pair."""
    _pair_vibration_enabled[pair_id] = enabled


async def send_vibration_to_client(client, large_motor, small_motor):
    """Send vibration command to a specific Joy-Con client"""
    try:
        if not client.is_connected:
            print(f"[VIBRATION] client not connected, skipping vibration")
            return

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


# Reuse the BLE notification loop instead of maintaining another permanent
# event-loop thread solely for vibration writes.
_event_loop = None
_vibration_registered_gamepads = {}

def vibration_callback(client, target, large_motor, small_motor, led_number, user_data):
    """Callback for gamepad vibration feedback from vgamepad"""
    pair_id = user_data if user_data is not None else 0
    if not _pair_vibration_enabled.get(pair_id, True):
        return
    
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
    
    if target_client and _event_loop is not None:
        try:
            asyncio.run_coroutine_threadsafe(
                send_vibration_to_client(target_client, large_motor, small_motor),
                _event_loop
            )
        except Exception as e:
            pass  # Silent fail


def register_vibration(pair_id: int):
    """Register vibration callback for a pair"""
    manager = get_controller_manager()
    pair = manager.get_pair(pair_id)
    if (pair and pair.gamepad
            and _vibration_registered_gamepads.get(pair_id) is not pair.gamepad):
        pair.gamepad.register_notification(lambda client, target, large_motor, small_motor, led_number, user_data: vibration_callback(client, target, large_motor, small_motor, led_number, pair_id))
        _vibration_registered_gamepads[pair_id] = pair.gamepad


def mouse_loop(pair_id: int):
    """Mouse movement loop for a pair"""
    with _pair_state_lock:
        wakeup = _mouse_events.setdefault(pair_id, threading.Event())
    while True:
        # Re-fetch state every iteration so reconnect/reset does not leave this
        # thread operating on an orphaned dictionary.
        with _pair_state_lock:
            state = get_pair_state(pair_id)
            stepX = int(state['targetX'] / 6)
            stepY = int(state['targetY'] / 6)
            if stepX == 0 and state['targetX']:
                stepX = 1 if state['targetX'] > 0 else -1
            if stepY == 0 and state['targetY']:
                stepY = 1 if state['targetY'] > 0 else -1
            if stepX != 0 or stepY != 0:
                state['targetX'] -= stepX
                state['targetY'] -= stepY
                mouse_controller = state['mouse']
            else:
                mouse_controller = None
        if mouse_controller is not None:
            mouse_controller.move(stepX, stepY)
            time.sleep(0.006)
        else:
            wakeup.wait()
            wakeup.clear()


async def update(joycon, side, orientation, isInMouse, pair_id: int):
    """Update gamepad state for a specific pair"""
    state = get_pair_state(pair_id)
    controls = get_pair_controls(pair_id)
    manager = get_controller_manager()
    pair = manager.get_pair(pair_id)

    if not pair:
        return

    gamepad = pair.gamepad
    
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

    if Config().enable_dsu:
        slot = pair_id * 2 + (1 if side == "Right" else 0)
        await controller_update(joycon.motionTimestamp, joycon.accelerometer, joycon.gyroscope, slot=slot)

    gamepad.update()


async def controller_traitement(joycon, side, orientation, data, pair_id: int):
    """Process controller data for single Joy-Con mode"""
    state = get_pair_state(pair_id)

    if joycon.orientation != orientation:
        joycon.orientation = orientation

    await joycon.update(data)

    # Determine mode from this report, not the previous report.
    isMouseMode = joycon.mouse["distance"] in ("00", "01")
    mouse_enabled = is_mouse_enabled(pair_id)
    if mouse_enabled and isMouseMode:
        with _pair_state_lock:
            mouse_thread = _mouse_threads.get(pair_id)
            if mouse_thread is None or not mouse_thread.is_alive():
                mouse_thread = threading.Thread(target=mouse_loop, args=(pair_id,), daemon=True)
                _mouse_threads[pair_id] = mouse_thread
                mouse_thread.start()

    await update(joycon, side, orientation, isMouseMode and mouse_enabled, pair_id)

    mouse_active = mouse_enabled and isMouseMode
    if mouse_active:
        with _pair_state_lock:
            if not state['mouse_mode_active']:
                # Establish a baseline when entering mouse mode so stale input
                # coordinates cannot produce a one-frame cursor jump.
                state['previousMouseX'] = joycon.mouse['X']
                state['previousMouseY'] = joycon.mouse['Y']
                state['targetX'] = 0
                state['targetY'] = 0
                state['mouse_mode_active'] = True
                deltaX = deltaY = 0
            else:
                deltaX = (joycon.mouse["X"] - state['previousMouseX'] + 32768) % 65536 - 32768
                deltaY = (joycon.mouse["Y"] - state['previousMouseY'] + 32768) % 65536 - 32768
                state['previousMouseX'] = joycon.mouse["X"]
                state['previousMouseY'] = joycon.mouse["Y"]
            state['targetX'] += deltaX
            state['targetY'] += deltaY
            if deltaX or deltaY:
                _mouse_events.setdefault(pair_id, threading.Event()).set()

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

        scroll_x = int(joycon.mouseBtn["scrollX"] / 32768)
        scroll_y = int(joycon.mouseBtn["scrollY"] / 32768)
        if scroll_x or scroll_y:
            state['mouse'].scroll(scroll_x, scroll_y)
    else:
        with _pair_state_lock:
            if state['leftPressed']:
                state['mouse'].release(Button.left)
            if state['rightPressed']:
                state['mouse'].release(Button.right)
            state['leftPressed'] = False
            state['rightPressed'] = False
            state['mouse_mode_active'] = False

    # Latency calculation
    currentTime = time.time()
    elapsedTime = (currentTime - state['lastTime']) * 1000
    state['lastTime'] = currentTime


async def notify_single_joycons(client, side, orientation, data, pair_id: int):
    """Handle notifications for single Joy-Con mode"""
    global _event_loop
    if _event_loop is None or _event_loop.is_closed():
        _event_loop = asyncio.get_running_loop()
    state = get_pair_state(pair_id)
    manager = get_controller_manager()
    pair = manager.get_pair(pair_id)
    if pair:
        # Read the current GUI-controlled orientation on every report rather
        # than retaining the value captured when notifications were started.
        orientation = pair.left.orientation if side == "Left" else pair.right.orientation

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

    # Only publish a verified battery value. Unknown must not become 0%.
    if state['joycon'].battery_level is not None:
        manager.update_battery(mac, int(state['joycon'].battery_level))

    return client
