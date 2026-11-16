from controllers.JoyconL import JoyConLeft
from controllers.JoyconR import JoyConRight

from dsu_server import controller_update
from control_type.mouse_scroll import (
    mouse_divisor as _mouse_divisor,
    scroll_notches,
    surface_threshold as _surface_threshold,
)
from control_type.rumble_stream import get_rumble_stream

from config import Config
from control_type.virtual_mouse import BTN_LEFT, BTN_RIGHT, get_mouse_output
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


# Per-pair Joy-Con instances (keyed by pair_id)
# Each pair gets its own JoyConLeft/JoyConRight to avoid cross-pair data corruption
_pair_joycons = {}  # pair_id -> {"Left": JoyConLeft, "Right": JoyConRight}


def _get_pair_joycons(pair_id: int):
    """Get or create Joy-Con instances for a specific pair"""
    if pair_id not in _pair_joycons:
        _pair_joycons[pair_id] = {
            "Left": JoyConLeft(),
            "Right": JoyConRight(),
        }
    return _pair_joycons[pair_id]


def reset_joycon_instances(pair_id: int = None):
    """Reset Joy-Con controller instances for a pair (called when reconnecting).

    If pair_id is None, resets all pairs (legacy behavior).
    """
    if pair_id is not None:
        if pair_id in _pair_joycons:
            _pair_joycons[pair_id] = {
                "Left": JoyConLeft(),
                "Right": JoyConRight(),
            }
    else:
        _pair_joycons.clear()


def reset_pair_joycons(pair_id: int):
    """Reset a specific pair's Joy-Con instances (called on disconnect)."""
    if pair_id in _pair_joycons:
        del _pair_joycons[pair_id]

# Store clients for vibration, keyed by pair_id -> {side: client}
vibration_clients = {}
# Track the exact gamepad object that owns each registered callback. A pair's
# virtual gamepad is recreated after a full disconnect, so pair_id alone is
# not sufficient for reconnect handling.
_vibration_registered_gamepads = {}
# Store event loop for thread-safe callback
_event_loop = None
# Per-pair vibration setting
_pair_vibration_enabled = {}

def set_vibration_enabled(enabled, pair_id: int = 0):
    """Set whether vibration feedback is enabled for one pair."""
    _pair_vibration_enabled[pair_id] = enabled

# Vibration callback function
async def send_vibration_to_client(pair_id, side, client, large_motor, small_motor):
    """Feed one XInput rumble update into this Joy-Con's HD Rumble stream.

    The old code wrote a single fixed stored effect (sample 0x01, a ~1 s
    buzz) to the command characteristic, merged both motors into one value,
    and used an invalid stop frame. Both motor channels are now preserved and
    the stream owns cadence, stopping and the amplitude cap.
    """
    if not getattr(client, "is_connected", False):
        return
    await get_rumble_stream().update(
        pair_id, side, client, large_motor, small_motor
    )


async def send_vibration(pair_id, large_motor, small_motor):
    """Two XInput motor channels -> independent HD Rumble streams per side."""
    pair_clients = vibration_clients.get(pair_id, {})
    tasks = []
    for side in ('Left', 'Right'):
        client = pair_clients.get(side)
        if client:
            tasks.append(
                send_vibration_to_client(
                    pair_id, side, client, large_motor, small_motor
                )
            )
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)

def vibration_callback(pair_id, client, target, large_motor, small_motor, led_number, user_data):
    """Callback for gamepad vibration feedback from vgamepad.

    Runs on vgamepad's thread. If a stream is already sending for this side,
    update its targets in place -- no event-loop hop. Only creating or
    restarting a stream needs the loop, and doing that on every callback
    starved the 12 ms sender (cadence fell to ~12 fps while writes took 0.7 ms).
    """
    if not _pair_vibration_enabled.get(pair_id, True):
        return

    global _event_loop
    stream = get_rumble_stream()
    clients = vibration_clients.get(pair_id, {})
    if clients and all(
        stream.update_sync(pair_id, side, c, large_motor, small_motor)
        for side, c in list(clients.items())
    ):
        return

    if _event_loop is not None:
        try:
            asyncio.run_coroutine_threadsafe(send_vibration(pair_id, large_motor, small_motor), _event_loop)
        except Exception as e:
            pass  # Silent fail

def _make_vibration_callback(pair_id):
    """Create a vgamepad-compatible vibration callback that captures pair_id via closure"""
    def callback(client, target, large_motor, small_motor, led_number, user_data):
        vibration_callback(pair_id, client, target, large_motor, small_motor, led_number, user_data)
    return callback

