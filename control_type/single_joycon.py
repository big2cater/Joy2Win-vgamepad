from controllers.JoyconL import JoyConLeft
from controllers.JoyconR import JoyConRight

from dsu_server import controller_update
from controller_manager import get_controller_manager
from control_type.mouse_scroll import (
    mouse_divisor as _mouse_divisor,
    scroll_notches,
    surface_threshold as _surface_threshold,
)
from control_type.rumble_stream import get_rumble_stream

from config import Config
from control_type.virtual_mouse import BTN_LEFT, BTN_RIGHT, get_mouse_output

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
                # R3 is the right stick's click; Vertical already maps it to
                # RIGHT_THUMB, so Horizontal mapping it to LEFT_THUMB was a
                # copy-paste slip.
                "R3": vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_THUMB,
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
_mouse_stop_events = {}

# Per-pair mouse enabled state (set from GUI)
pair_mouse_enabled = {}
# Explicit per-pair override of config.mouse_mode (GUI checkbox). Unset pairs
# follow config.ini: 0 disabled, 1 automatic, 2 always on.
_pair_mouse_mode = {}

# Per-pair DSU motion streaming; unset pairs fall back to the global flag.
_pair_dsu_enabled = {}
STICK_DEADZONE = 1200
SURFACE_DISTANCE_MAX = 512


def set_dsu_enabled(pair_id: int, enabled: bool):
    _pair_dsu_enabled[pair_id] = bool(enabled)


def is_dsu_enabled(pair_id: int) -> bool:
    if pair_id in _pair_dsu_enabled:
        return _pair_dsu_enabled[pair_id]
    return bool(Config().enable_dsu)


def _config_mouse_mode() -> int:
    try:
        mode = int(Config().mouse_mode)
    except Exception:
        return 0
    return mode if mode in (0, 1, 2) else 0


def mouse_mode(pair_id: int) -> int:
    """Effective mode: the GUI override if present, else config.ini."""
    return _pair_mouse_mode.get(pair_id, _config_mouse_mode())


def set_mouse_enabled(pair_id: int, enabled: bool):
    """GUI checkbox. Ticking it means automatic switching, not "always on"."""
    _pair_mouse_mode[pair_id] = 1 if enabled else 0
    pair_mouse_enabled[pair_id] = enabled


def is_mouse_enabled(pair_id: int) -> bool:
    """Check if mouse control is enabled for a specific pair"""
    return mouse_mode(pair_id) != 0


def is_mouse_always(pair_id: int) -> bool:
    """Mouse mode on regardless of the surface-distance sensor."""
    return mouse_mode(pair_id) == 2


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
        'mouse': None,
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
                get_mouse_output().button(BTN_LEFT, False)
            if old_state['rightPressed']:
                get_mouse_output().button(BTN_RIGHT, False)
            pair_state[pair_id] = _new_pair_state()
            _mouse_events.setdefault(pair_id, threading.Event()).set()


# Per-pair vibration setting
_pair_vibration_enabled = {}


def set_vibration_enabled(enabled, pair_id: int = 0):
    """Set whether vibration feedback is enabled for one pair."""
    _pair_vibration_enabled[pair_id] = enabled


async def send_vibration_to_client(pair_id, side, client, large_motor, small_motor):
    """Feed one XInput rumble update into this Joy-Con's HD Rumble stream."""
    if not getattr(client, "is_connected", False):
        return
    await get_rumble_stream().update(
        pair_id, side, client, large_motor, small_motor
    )


# Reuse the BLE notification loop instead of maintaining another permanent
# event-loop thread solely for vibration writes.
_event_loop = None
_vibration_registered_gamepads = {}

