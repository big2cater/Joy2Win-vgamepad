import asyncio, os
from typing import Optional
from bleak import BleakClient, BleakScanner
from config import Config
from controller_command import ControllerCommand, UUID_NOTIFY, UUID_CMD_RESPONSE
from dsu_server import main_dsu
from controller_manager import get_controller_manager, ControllerMode
from logger_config import info, warning, error, debug

# Check if the operating system is Windows
if(os.name != 'nt'):
    error("This application is only supported on Windows.")
    exit(1)

# Read the configuration from config.ini
config = Config().getConfig()

manufact = {
    "id": 0x0553,  # Nintendo Co., Ltd.
    "data-prefix": bytes([0x01, 0x00, 0x03, 0x7e, 0x05])
}

# Global state
_connected_devices = {}  # mac_address -> (client, side, pair_id)
_main_event_loop = None  # Reference to main event loop for callbacks


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


async def connect_joycon(device, side: str, mac: str, pair_id: Optional[int] = None, mode: str = "auto", orientation: int = 0):
    """Connect to a Joy-Con and assign it to a pair
    
    Args:
        device: BLE device
        side: "Left" or "Right"
        mac: MAC address
        pair_id: Optional preferred pair ID (0-based)
        mode: "auto", "left", "right", or "both"
        orientation: 0=Vertical (default), 1=Horizontal
    """
    global _connected_devices
    
    manager = get_controller_manager()
    
    # Try to connect
    client = BleakClient(device, timeout=10.0)  # Increase timeout to 10 seconds
    try:
        info(f"Attempting to connect to {mac} ({device.name})...")
        await client.connect()
        
        if not client.is_connected:
            warning(f"Failed to connect to {mac} - not connected after attempt")
            return False
        
        info(f"Successfully connected to {mac}")
        
        # Assign to a pair (use preferred pair if specified)
        pair_id_result = await manager.assign_joycon(client, side, mac, preferred_pair=pair_id)
        if pair_id_result is None:
            warning(f"No available slot for {side} Joy-Con {mac}")
            await client.disconnect()
            return False
        
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
        return False
    except Exception as e:
        error(f"Error connecting to {mac}: {type(e).__name__}: {e}")
        try:
            await manager.remove_joycon(mac)
        except:
            pass
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
    # Reset Joy-Con instances to clear old state
    from control_type.duo_joycon import reset_joycon_instances
    reset_joycon_instances()
    
    from control_type.duo_joycon import notify_duo_joycons
    
    async def notification_handler(sender, data):
        try:
            # Check if client is still connected before processing
            if not client.is_connected:
                return
            # Directly await the notification handler
            await notify_duo_joycons(client, side, data, pair_id)
        except Exception as e:
            # Silently ignore errors after disconnect
            pass
    
    def response_handler(sender, data):
        try:
            if client.is_connected:
                ControllerCommand().receive_response(client, data)
        except:
            pass
    
    try:
        await client.start_notify(UUID_CMD_RESPONSE, response_handler)
        await initSendControllerCmd(client, "Joy-Con", pair_id)
        await client.stop_notify(UUID_CMD_RESPONSE)
        
        # Set controller orientation
        from controller_manager import get_controller_manager
        manager = get_controller_manager()
        pair = manager.get_pair(pair_id)
        if pair:
            if side == "Left" and pair.left.is_connected:
                pair.left.orientation = orientation
            elif side == "Right" and pair.right.is_connected:
                pair.right.orientation = orientation
    except Exception as e:
        warning(f"Error with UUID_CMD_RESPONSE for {mac}: {e}")
        info("Continuing without command response notifications...")
        await initSendControllerCmd(client, "Joy-Con", pair_id)
    
    await client.start_notify(UUID_NOTIFY, notification_handler)


async def handle_single_joycon(client, side: str, orientation: int, pair_id: int, mac: str):
    """Handle single Joy-Con mode for a specific pair"""
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
            # Silently ignore errors after disconnect
            pass
    
    def response_handler(sender, data):
        try:
            if client.is_connected:
                ControllerCommand().receive_response(client, data)
        except:
            pass
    
    try:
        await client.start_notify(UUID_CMD_RESPONSE, response_handler)
        await initSendControllerCmd(client, "Joy-Con", pair_id)
        await client.stop_notify(UUID_CMD_RESPONSE)
    except Exception as e:
        warning(f"Error with UUID_CMD_RESPONSE for {mac}: {e}")
        info("Continuing without command response notifications...")
        await initSendControllerCmd(client, "Joy-Con", pair_id)
    
    await client.start_notify(UUID_NOTIFY, notification_handler)


