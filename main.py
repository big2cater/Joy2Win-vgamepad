import asyncio, os, platform, time
from typing import Optional
from bleak import BleakClient, BleakScanner
from config import Config
from controller_command import (
    ControllerCommand,
    UUID_NOTIFY,
    UUID_CMD_RESPONSE,
    UUID_POWER_LEFT,
    UUID_POWER_RIGHT,
)
from dsu_server import main_dsu
from controller_manager import get_controller_manager, ControllerMode
from logger_config import info, warning, error, debug
from controllers.battery import battery_percentage_from_voltage

# Check if the operating system is Windows
if(os.name != 'nt'):
    error("This application is only supported on Windows.")
    exit(1)

manufact = {
    "id": 0x0553,  # Nintendo Co., Ltd.
    "data-prefix": bytes([0x01, 0x00, 0x03, 0x7e, 0x05])
}

# Switch 2 controller product IDs, little-endian at manufacturer-data bytes
# 5..6 (right after the 5-byte prefix above). jacc/joy2con reads the same
# field, and also finds it in the controller's flash at 0x13000 + 0x14.
SIDE_BY_PID = {0x2067: "Left", 0x2066: "Right", 0x2069: "Pro"}


def side_from_advertisement(data) -> str:
    """Read the controller product ID from a Nintendo advertisement.

    Returns "Left"/"Right"/"Pro", or "Unknown". Available before connecting,
    so the scan result can already say which half was found -- a Joy-Con 2
    advertisement carries no "Left"/"Right" in its name.
    """
    if not data or len(data) < 7:
        return "Unknown"
    pid = data[5] | (data[6] << 8)
    return SIDE_BY_PID.get(pid, "Unknown")

# Global state
_connected_devices = {}  # mac_address -> (client, side, pair_id)
_main_event_loop = None  # Reference to main event loop for callbacks
_notification_error_last = {}
_timer_resolution_raised = False


def raise_timer_resolution(period_ms: int = 1) -> bool:
    """Ask Windows for a 1 ms timer period.

    asyncio.sleep() is rounded up to the system timer tick, which is 15.6 ms by
    default. A 12 ms rumble cadence therefore measured 43 fps (~23 ms per frame)
    with max write time stuck at 16.0 ms: the packet carries ~12 ms of haptics,
    the rest of the period is silence, and a Joy-Con fills that gap by
    repeating the last frame -- audible as a stutter. timeBeginPeriod(1) is the
    documented way to get millisecond scheduling (Switch2Connect does the same).
    """
    global _timer_resolution_raised
    if platform.system() != "Windows":
        return False
    try:
        import ctypes
        result = ctypes.WinDLL("winmm").timeBeginPeriod(period_ms)
        _timer_resolution_raised = (result == 0)
        if _timer_resolution_raised:
            info(f"Windows timer resolution raised to {period_ms} ms")
        else:
            warning(f"timeBeginPeriod({period_ms}) returned {result}; rumble "
                    f"cadence will be rounded to the 15.6 ms system tick")
        return _timer_resolution_raised
    except Exception as exc:
        warning(f"timeBeginPeriod failed: {type(exc).__name__}: {exc}; rumble "
                f"cadence will be rounded to the 15.6 ms system tick")
        return False


def restore_timer_resolution():
    """Give the 15.6 ms default back so the rest of the OS behaves normally."""
    global _timer_resolution_raised
    if not _timer_resolution_raised:
        return
    try:
        import ctypes
        ctypes.WinDLL("winmm").timeEndPeriod(1)
    except Exception as exc:
        debug(f"timeEndPeriod failed: {type(exc).__name__}: {exc}")
    _timer_resolution_raised = False
_low_battery_counts = {}
_low_battery_alerted = set()
LOW_BATTERY_PERCENT = 20
LOW_BATTERY_RECOVERY_PERCENT = 30
LOW_BATTERY_CONFIRM_REPORTS = 3
# Bleak fires disconnected_callback for both unsolicited and explicit
# disconnects. Without this set the explicit path and the callback race to
# clean up the same pair, which is what made connecting a second Joy-Con drop
# both controllers.
_intentional_disconnects = set()

# GATT descriptor for report-rate tuning, documented in
# ndeadly/switch2_controller_research/bluetooth_interface.md. Writing 0x85 00
# selects the high report rate on all Switch 2 controllers.
UUID_REPORT_RATE = "679d5510-5a24-4dee-9557-95df80486ecb"


def log_notification_error(key: str, exc: Exception, interval: float = 5.0):
    """Log recurring BLE notification failures at a bounded rate."""
    now = time.monotonic()
    if now - _notification_error_last.get(key, 0) >= interval:
        _notification_error_last[key] = now
        warning(f"{key}: {type(exc).__name__}: {exc}")