def vibration_callback(client, target, large_motor, small_motor, led_number, user_data):
    """Callback for gamepad vibration feedback from vgamepad.

    Steady state must not hop into the event loop: doing that on every callback
    starved the 12 ms rumble sender (measured 12 fps despite 0.7 ms writes).
    """
    pair_id = user_data if user_data is not None else 0
    if not _pair_vibration_enabled.get(pair_id, True):
        return
    
    manager = get_controller_manager()
    pair = manager.get_pair(pair_id)
    if not pair:
        return
    
    # In single Joy-Con mode, check which Joy-Con is connected
    target_client = None
    target_side = None
    if pair.left.is_connected and pair.left.client:
        target_client, target_side = pair.left.client, "Left"
    elif pair.right.is_connected and pair.right.client:
        target_client, target_side = pair.right.client, "Right"

    if not (target_client and target_side):
        return

    if get_rumble_stream().update_sync(
        pair_id, target_side, target_client, large_motor, small_motor
    ):
        return

    if _event_loop is not None:
        try:
            asyncio.run_coroutine_threadsafe(
                send_vibration_to_client(
                    pair_id, target_side, target_client,
                    large_motor, small_motor
                ),
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


def mouse_loop(pair_id: int, stop_event=None):
    """Mouse movement loop for a pair until its stop event is set."""
    with _pair_state_lock:
        wakeup = _mouse_events.setdefault(pair_id, threading.Event())
    while stop_event is None or not stop_event.is_set():
        # Re-fetch state every iteration so reconnect/reset does not leave this
        # thread operating on an orphaned dictionary.
        divisor = _mouse_divisor()
        with _pair_state_lock:
            state = get_pair_state(pair_id)
            stepX = int(state['targetX'] / divisor)
            stepY = int(state['targetY'] / divisor)
            if stepX == 0 and state['targetX']:
                stepX = 1 if state['targetX'] > 0 else -1
            if stepY == 0 and state['targetY']:
                stepY = 1 if state['targetY'] > 0 else -1
            if stepX != 0 or stepY != 0:
                state['targetX'] -= stepX
                state['targetY'] -= stepY
                should_move = True
            else:
                should_move = False
        if should_move:
            get_mouse_output().move(stepX, stepY)
            time.sleep(0.006)
        else:
            # Timeout lets the loop notice stop_mouse_loops() while idle.
            wakeup.wait(timeout=0.2)
            wakeup.clear()


def stop_mouse_loops():
    """Stop every per-pair mouse loop and wait for the threads to exit."""
    for event in list(_mouse_stop_events.values()):
        event.set()
    for wakeup in list(_mouse_events.values()):
        wakeup.set()
    for thread in list(_mouse_threads.values()):
        if (thread is not None and thread.is_alive()
                and thread is not threading.current_thread()):
            thread.join(timeout=2.0)
    _mouse_threads.clear()


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
        
        # Light guard only; the learned stick centre removes drift at source.
        DEADZONE = STICK_DEADZONE
        if abs(stick_x) < DEADZONE:
            stick_x = 0
        if abs(stick_y) < DEADZONE:
            stick_y = 0
        
        gamepad.left_joystick(stick_x, stick_y)

    if is_dsu_enabled(pair_id):
        slot = pair_id * 2 + (1 if side == "Right" else 0)
        await controller_update(joycon.motionTimestamp, joycon.accelerometer, joycon.gyroscope, slot=slot)

    gamepad.update()


async def controller_traitement(joycon, side, orientation, data, pair_id: int):
    """Process controller data for single Joy-Con mode"""
    state = get_pair_state(pair_id)

    if joycon.orientation != orientation:
        joycon.orientation = orientation

    await joycon.update(data)

    # Determine mode from this report, not the previous report. The numeric
    # lift-off distance is more robust than the legacy high-byte hex check.
    isMouseMode = is_mouse_always(pair_id) or (
        joycon.mouse.get("distance_raw", 0xFFFF) < _surface_threshold()
    )
    mouse_enabled = is_mouse_enabled(pair_id)
    if mouse_enabled and isMouseMode:
        with _pair_state_lock:
            mouse_thread = _mouse_threads.get(pair_id)
            if mouse_thread is None or not mouse_thread.is_alive():
                stop_event = _mouse_stop_events.get(pair_id)
                if stop_event is None:
                    stop_event = threading.Event()
                    _mouse_stop_events[pair_id] = stop_event
                stop_event.clear()
                mouse_thread = threading.Thread(
                    target=mouse_loop, args=(pair_id, stop_event), daemon=True
                )
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
                get_mouse_output().button(BTN_LEFT, True)
            state['leftPressed'] = True
        else:
            if state['leftPressed']:
                get_mouse_output().button(BTN_LEFT, False)
            state['leftPressed'] = False

        if joycon.mouseBtn["Right"] == True:
            if not state['rightPressed']:
                get_mouse_output().button(BTN_RIGHT, True)
            state['rightPressed'] = True
        else:
            if state['rightPressed']:
                get_mouse_output().button(BTN_RIGHT, False)
            state['rightPressed'] = False

        with _pair_state_lock:
            notches_x = scroll_notches(
                state, 'scrollAccX', joycon.mouseBtn["scrollX"]
            )
            notches_y = scroll_notches(
                state, 'scrollAccY', joycon.mouseBtn["scrollY"]
            )
        if notches_x or notches_y:
            get_mouse_output().scroll(notches_x, notches_y)
    else:
        with _pair_state_lock:
            if state['leftPressed']:
                get_mouse_output().button(BTN_LEFT, False)
            if state['rightPressed']:
                get_mouse_output().button(BTN_RIGHT, False)
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

    await controller_traitement(state['joycon'], side, orientation, data, pair_id)

    # Battery is published by main.handle_power_report (native 0-9 level) or
    # the init-time voltage fallback. The legacy JoyCon*.battery_level field is
    # never written, so the old call here was dead code -- and would have
    # overwritten is_charging/external_power with False if it ever ran.
    return client