def register_vibration(client, side, pair_id: int = 0):
    """Register/update a client for vibration on a specific pair.

    Always updates the client reference (so reconnected Joy-Cons get
    their new client stored). Only registers the gamepad callback once
    per pair (vgamepad.register_notification).
    """
    if pair_id not in vibration_clients:
        vibration_clients[pair_id] = {}
    previous_client = vibration_clients[pair_id].get(side)
    vibration_clients[pair_id][side] = client
    if previous_client is not client:
        info(f"[VIBRATION] client updated: pair_id={pair_id} side={side}")

    # Register once per actual gamepad object. A reconnect can create a new
    # VX360Gamepad for the same pair_id and needs a fresh callback.
    from controller_manager import get_controller_manager
    manager = get_controller_manager()
    pair = manager.get_pair(pair_id)
    if pair and pair.gamepad:
        if _vibration_registered_gamepads.get(pair_id) is not pair.gamepad:
            try:
                pair.gamepad.register_notification(_make_vibration_callback(pair_id))
                _vibration_registered_gamepads[pair_id] = pair.gamepad
                info(f"[VIBRATION] callback registered on gamepad for pair_id={pair_id}")
            except Exception as e:
                error(f"[VIBRATION] register_notification failed: {e}")
    else:
        warning(f"[VIBRATION] cannot register: pair={pair is not None}, gamepad={pair.gamepad if pair else 'N/A'}")


def unregister_vibration(side: str, pair_id: int = 0):
    """Remove a client from vibration tracking (called on disconnect)."""
    try:
        get_rumble_stream().stop_sync(pair_id, side)
    except Exception as exc:
        debug(f"[RUMBLE] stop on unregister failed: {exc}")

    if pair_id in vibration_clients and side in vibration_clients[pair_id]:
        del vibration_clients[pair_id][side]
        info(f"[VIBRATION] unregistered side={side} from pair_id={pair_id}")
        # If both sides are gone, clean up the pair entry entirely
        if not vibration_clients[pair_id]:
            del vibration_clients[pair_id]
            _vibration_registered_gamepads.pop(pair_id, None)


# Per-pair update locks to serialize gamepad access from Left/Right notifications
_pair_update_locks = {}


def _get_pair_update_lock(pair_id: int):
    """Get or create an asyncio lock for serializing update() calls per pair."""
    if pair_id not in _pair_update_locks:
        _pair_update_locks[pair_id] = asyncio.Lock()
    return _pair_update_locks[pair_id]


# Per-pair state for duo mode
pair_state = {}
# Lock to protect pair_state dict fields from concurrent read-modify-write
# between mouse_loop (thread) and update() (event loop)
_pair_state_lock = threading.RLock()
_mouse_loop_thread = None
_mouse_loop_start_lock = threading.Lock()
_mouse_wakeup = threading.Event()
_mouse_stop = threading.Event()

# Per-pair mouse mode override (set from the GUI checkbox). Unset pairs follow
# config.ini's mouse_mode, which config.py has always parsed but nothing ever
# read: 0 disabled, 1 automatic (lift off the surface to switch), 2 always on.
pair_mouse_enabled = {}
_pair_mouse_mode = {}

# Per-pair DSU motion streaming. Unset pairs fall back to the global config
# flag so existing installs keep working without touching config.ini.
_pair_dsu_enabled = {}

# Xbox signed axis units (-32768..32767). The old value of 3000 swallowed
# roughly 9% of the stick range; with a learned centre the residual noise
# only needs a light guard.
STICK_DEADZONE = 1200

# Report 0x05 offset 0x16: ~117-158 on a desk, ~3083-3321 when lifted.
SURFACE_DISTANCE_MAX = 512


def set_dsu_enabled(pair_id: int, enabled: bool):
    _pair_dsu_enabled[pair_id] = bool(enabled)


def is_dsu_enabled(pair_id: int) -> bool:
    if pair_id in _pair_dsu_enabled:
        return _pair_dsu_enabled[pair_id]
    return bool(Config().enable_dsu)


def get_pair_state(pair_id: int):
    """Get or create state for a pair"""
    with _pair_state_lock:
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


def mouse_loop():
    """Global mouse loop - handles all pairs until stop_mouse_loop()."""
    while not _mouse_stop.is_set():
        # Read once per tick: Config() is a singleton, so this is an attribute
        # access, and it lets a config change take effect without a restart.
        divisor = _mouse_divisor()
        movements = []
        with _pair_state_lock:
            for state in pair_state.values():
                # Truncate towards zero and always consume a non-zero remainder.
                # ``//`` made tiny positive moves disappear and biased negative
                # moves, which made pointer control feel delayed and uneven.
                stepX = int(state['targetX'] / divisor)
                stepY = int(state['targetY'] / divisor)
                if stepX == 0 and state['targetX']:
                    stepX = 1 if state['targetX'] > 0 else -1
                if stepY == 0 and state['targetY']:
                    stepY = 1 if state['targetY'] > 0 else -1
                if stepX != 0 or stepY != 0:
                    state['targetX'] -= stepX
                    state['targetY'] -= stepY
                else:
                    continue
                movements.append((stepX, stepY))
        # pynput can block; do not hold the state lock while calling it.
        if movements:
            for stepX, stepY in movements:
                get_mouse_output().move(stepX, stepY)
            time.sleep(0.006)
        else:
            # Timeout lets the loop notice stop_mouse_loop() while idle.
            _mouse_wakeup.wait(timeout=0.2)
            _mouse_wakeup.clear()