def set_event_loop(loop):
    """Set the main event loop reference for use in callbacks"""
    global _main_event_loop
    _main_event_loop = loop


def get_event_loop():
    """Get the main event loop"""
    return _main_event_loop


def get_mac_from_device(device):
    """Extract MAC address from device"""
    return device.address.replace(":", "").replace("-", "").upper()


def _normalize_mac(mac: str) -> str:
    """One canonical MAC format everywhere (colon/dash/compact differ)."""
    return (mac or "").replace(":", "").replace("-", "").upper()


def get_power_report_uuid(side: str):
    if side == "Left":
        return UUID_POWER_LEFT
    if side == "Right":
        return UUID_POWER_RIGHT
    raise ValueError(f"Unknown Joy-Con side: {side}")


def get_player_led_value(pair_id: int):
    if not 0 <= pair_id < 4:
        raise ValueError(f"Invalid pair_id: {pair_id}")
    return format(1 << pair_id, 'x')


def handle_power_report(mac: str, data, side: str = "Joy-Con 2"):
    """Decode Joy-Con 2 report 0x07/0x08 power information."""
    if len(data) < 2:
        return
    power_info = data[1]
    external_power = bool(power_info & 0x01)
    is_charging = bool(power_info & 0x02)
    battery_units = (power_info >> 2) & 0x0F
    if battery_units > 9:
        debug(f"Ignoring invalid Joy-Con 2 battery level: {battery_units}")
        return
    battery_level = round(battery_units * 100 / 9)
    get_controller_manager().update_battery(
        mac,
        battery_level,
        is_charging=is_charging,
        external_power=external_power,
    )
    info(f"Joy-Con 2 {side} battery level: {battery_units}/9 ({battery_level}%)")
    _update_low_battery_alert(mac, side, battery_level, is_charging)


def _update_low_battery_alert(mac, side, battery_level, is_charging):
    """Log one low-battery warning after several consecutive low reports.

    Deliberately no message box: the old notify_low_battery() path opened a
    modal dialog from a BLE callback thread, which blocked input handling.
    GUI shows the level via its colour bar; this is the non-intrusive notice.
    """
    mac = _normalize_mac(mac)
    if battery_level <= LOW_BATTERY_PERCENT and not is_charging:
        _low_battery_counts[mac] = _low_battery_counts.get(mac, 0) + 1
        if (_low_battery_counts[mac] >= LOW_BATTERY_CONFIRM_REPORTS
                and mac not in _low_battery_alerted):
            _low_battery_alerted.add(mac)
            warning(
                f"{side} Joy-Con {mac} battery low ({battery_level}%), please charge"
            )
        return
    _low_battery_counts.pop(mac, None)
    if battery_level >= LOW_BATTERY_RECOVERY_PERCENT:
        _low_battery_alerted.discard(mac)


async def capture_power_level(client, side: str, mac: str, timeout: float = 3.0):
    """Capture one native 0-9 battery report before selecting report 0x05.

    Keeping report 0x07/0x08 subscribed after sensor initialisation can stop the
    main button/IMU stream on real controllers. A short pre-initialisation
    subscription obtains the controller's own state-of-charge value and is
    removed before report 0x05 is enabled.
    """
    received = asyncio.Event()

    def power_handler(sender, data):
        try:
            handle_power_report(mac, data, side)
            received.set()
        except Exception as exc:
            debug(f"Failed to decode {side} power report: {exc}")

    uuid = get_power_report_uuid(side)
    started = False
    try:
        await client.start_notify(uuid, power_handler)
        started = True
        await asyncio.wait_for(received.wait(), timeout=timeout)
        return True
    except asyncio.TimeoutError:
        debug(f"Timed out waiting for {side} native battery report")
        return False
    except Exception as exc:
        debug(f"Unable to capture {side} native battery report: {exc}")
        return False
    finally:
        if started:
            try:
                await client.stop_notify(uuid)
            except Exception as exc:
                debug(f"Unable to stop {side} battery report: {exc}")