async def initSendControllerCmd(client, controllerName: str, pair_id: int):
    """Send initialization commands to controller"""
    controllerCommand = ControllerCommand()
    
    if config.get('save_mac_address', False):
        mac_address = config.get('mac_address', b'\xFF' * 6)
        mac_addr1 = mac_address
        mac_addr2 = (mac_address[0] - 1).to_bytes(1, 'big') + mac_address[1:]
        
        await controllerCommand.send_command(client, "JOY2_SAVE_MC_ADDR_STEP1", 
                                            {"mac-addr1": mac_addr1.hex(), "mac-addr2": mac_addr2.hex()})
        await controllerCommand.send_command(client, "JOY2_SAVE_MC_ADDR_STEP2")
        await controllerCommand.send_command(client, "JOY2_SAVE_MC_ADDR_STEP3")
        await controllerCommand.send_command(client, "JOY2_SAVE_MC_ADDR_STEP4")
        info(f"MAC address saved successfully.")
    
    await controllerCommand.send_command(client, "JOY2_CONNECTED_VIBRATION")
    
    # Set LED to show pair number (1-4)
    led_value = format(pair_id + 1, 'x')  # 1, 2, 4, 8 for players 1-4
    await controllerCommand.send_command(client, "JOY2_SET_PLAYER_LED", {"led_player": led_value})
    
    await controllerCommand.send_command(client, "JOY2_INIT_SENSOR_DATA")
    await controllerCommand.send_command(client, "JOY2_START_SENSOR_DATA")


async def disconnect_all():
    """Disconnect all connected devices"""
    global _connected_devices
    
    info("Disconnecting all controllers...")
    for mac, (client, side, pair_id) in list(_connected_devices.items()):
        try:
            if client.is_connected:
                await client.disconnect()
                print(f"Disconnected {mac}")
        except Exception as e:
            print(f"Error disconnecting {mac}: {e}")
    
    _connected_devices.clear()
    
    # Clear controller manager
    manager = get_controller_manager()
    for mac in list(manager._mac_to_pair.keys()):
        await manager.remove_joycon(mac)


async def scan_for_joycons():
    """Scan for Joy-Cons - same as original Joy2Win project"""
    device_controller = None
    
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
                print(f"Controller with address: {device.address} found.")
                device_controller = device
    
    scanner = BleakScanner(scan_callback)
    await scanner.start()
    
    # Keep scanning until a device is found (no timeout)
    while True:
        if device_controller:
            break
        await asyncio.sleep(0.5)
    
    await scanner.stop()
    return device_controller


async def scan_for_joycons_with_side():
    """Scan for Joy-Cons and try to detect side even when name is None"""
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
                
                print(f"Controller with address: {device.address} found.")
                device_controller = device
                
                # Try to detect side from device name
                device_name = device.name if device.name else ""
                if device_name:
                    detected_side = detect_side_from_name(device_name)
                    print(f"Detected side from name '{device_name}': {detected_side}")
                else:
                    # If name is None, try to detect from MAC address pattern
                    # Some Joy-Cons have different MAC patterns for L/R
                    # Or check advertisement data for clues
                    print(f"Device name is None, checking other characteristics...")
                    # For now, we'll rely on user to specify side in GUI
    
    scanner = BleakScanner(scan_callback)
    await scanner.start()
    
    # Keep scanning until a device is found (no timeout)
    while True:
        if device_controller:
            break
        await asyncio.sleep(0.5)
    
    await scanner.stop()
    return device_controller, detected_side


async def connect_device(device_info: dict) -> bool:
    """Connect to a specific device"""
    device = device_info.get('device')
    side = device_info.get('side', 'Unknown')
    mac = device_info.get('mac', '')
    pair_id = device_info.get('pair_id')  # Get preferred pair_id from device_info
    mode = device_info.get('mode', 'auto')  # Get connection mode
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
                    await client.disconnect()
            except:
                pass
            del _connected_devices[mac]
        await manager.remove_joycon(mac)
    
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
                    await client.disconnect()
            except:
                pass
            del _connected_devices[mac]
        await manager.remove_joycon(mac)


async def main():
    """Main entry point - CLI mode (manual connection only)"""
    print("=" * 50)
    print("Joy2Win - Multi Controller Support")
    print("Supports up to 4 pairs (8 Joy-Cons)")
    print("=" * 50)
    print("Note: Use GUI mode for better experience (python gui.py)")
    print("=" * 50)

    try:
        # Start DSU server if enabled
        if config.get('enable_dsu', False):
            main_dsu()

        # Keep running until interrupted
        while True:
            await asyncio.sleep(1)

    except (KeyboardInterrupt, asyncio.CancelledError):
        print("\nInterrupting...")
    finally:
        await disconnect_all()
        print("All controllers disconnected.")