def stop_mouse_loop():
    """Signal the global mouse loop to exit and wait for its thread."""
    global _mouse_loop_thread
    _mouse_stop.set()
    _mouse_wakeup.set()
    with _mouse_loop_start_lock:
        thread = _mouse_loop_thread
        _mouse_loop_thread = None
    if (thread is not None and thread.is_alive()
            and thread is not threading.current_thread()):
        thread.join(timeout=2.0)




def cleanup_disconnected_joycon(pair_id: int, side: str, pair_empty: bool = False):
    """Clear cached input/mouse state after a Joy-Con disconnects."""
    if pair_empty:
        _pair_joycons.pop(pair_id, None)
    elif pair_id in _pair_joycons and side in ("Left", "Right"):
        _pair_joycons[pair_id][side] = JoyConLeft() if side == "Left" else JoyConRight()

    with _pair_state_lock:
        state = pair_state.get(pair_id)
        if state is not None:
            if state['leftPressed']:
                get_mouse_output().button(BTN_LEFT, False)
            if state['rightPressed']:
                get_mouse_output().button(BTN_RIGHT, False)
            state['leftPressed'] = False
            state['rightPressed'] = False
            state['targetX'] = 0
            state['targetY'] = 0
            if pair_empty or state['joyconMouseMode'] == side:
                state['joyconMouseMode'] = None
            if pair_empty:
                pair_state.pop(pair_id, None)

    if pair_empty:
        _pair_update_locks.pop(pair_id, None)