async def cleanup_failed_connection(client, side: str, mac: str, pair_id=None):
    """Release resources left by a failed or partial BLE initialisation."""
    mac = _normalize_mac(mac)
    # Suppress the disconnected_callback recursion for our own disconnect().
    _intentional_disconnects.add(mac)
    _connected_devices.pop(mac, None)
    _low_battery_counts.pop(mac, None)
    _low_battery_alerted.discard(mac)
    try:
        if client.is_connected:
            notify_uuids = [UUID_NOTIFY, UUID_CMD_RESPONSE]
            try:
                notify_uuids.append(get_power_report_uuid(side))
            except ValueError:
                pass
            for uuid in notify_uuids:
                try:
                    await client.stop_notify(uuid)
                except Exception:
                    pass
            await client.disconnect()
    except Exception as exc:
        debug(f"Cleanup disconnect failed for {mac}: {exc}")

    manager = get_controller_manager()
    if pair_id is None:
        mapped_pair = manager.get_pair_by_mac(mac)
        pair_id = mapped_pair.pair_id if mapped_pair else None
    await manager.remove_joycon(mac)

    if pair_id is not None:
        pair = manager.get_pair(pair_id)
        pair_empty = pair is None or not pair.is_active()
        try:
            from control_type.duo_joycon import cleanup_disconnected_joycon, unregister_vibration
            unregister_vibration(side, pair_id)
            cleanup_disconnected_joycon(pair_id, side, pair_empty)
            from control_type.single_joycon import reset_pair_state
            reset_pair_state(pair_id)
        except Exception as exc:
            debug(f"State cleanup failed for pair {pair_id}: {exc}")

    # Keep the marker until disconnected_callback consumes it; removing it
    # here would let a late callback re-enter this cleanup routine.


def detect_side_from_name(name: str) -> str:
    """Detect Joy-Con side from device name"""
    if not name:
        return "Unknown"
    
    name_upper = name.upper()
    
    # Check for explicit left/right indicators
    if "(L)" in name_upper or "LEFT" in name_upper or name_upper.endswith(" L"):
        return "Left"
    elif "(R)" in name_upper or "RIGHT" in name_upper or name_upper.endswith(" R"):
        return "Right"
    
    # Fallback: check for standalone L/R with better pattern matching
    # Check if name contains " L " or " R " (with spaces)
    if " L " in name or name.startswith("L ") or name.endswith(" L"):
        return "Left"
    elif " R " in name or name.startswith("R ") or name.endswith(" R"):
        return "Right"
    
    # Check for Joy-Con specific patterns
    if "Joy" in name:
        # Joy-Con typically has (L) or (R) in the name
        # If we see "L)" or "R)" without the opening paren, it's likely a formatting issue
        if name_upper.find("L)") != -1:
            return "Left"
        elif name_upper.find("R)") != -1:
            return "Right"
    
    return "Unknown"


def _detect_side_from_gatt(client):
    """Identify which Joy-Con half this is from its GATT table.

    A Joy-Con 2 advertisement carries no "Left"/"Right" marker, so name-based
    detection returns nothing -- that is the "(None)" in the connect log, and
    why the user had to pick a mode by hand. Each half exposes a different
    vibration characteristic, which is an authoritative post-connection signal
    (jacc/joy2con reads the PID from flash 0x13000+0x14 instead; this needs no
    extra command).
    """
    try:
        from controllers.hd_rumble import UUID_RUMBLE_LEFT, UUID_RUMBLE_RIGHT
    except Exception:
        return None

    def match(uuid):
        if not uuid:
            return None
        value = str(uuid).lower()
        if value == UUID_RUMBLE_LEFT:
            return "Left"
        if value == UUID_RUMBLE_RIGHT:
            return "Right"
        return None

    services = getattr(client, "services", None)
    if services is None:
        return None
    try:
        getter = getattr(services, "get_characteristic", None)
        if callable(getter):
            for uuid in (UUID_RUMBLE_LEFT, UUID_RUMBLE_RIGHT):
                if getter(uuid) is not None:
                    return match(uuid)
            return None
        for service in services:
            for characteristic in getattr(service, "characteristics", []):
                side = match(getattr(characteristic, "uuid", None))
                if side:
                    return side
    except Exception as exc:
        debug(f"Side detection from GATT failed: {exc}")
    return None


async def connect_joycon(device, side: str, mac: str, pair_id: Optional[int] = None, mode: str = "both", orientation: int = 0):
    """Connect to a Joy-Con and assign it to a pair
    
    Args:
        device: BLE device
        side: "Left" or "Right"
        mac: MAC address
        pair_id: Optional preferred pair ID (0-based)
        mode: "left", "right", or "both"
        orientation: 0=Vertical (default), 1=Horizontal
    """
    global _connected_devices

    manager = get_controller_manager()
    # The GUI passes device.address ("AA:BB:...") while ControllerManager
    # stores compact "AABB...". Using both formats as dict keys made
    # disconnect_pair_by_id miss the BLE client entirely: the UI reported a
    # disconnect while the controller stayed connected.
    mac = _normalize_mac(mac) or get_mac_from_device(device)
    assigned_pair_id = None
    connection_loop = asyncio.get_running_loop()

    def disconnected_callback(disconnected_client):
        if mac in _intentional_disconnects:
            _intentional_disconnects.discard(mac)
            return
        if connection_loop.is_closed():
            return
        asyncio.run_coroutine_threadsafe(
            cleanup_failed_connection(
                disconnected_client, side, mac, assigned_pair_id
            ),
            connection_loop,
        )
    
    # Try to connect
    client = BleakClient(
        device,
        timeout=10.0,
        disconnected_callback=disconnected_callback,
    )
    try:
        info(f"Attempting to connect to {mac} ({device.name})...")
        await client.connect()
        
        if not client.is_connected:
            warning(f"Failed to connect to {mac} - not connected after attempt")
            return False
        
        info(f"Successfully connected to {mac}")
        # Clear any stale marker left by a previous session for this MAC.
        _intentional_disconnects.discard(mac)

        # Ask for the shortest connection interval before the first command or
        # rumble write: everything after this point is paced by it. With the
        # Windows default a rumble frame can take longer to send than the ~12 ms
        # of haptics it carries.
        try:
            await _request_throughput_parameters(client)
        except Exception as exc:
            debug(f"Connection parameter request failed: {type(exc).__name__}: {exc}")

        # The advertisement cannot tell the halves apart; the GATT table can.
        # The detected value is authoritative, so it also corrects a wrong or
        # missing side from the UI.
        detected_side = _detect_side_from_gatt(client)
        if detected_side:
            if side != detected_side:
                info(f"Detected {detected_side} Joy-Con from GATT "
                     f"(UI/name said {side})")
            side = detected_side
        elif side in (None, "Unknown"):
            warning(f"Could not determine which half {mac} is; "
                    f"buttons may be mapped incorrectly")

        # Assign to a pair (use preferred pair if specified)
        pair_id_result = await manager.assign_joycon(client, side, mac, preferred_pair=pair_id)
        if pair_id_result is None:
            warning(f"No available slot for {side} Joy-Con {mac}")
            await client.disconnect()
            return False
        assigned_pair_id = pair_id_result
        
        pair = manager.get_pair(pair_id_result)
        info(f"Connected {side} Joy-Con {mac} to Pair {pair_id_result + 1} (Mode: {pair.get_mode_display()})")
        
        # Store connection info
        _connected_devices[mac] = (client, side, pair_id_result)
        
        # Initialize the controller
        # For "both" mode, always use duo mode even if only one Joy-Con is connected
        if mode == "both":
            await handle_duo_joycons(client, side, pair_id_result, mac, orientation)
        elif pair.mode == ControllerMode.BOTH:
            await handle_duo_joycons(client, side, pair_id_result, mac, orientation)
        elif pair.mode == ControllerMode.LEFT_ONLY:
            await handle_single_joycon(client, side, orientation, pair_id_result, mac)
        elif pair.mode == ControllerMode.RIGHT_ONLY:
            await handle_single_joycon(client, side, orientation, pair_id_result, mac)
        
        info(f"Initialization complete for {mac}")
        return True
        
    except asyncio.TimeoutError:
        warning(f"Connection timeout for {mac} - device may not be in pairing mode")
        await cleanup_failed_connection(client, side, mac, assigned_pair_id)
        return False
    except Exception as e:
        error(f"Error connecting to {mac}: {type(e).__name__}: {e}")
        await cleanup_failed_connection(client, side, mac, assigned_pair_id)
        return False


async def handle_duo_joycons(client, side: str, pair_id: int, mac: str, orientation: int = 0):
    """Handle duo Joy-Con mode for a specific pair
    
    Args:
        client: BLE client
        side: "Left" or "Right"
        pair_id: Pair ID (0-based)
        mac: MAC address
        orientation: 0=Vertical (default), 1=Horizontal
    """
    from control_type.duo_joycon import notify_duo_joycons
    
    async def notification_handler(sender, data):
        try:
            # Check if client is still connected before processing
            if not client.is_connected:
                return
            # Directly await the notification handler
            await notify_duo_joycons(client, side, data, pair_id)
        except Exception as e:
            log_notification_error(f"Duo notification pair={pair_id} side={side}", e)
    
    def response_handler(sender, data):
        try:
            if client.is_connected:
                ControllerCommand().receive_response(client, data)
        except Exception as e:
            log_notification_error(f"Duo command response pair={pair_id} side={side}", e)
    
    # Keep the command-response subscription for the whole connection. It was
    # stopped as soon as init finished, so any later command (LED changes,
    # reconnect reconfiguration) timed out twice for 3 s each.
    await client.start_notify(UUID_CMD_RESPONSE, response_handler)
    await capture_power_level(client, side, mac)
    await initSendControllerCmd(client, "Joy-Con", pair_id)

    # Set controller orientation
    from controller_manager import get_controller_manager
    manager = get_controller_manager()
    pair = manager.get_pair(pair_id)
    if pair:
        if side == "Left" and pair.left.is_connected:
            pair.left.orientation = orientation
        elif side == "Right" and pair.right.is_connected:
            pair.right.orientation = orientation

    await client.start_notify(UUID_NOTIFY, notification_handler)