async def update(pair_id: int = 0, updated_side: str = None):
    # Serialize per-pair updates so Left and Right notifications don't
    # interleave gamepad writes across an await boundary.
    async with _get_pair_update_lock(pair_id):
        from controller_manager import get_controller_manager
        manager = get_controller_manager()
        pair = manager.get_pair(pair_id)
        if not pair or not pair.gamepad:
            return

        gamepad = pair.gamepad
        state = get_pair_state(pair_id)
        controls = get_pair_controls(pair_id)

        # Get per-pair Joy-Con instances
        pair_joycons = _get_pair_joycons(pair_id)
        joyconLeft = pair_joycons["Left"]
        joyconRight = pair_joycons["Right"]

        # Check if mouse control is enabled for this pair
        mouse_enabled = is_mouse_enabled(pair_id)

        # Check mouse mode from both Joy-Cons. Mode 2 ("always") skips the
        # distance sensor entirely; with both halves lying flat the left one
        # wins, matching the automatic path's preference.
        always_on = is_mouse_always(pair_id)
        threshold = _surface_threshold()
        isMouseModeLeft = always_on or (
            joyconLeft.mouse.get("distance_raw", 0xFFFF) < threshold
        )
        isMouseModeRight = always_on or (
            joyconRight.mouse.get("distance_raw", 0xFFFF) < threshold
        )
        
        previous_mouse_mode = state['joyconMouseMode']
        if not mouse_enabled:
            state['joyconMouseMode'] = None
        else:
            current = state['joyconMouseMode']
            # Keep whichever side is actually on a surface, otherwise switch to
            # the one that just landed, otherwise give up the mode.
            #
            # The previous two-branch form pinned the mode to "Left" whenever the
            # left half lifted while the right one was being used (neither branch
            # matched), so pointer input froze on a Joy-Con that was in the air.
            if current == "Left" and isMouseModeLeft:
                pass
            elif current == "Right" and isMouseModeRight:
                pass
            elif isMouseModeLeft:
                state['joyconMouseMode'] = "Left"
            elif isMouseModeRight:
                state['joyconMouseMode'] = "Right"
            else:
                state['joyconMouseMode'] = None

        if previous_mouse_mode != state['joyconMouseMode']:
            current_joycon = joyconLeft if state['joyconMouseMode'] == "Left" else joyconRight
            with _pair_state_lock:
                state['previousMouseX'] = current_joycon.mouse['X']
                state['previousMouseY'] = current_joycon.mouse['Y']
                state['targetX'] = 0
                state['targetY'] = 0
            if state['joyconMouseMode'] is None:
                if state['leftPressed']:
                    get_mouse_output().button(BTN_LEFT, False)
                if state['rightPressed']:
                    get_mouse_output().button(BTN_RIGHT, False)
                state['leftPressed'] = False
                state['rightPressed'] = False

        global _mouse_loop_thread
        if mouse_enabled and state['joyconMouseMode'] is not None:
            with _mouse_loop_start_lock:
                if _mouse_loop_thread is None or not _mouse_loop_thread.is_alive():
                    # Re-arm in case a previous shutdown set the stop flag.
                    _mouse_stop.clear()
                    _mouse_loop_thread = threading.Thread(target=mouse_loop, daemon=True)
                    _mouse_loop_thread.start()

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
            # Light guard only; the learned centre removes the need for a
            # large deadzone that used to eat fine stick movement.
            DEADZONE = STICK_DEADZONE
            if abs(left_x) < DEADZONE:
                left_x = 0
            if abs(left_y) < DEADZONE:
                left_y = 0
            gamepad.left_joystick(left_x, left_y)
            
        if state['joyconMouseMode'] != "Right":
            # Convert 0-32767 (Joy-Con format) to -32768-32767 (Xbox format)
            right_x_raw = min(joyconRight.analog_stick["X"], 32767)
            right_y_raw = min(joyconRight.analog_stick["Y"], 32767)
            right_x = int((right_x_raw - 16384) * 2)
            right_y = int((right_y_raw - 16384) * 2)
            right_x = max(-32768, min(32767, right_x))
            right_y = max(-32768, min(32767, right_y))
            # Light guard only; the learned centre removes the need for a
            # large deadzone that used to eat fine stick movement.
            DEADZONE = STICK_DEADZONE
            if abs(right_x) < DEADZONE:
                right_x = 0
            if abs(right_y) < DEADZONE:
                right_y = 0
            gamepad.right_joystick(right_x, right_y)

        gamepad.update()

        # Motion must stream on every report regardless of mouse mode or which
        # stick branch ran. Previously entering mouse mode silently froze the
        # DSU timestamp and emulators saw a dead gyro.
        if is_dsu_enabled(pair_id):
            if updated_side != "Right":
                await controller_update(
                    joyconLeft.motionTimestamp,
                    joyconLeft.accelerometer,
                    joyconLeft.gyroscope,
                    slot=pair_id * 2,
                )
            if updated_side != "Left":
                await controller_update(
                    joyconRight.motionTimestamp,
                    joyconRight.accelerometer,
                    joyconRight.gyroscope,
                    slot=pair_id * 2 + 1,
                )

        # Handle mouse movement based on which Joy-Con is in mouse mode
        if state['joyconMouseMode'] == "Left":
            joycon = joyconLeft
        elif state['joyconMouseMode'] == "Right":
            joycon = joyconRight
        else:
            joycon = None
        
        if joycon is not None:
            # Protect targetX/targetY read-modify-write from mouse_loop thread
            with _pair_state_lock:
                deltaX = (joycon.mouse["X"] - state['previousMouseX'] + 32768) % 65536 - 32768
                deltaY = (joycon.mouse["Y"] - state['previousMouseY'] + 32768) % 65536 - 32768
                state['previousMouseX'] = joycon.mouse["X"]
                state['previousMouseY'] = joycon.mouse["Y"]

                state['targetX'] += deltaX
                state['targetY'] += deltaY
                if deltaX or deltaY:
                    _mouse_wakeup.set()

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


async def notify_duo_joycons(client, side, data, pair_id: int = 0):
    global _event_loop
    if _event_loop is None:
        _event_loop = asyncio.get_running_loop()

    # Sensor notifications arrive many times per second. Only touch vibration
    # registration when the BLE client object actually changes.
    if vibration_clients.get(pair_id, {}).get(side) is not client:
        register_vibration(client, side, pair_id)

    # Get per-pair Joy-Con instances
    pair_joycons = _get_pair_joycons(pair_id)

    if side == "Left":
        # Sync orientation from JoyConInfo to the JoyCon instance
        from controller_manager import get_controller_manager
        manager = get_controller_manager()
        pair = manager.get_pair(pair_id)
        if pair and pair.left.is_connected:
            pair_joycons["Left"].orientation = pair.left.orientation

        await pair_joycons["Left"].update(data)
        await update(pair_id, "Left")
    elif side == "Right":
        # Sync orientation from JoyConInfo to the JoyCon instance
        from controller_manager import get_controller_manager
        manager = get_controller_manager()
        pair = manager.get_pair(pair_id)
        if pair and pair.right.is_connected:
            pair_joycons["Right"].orientation = pair.right.orientation

        await pair_joycons["Right"].update(data)
        await update(pair_id, "Right")
    else:
        warning("Unknown controller side.")

    return client