async def handle_single_joycon(client, side: str, orientation: int, pair_id: int, mac: str):
    """Handle single Joy-Con mode for a specific pair"""
    # Persist the initial orientation in the shared pair state.  Subsequent
    # GUI changes update this same value and are picked up per report.
    manager = get_controller_manager()
    pair = manager.get_pair(pair_id)
    if pair:
        if side == "Left":
            pair.left.orientation = orientation
        elif side == "Right":
            pair.right.orientation = orientation

    # Reset pair state to clear old joycon instance
    from control_type.single_joycon import reset_pair_state
    reset_pair_state(pair_id)
    
    from control_type.single_joycon import notify_single_joycons
    
    async def notification_handler(sender, data):
        try:
            # Check if client is still connected before processing
            if not client.is_connected:
                return
            # Directly await the notification handler
            await notify_single_joycons(client, side, orientation, data, pair_id)
        except Exception as e:
            log_notification_error(f"Single notification pair={pair_id} side={side}", e)
    
    def response_handler(sender, data):
        try:
            if client.is_connected:
                ControllerCommand().receive_response(client, data)
        except Exception as e:
            log_notification_error(f"Single command response pair={pair_id} side={side}", e)
    
    # Command responses stay subscribed for the whole connection; see the
    # note in handle_duo_joycons.
    await client.start_notify(UUID_CMD_RESPONSE, response_handler)
    await capture_power_level(client, side, mac)
    await initSendControllerCmd(client, "Joy-Con", pair_id)

    await client.start_notify(UUID_NOTIFY, notification_handler)


async def _tune_report_rate(client):
    """Raise the BLE rate in both directions. Best effort; never fatal.

    Two independent settings matter, and the old version only ever did the first
    one -- it returned right after the descriptor write, so the connection
    interval was never requested:

      * report-rate descriptor 679d5510-... <- 0x85 00: how often the controller
        pushes input reports to us.
      * preferred connection parameters: the connection interval, which caps how
        fast *we* can write rumble frames. With the Windows default (~30 ms) a
        single rumble write takes 11-38 ms -- longer than the ~12 ms of haptics
        one packet carries -- so frames tear, and the zero-amplitude stop packet
        queues behind them.
    """
    try:
        services = getattr(client, "services", None)
        descriptors = getattr(services, "descriptors", None) if services else None
        iterable = descriptors.values() if hasattr(descriptors, "values") else (descriptors or [])
        for descriptor in iterable:
            if str(getattr(descriptor, "uuid", "")).lower() != UUID_REPORT_RATE:
                continue
            handle = getattr(descriptor, "handle", None)
            if handle is None:
                continue
            try:
                await client.write_gatt_descriptor(handle, b"\x85\x00")
                info("High report-rate descriptor written (85 00)")
                break
            except Exception as exc:
                debug(f"Report-rate descriptor write failed: {exc}")
    except Exception as exc:
        debug(f"Report-rate descriptor discovery failed: {type(exc).__name__}: {exc}")

    # Always continue: the descriptor does not change the write direction.
    await _request_throughput_parameters(client)


async def _request_throughput_parameters(client):
    """Ask Windows for the shortest BLE connection interval (throughput mode).

    Without this the rumble cadence is gated by the default interval: each
    write waits for a connection event, which is why a single frame can take
    30 ms while carrying only 12 ms of haptics.
    """
    if platform.system() != "Windows":
        return False
    try:
        build_number = int(platform.version().rsplit(".", 1)[-1])
    except (TypeError, ValueError):
        debug(f"Unable to parse Windows build from {platform.version()!r}")
        return False
    if build_number < 22000:
        info("Windows build < 22000: preferred connection parameters unavailable")
        return False

    try:
        try:
            from winrt.windows.devices.bluetooth import (
                BluetoothLEPreferredConnectionParameters,
            )
        except ImportError:
            from bleak_winrt.windows.devices.bluetooth import (
                BluetoothLEPreferredConnectionParameters,
            )
    except Exception as exc:
        debug(f"BLE parameter types unavailable: {type(exc).__name__}: {exc}")
        return False

    params = BluetoothLEPreferredConnectionParameters.throughput_optimized
    backend = getattr(client, "_backend", None)
    # bleak's WinRT client keeps the BluetoothLEDevice on _device; _requester is
    # an older/alternate name. Try both, as other implementations do.
    candidates = (
        getattr(client, "_device", None),
        getattr(backend, "_device", None),
        getattr(backend, "_requester", None),
    )
    for device in candidates:
        if device is None:
            continue
        try:
            if hasattr(device, "request_preferred_connection_parameters_async"):
                result = await device.request_preferred_connection_parameters_async(params)
            elif hasattr(device, "request_preferred_connection_parameters"):
                result = device.request_preferred_connection_parameters(params)
                if hasattr(result, "__await__"):
                    result = await result
            else:
                continue
            status = getattr(result, "status", result)
            status_name = getattr(status, "name", str(status))
            info(f"BLE connection interval: throughput-optimized requested ({status_name})")
            return True
        except Exception as exc:
            debug(f"Preferred connection parameters failed via "
                  f"{type(device).__name__}: {type(exc).__name__}: {exc}")

    warning("Could not request throughput-optimized BLE parameters; rumble "
            "frames stay paced by the default connection interval")
    return False


async def initSendControllerCmd(client, controllerName: str, pair_id: int):
    """Send initialization commands to controller"""
    controllerCommand = ControllerCommand()
    current_config = Config().getConfig()

    async def send_required(command_type, args=None):
        if not await controllerCommand.send_command(client, command_type, args):
            raise RuntimeError(f"Controller command failed: {command_type}")
    
    if current_config.get('save_mac_address', False):
        mac_address = current_config.get('mac_address', b'\xFF' * 6)
        mac_addr1 = mac_address
        mac_addr2 = ((mac_address[0] - 1) & 0xFF).to_bytes(1, 'big') + mac_address[1:]
        
        await send_required("JOY2_SAVE_MC_ADDR_STEP1",
                            {"mac-addr1": mac_addr1.hex(), "mac-addr2": mac_addr2.hex()})
        await send_required("JOY2_SAVE_MC_ADDR_STEP2")
        await send_required("JOY2_SAVE_MC_ADDR_STEP3")
        await send_required("JOY2_SAVE_MC_ADDR_STEP4")
        info(f"MAC address saved successfully.")
    
    await send_required("JOY2_CONNECTED_VIBRATION")
    
    # Set LED to show pair number (1-4)
    led_value = get_player_led_value(pair_id)
    await send_required("JOY2_SET_PLAYER_LED", {"led_player": led_value})

    await send_required("JOY2_INIT_SENSOR_DATA")
    await send_required("JOY2_START_SENSOR_DATA")

    # Query battery through the command-response channel. This is reliable on
    # hardware where report 0x07/0x08 is notify-only, and unlike subscribing to
    # that alternate report it does not interrupt the main button/IMU stream.
    if await controllerCommand.send_command(client, "JOY2_GET_BATTERY_VOLTAGE"):
        # Per-client response, not the shared singleton attribute: two
        # Joy-Cons initialising together used to overwrite each other's reply.
        response = controllerCommand.get_last_response(client)
        if response and len(response) >= 10:
            voltage_mv = int.from_bytes(response[8:10], "little")
            battery_level = battery_percentage_from_voltage(voltage_mv)
            if battery_level is not None:
                mac = _normalize_mac(client.address)
                manager = get_controller_manager()
                pair = manager.get_pair_by_mac(mac)
                joycon_info = None
                if pair:
                    if pair.left.mac_address == mac:
                        joycon_info = pair.left
                    elif pair.right.mac_address == mac:
                        joycon_info = pair.right
                # The native 0-9 state-of-charge report is authoritative.
                # Only use voltage estimation when that report was unavailable.
                if joycon_info is None or joycon_info.battery_level is None:
                    manager.update_battery(mac, battery_level)
                    info(f"Joy-Con 2 battery fallback: {voltage_mv} mV (~{battery_level}%)")
                else:
                    # Native state-of-charge won; log the voltage for
                    # diagnostics only, and say so explicitly so the line is
                    # not mistaken for the value shown in the GUI.
                    info(
                        f"Joy-Con 2 battery voltage: {voltage_mv} mV "
                        f"(native {joycon_info.battery_level}% kept, "
                        f"voltage estimate ignored)"
                    )
            else:
                warning(f"Ignoring invalid Joy-Con 2 battery voltage: {voltage_mv} mV")

    # Best-effort report-rate tuning. Failures are logged and ignored so that
    # a WinRT/bleak mismatch can never tear down a working connection.
    await _tune_report_rate(client)


async def disconnect_all():
    """Disconnect all connected devices"""
    global _connected_devices
    
    info("Disconnecting all controllers...")
    manager = get_controller_manager()
    for mac, (client, side, pair_id) in list(_connected_devices.items()):
        mac = _normalize_mac(mac)
        _intentional_disconnects.add(mac)
        try:
            if client.is_connected:
                try:
                    await client.stop_notify(get_power_report_uuid(side))
                except:
                    pass
                await client.disconnect()
            info(f"Disconnected {mac}")
        except Exception as e:
            error(f"Error disconnecting {mac}: {e}")
        await manager.remove_joycon(mac)
        pair = manager.get_pair(pair_id)
        try:
            from control_type.duo_joycon import cleanup_disconnected_joycon, unregister_vibration
            unregister_vibration(side, pair_id)
            cleanup_disconnected_joycon(pair_id, side, pair is None or not pair.is_active())
            from control_type.single_joycon import reset_pair_state
            reset_pair_state(pair_id)
        except Exception as exc:
            debug(f"State cleanup failed for pair {pair_id}: {exc}")
    
    _connected_devices.clear()
    
    # Clear any assignments that were not present in the connection registry.
    for mac in list(manager._mac_to_pair.keys()):
        await manager.remove_joycon(mac)

    # Do not clear _intentional_disconnects here: disconnected_callback can
    # still arrive one tick later. Markers are consumed by that callback, or
    # cleared by connect_joycon on the next reconnect of the same MAC.


async def shutdown():
    """Release every app-owned resource before the process exits."""
    # Stop the rumble streams first: their zero-amplitude stop packet needs
    # the BLE link to still be alive.
    try:
        from control_type.rumble_stream import get_rumble_stream
        await get_rumble_stream().shutdown()
    except Exception as exc:
        debug(f"Failed to stop rumble streams: {exc}")

    # Mouse loops are daemon threads with no exit condition in the original
    # code. Stop and join them before the process leaves the Qt event loop.
    try:
        from control_type.duo_joycon import stop_mouse_loop
        from control_type.single_joycon import stop_mouse_loops
        stop_mouse_loop()
        stop_mouse_loops()
    except Exception as exc:
        debug(f"Failed to stop mouse loops: {exc}")

    await disconnect_all()
    try:
        from dsu_server import stop_dsu
        stop_dsu()
    except Exception as exc:
        debug(f"Failed to stop DSU server: {exc}")

    # Release held buttons before destroying the device: a stuck left button
    # would survive process exit until the user clicks something.
    try:
        from control_type.virtual_mouse import (
            release_all_buttons,
            release_mouse_output,
        )
        release_all_buttons()
        release_mouse_output()
    except Exception as exc:
        debug(f"Failed to release virtual mouse: {exc}")


async def scan_for_joycons(timeout: float = 30.0, stop_event=None):
    """Scan for one Joy-Con; return None on timeout or explicit cancellation.

    The old version looped forever with no try/finally. Cancelling the "Add
    controller" dialog leaked a running BLE scanner and left its QThread alive
    for the rest of the process, which in turn made later GATT connections
    report "Unreachable".
    """
    device_controller = None
    loop = asyncio.get_running_loop()

    def scan_callback(device, advertisement_data):
        nonlocal device_controller
        data = advertisement_data.manufacturer_data.get(manufact["id"])
        if not data:
            return

        if data.startswith(manufact["data-prefix"]):
            if not device_controller:
                mac = get_mac_from_device(device)
                # Skip if already connected
                if mac in _connected_devices:
                    return
                info(f"Controller with address: {device.address} found.")
                device_controller = device

    scanner = BleakScanner(scan_callback)
    await scanner.start()
    try:
        deadline = loop.time() + max(0.0, timeout)
        while not device_controller:
            if stop_event is not None and stop_event.is_set():
                break
            remaining = deadline - loop.time()
            if remaining <= 0:
                debug("Joy-Con scan timed out")
                break
            await asyncio.sleep(min(0.5, remaining))
        return device_controller
    finally:
        try:
            await scanner.stop()
        except Exception as exc:
            debug(f"Failed to stop BLE scanner: {exc}")


async def scan_for_joycons_with_side(timeout: float = 30.0, stop_event=None):
    """Scan for Joy-Cons and try to detect side even when name is None."""
    device_controller = None
    detected_side = "Unknown"
    
    def scan_callback(device, advertisement_data):
        nonlocal device_controller, detected_side
        data = advertisement_data.manufacturer_data.get(manufact["id"])
        if not data:
            return
        
        if data.startswith(manufact["data-prefix"]):
            if not device_controller:
                mac = get_mac_from_device(device)
                # Skip if already connected
                if mac in _connected_devices:
                    return
                
                info(f"Controller with address: {device.address} found.")
                device_controller = device
                
                # The advertising product ID is authoritative and available
                # before connecting.
                pid_side = side_from_advertisement(data)
                if pid_side in ("Left", "Right"):
                    detected_side = pid_side
                    info(f"Detected {pid_side} Joy-Con from advertising PID")
                elif device.name:
                    detected_side = detect_side_from_name(device.name)
                    info(f"Detected side from name '{device.name}': {detected_side}")
                else:
                    debug("No side in advertising data or device name; the "
                          "GATT table will decide after connecting")
    
    scanner = BleakScanner(scan_callback)
    await scanner.start()
    try:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + max(0.0, timeout)
        while not device_controller:
            if stop_event is not None and stop_event.is_set():
                break
            remaining = deadline - loop.time()
            if remaining <= 0:
                debug("Joy-Con scan timed out")
                break
            await asyncio.sleep(min(0.5, remaining))
        return device_controller, detected_side
    finally:
        try:
            await scanner.stop()
        except Exception as exc:
            debug(f"Failed to stop BLE scanner: {exc}")


async def connect_device(device_info: dict) -> bool:
    """Connect to a specific device"""
    device = device_info.get('device')
    side = device_info.get('side', 'Unknown')
    mac = device_info.get('mac') or getattr(device, "address", "")
    pair_id = device_info.get('pair_id')  # Get preferred pair_id from device_info
    mode = device_info.get('mode', 'both')  # Get connection mode
    orientation = device_info.get('orientation', 0)  # Get orientation (0=vertical, 1=horizontal)
    
    if not device:
        return False
    
    return await connect_joycon(device, side, mac, pair_id=pair_id, mode=mode, orientation=orientation)


async def disconnect_pair_by_id(pair_id: int):
    """Disconnect a specific pair by ID"""
    manager = get_controller_manager()
    pair = manager.get_pair(pair_id)

    if not pair:
        return

    # Mark both halves before disconnecting so the disconnected_callback does
    # not start a second, concurrent cleanup of the same pair.
    marked_macs = [m for m in (pair.left.mac_address, pair.right.mac_address) if m]
    for mac in marked_macs:
        _intentional_disconnects.add(_normalize_mac(mac))

    from control_type.duo_joycon import cleanup_disconnected_joycon, unregister_vibration
    from control_type.single_joycon import reset_pair_state

    # Silence both actuators while the links are still up. Once BLE is
    # disconnected the zero-amplitude packet can no longer be delivered and the
    # Joy-Con keeps buzzing until it runs out of power or times out.
    try:
        from control_type.rumble_stream import get_rumble_stream
        stream = get_rumble_stream()
        for rumble_side in ("Left", "Right"):
            try:
                await stream.stop(pair_id, rumble_side)
            except Exception as exc:
                debug(f"[RUMBLE] stop before disconnect failed "
                      f"({rumble_side}): {exc}")
    except Exception as exc:
        debug(f"[RUMBLE] unable to reach rumble stream: {exc}")

    # Disconnect left
    if pair.left and pair.left.mac_address:
        mac = pair.left.mac_address
        if mac in _connected_devices:
            client, _, _ = _connected_devices[mac]
            try:
                # Stop notifications before disconnecting
                if client.is_connected:
                    try:
                        await client.stop_notify(UUID_NOTIFY)
                    except:
                        pass
                    try:
                        await client.stop_notify(UUID_CMD_RESPONSE)
                    except:
                        pass
                    try:
                        await client.stop_notify(get_power_report_uuid("Left"))
                    except:
                        pass
                    await client.disconnect()
            except:
                pass
            _connected_devices.pop(mac, None)
        await manager.remove_joycon(mac)
        cleanup_disconnected_joycon(pair_id, "Left", not pair.is_active())
        reset_pair_state(pair_id)
        unregister_vibration("Left", pair_id)

    # Disconnect right
    if pair.right and pair.right.mac_address:
        mac = pair.right.mac_address
        if mac in _connected_devices:
            client, _, _ = _connected_devices[mac]
            try:
                # Stop notifications before disconnecting
                if client.is_connected:
                    try:
                        await client.stop_notify(UUID_NOTIFY)
                    except:
                        pass
                    try:
                        await client.stop_notify(UUID_CMD_RESPONSE)
                    except:
                        pass
                    try:
                        await client.stop_notify(get_power_report_uuid("Right"))
                    except:
                        pass
                    await client.disconnect()
            except:
                pass
            _connected_devices.pop(mac, None)
        await manager.remove_joycon(mac)
        cleanup_disconnected_joycon(pair_id, "Right", not pair.is_active())
        reset_pair_state(pair_id)
        unregister_vibration("Right", pair_id)

    # Markers are intentionally left in place until the callback consumes
    # them (or connect_joycon clears them on reconnect), so a late callback
    # cannot start a duplicate cleanup.


async def main():
    """Main entry point - CLI mode (manual connection only)"""
    info("=" * 50)
    info("Joy2Win - Multi Controller Support")
    info("Supports up to 4 pairs (8 Joy-Cons)")
    info("=" * 50)
    info("Note: Use GUI mode for better experience (python gui.py)")
    info("=" * 50)

    try:
        # Start DSU server if enabled
        if Config().enable_dsu:
            main_dsu()

        # Keep running until interrupted
        while True:
            await asyncio.sleep(1)

    except (KeyboardInterrupt, asyncio.CancelledError):
        info("Interrupting...")
    finally:
        await disconnect_all()
        info("All controllers disconnected.")
