import socket
import struct
import random
import zlib
import asyncio
import threading
import time

IP_ADDRESS = '0.0.0.0'
PORT = 26760
SERVER_ID = random.randint(0, 0xFFFFFFFF)

sendWaitClientMsg = False
sendClientConnectedMsg = False

idPacket = 0
isReadyToSend = False
DSUClientAddr = None
_clients = {}

sock = None
_dsu_thread = None
_socket_lock = threading.RLock()
_state_lock = threading.Lock()
_stop_event = threading.Event()

# Joy2Win exposes two motion slots per pair (left/right) and supports four
# pairs.  This is an eight-slot extension used by the Eden integration.
DSU_SLOT_COUNT = 8
DSU_CLIENT_TIMEOUT = 10.0


def _valid_client_packet(data):
    if len(data) < 20 or struct.unpack_from('<H', data, 6)[0] != len(data) - 16:
        return False
    expected_crc = struct.unpack_from('<I', data, 8)[0]
    crc_data = bytearray(data)
    crc_data[8:12] = b'\x00\x00\x00\x00'
    return expected_crc == (zlib.crc32(crc_data) & 0xFFFFFFFF)


def _prune_clients_locked(now=None):
    """Drop UDP subscriptions that have not been renewed recently."""
    global DSUClientAddr, isReadyToSend, sendWaitClientMsg, sendClientConnectedMsg
    now = time.monotonic() if now is None else now
    for addr, subscription in list(_clients.items()):
        if now - subscription[3] > DSU_CLIENT_TIMEOUT:
            _clients.pop(addr, None)
    if DSUClientAddr not in _clients:
        DSUClientAddr = next(iter(_clients), None)
    isReadyToSend = bool(_clients)
    sendWaitClientMsg = not isReadyToSend
    sendClientConnectedMsg = isReadyToSend


def _get_slot_info(slot):
    """Return connection and battery information for a DSU slot."""
    try:
        from controller_manager import get_controller_manager
        pair = get_controller_manager().get_pair(slot // 2)
        if pair is None:
            return False, 0
        joycon = pair.left if slot % 2 == 0 else pair.right
        if not joycon.is_connected:
            return False, 0
        battery_level = joycon.battery_level
        if battery_level is None:
            return True, 0
        if joycon.is_charging:
            return True, 0xEF if battery_level >= 100 else 0xEE
        if battery_level <= 5:
            battery_status = 1
        elif battery_level <= 20:
            battery_status = 2
        elif battery_level <= 70:
            battery_status = 3
        elif battery_level < 95:
            battery_status = 4
        else:
            battery_status = 5
        return True, battery_status
    except Exception:
        # Controller discovery must still get a valid response while the
        # manager is starting or shutting down.
        return False, 0


def _slot_mac(slot):
    """Create a stable, unique synthetic MAC for a Joy2Win DSU slot."""
    return bytes((0xAA, 0xBB, 0xCC, 0xDD, 0xEE, slot & 0xFF))


def _build_packet(payload):
    header = bytearray([
        *b'DSUS',
        0xE9, 0x03,
        len(payload) & 0xFF, (len(payload) >> 8) & 0xFF,
        0x00, 0x00, 0x00, 0x00,
        *SERVER_ID.to_bytes(4, 'little'),
    ])
    packet = header + payload
    header[8:12] = struct.pack('<I', zlib.crc32(packet) & 0xFFFFFFFF)
    return header + payload

def incrementIdPacket():
    global idPacket
    idPacket += 1
    if idPacket > 0xFFFFFFFF:  # Reset if it exceeds 32-bit unsigned int
        idPacket = 1
    return idPacket

## DSU Server response functions: Controller information ##
async def responseInfoController(slot=0):
    """Build one Cemuhook controller-info response for one requested slot."""
    connected, battery_status = _get_slot_info(slot)
    payload = bytearray([
        0x01, 0x00, 0x10, 0x00,
        slot,
        0x02 if connected else 0x00,
        0x02 if connected else 0x00,
        0x02 if connected else 0x00,
        *_slot_mac(slot),
        battery_status,
        0x01 if connected else 0x00,
    ])
    return _build_packet(payload)

## DSU Server response functions: Controller data ##
async def responseDataController(timestampMotion, accel, gyro, slot=0):
    global idPacket
    idPacket = incrementIdPacket()  # Increment packet ID

    connected, battery_status = _get_slot_info(slot)
    if not isinstance(timestampMotion, int):
        timestampMotion = 0
    timestampMotion &= 0xFFFFFFFFFFFFFFFF

    slotInfo = bytearray([
        0x02, 0x00, 0x10, 0x00, # Message type: 0x02001000 (Ask data from controller)
        slot, # Slot ID | 1 bytes
        0x02 if connected else 0x00,
        0x02 if connected else 0x00,
        0x02 if connected else 0x00,
        *_slot_mac(slot),
        battery_status,
        # Total length: 11 bytes
    ])

    controllerStats = bytearray([
        0x01 if connected else 0x00,
        *idPacket.to_bytes(4, 'little'),  # packet ID
        0b00000000,  # buttons byte 1
        0b00000000,  # buttons byte 2
        0x00,  # HOME
        0x00,  # Touch
        128, 128,  # Left Stick X/Y
        128, 128,  # Right Stick X/Y
        0, 0, 0, 0,  # analog D-PAD L/D/R/U
        0, 0, 0, 0,  # analog Y/B/A/X
        0, 0, 0, 0,  # analog R1/L1/R2/L2
        0, 0, 0, 0, 0, 0,  # touch 1 (inactive)
        0, 0, 0, 0, 0, 0,  # touch 2 (inactive)
        *struct.pack("<Q", timestampMotion),
        *struct.pack("<3f", accel["X"], accel["Y"], accel["Z"]), # Accelerometer data (already in bytes, length 4 bytes) | 4 bytes
        *struct.pack("<3f", gyro["X"], gyro["Y"], gyro["Z"]) # Gyroscope data (already in bytes, length 4 bytes) | 4 bytes
    ])

    data = slotInfo + controllerStats

    return _build_packet(data)

## Send message to DSU client ##
async def send_message(data, addr):
    """Send a UDP packet without allowing a transient socket error to kill DSU."""
    global DSUClientAddr, isReadyToSend, sendWaitClientMsg, sendClientConnectedMsg
    try:
        with _socket_lock:
            current_sock = sock
            if current_sock is None:
                return False
            current_sock.sendto(data, addr)
        return True
    except OSError as exc:
        print(f"DSU send failed: {exc}")
        with _state_lock:
            _clients.pop(addr, None)
            if DSUClientAddr == addr:
                DSUClientAddr = next(iter(_clients), None)
            isReadyToSend = bool(_clients)
            sendWaitClientMsg = not isReadyToSend
            sendClientConnectedMsg = isReadyToSend
        return False

## Initialize DSU server ##
async def wait_response():
    global DSUClientAddr, isReadyToSend, sendWaitClientMsg, sendClientConnectedMsg
    while not _stop_event.is_set():
        try:
            with _socket_lock:
                current_sock = sock
            if current_sock is None:
                break
            data, addr = current_sock.recvfrom(1024)
            #print(f"Received data from {addr}: {data.hex()}")
            if len(data) < 20:
                print(f"Received too short packet: {data.hex()}")
                continue
            if not _valid_client_packet(data):
                continue
            header = data[0:16] # Lenght 16 bytes
            message_type = data[16:20] # Lenght 4 bytes
            
            if header[0:4] == b'DSUC' and header[4:6] == b'\xE9\x03':

                if message_type.hex() == "01001000": #Information about controllers
                    if len(data) < 24:
                        continue
                    requested_count = struct.unpack_from('<i', data, 20)[0]
                    if requested_count < 0 or requested_count > DSU_SLOT_COUNT:
                        continue
                    requested_slots = data[24:24 + requested_count]
                    if len(requested_slots) != requested_count:
                        continue
                    # Cemuhook expects one complete response packet per slot.
                    for requested_slot in requested_slots:
                        if 0 <= requested_slot < DSU_SLOT_COUNT:
                            await send_message(await responseInfoController(requested_slot), addr)

                elif message_type.hex() == "02001000": #Ask data from controller
                    if len(data) < 28:
                        continue
                    flags = data[20]
                    requested_slot = data[21]
                    requested_mac = bytes(data[22:28])
                    with _state_lock:
                        is_new_client = addr not in _clients
                        _clients[addr] = (flags, requested_slot, requested_mac, time.monotonic())
                        sendClientConnectedMsg = True
                        isReadyToSend = True
                        # Always refresh the address. Eden's test dialog may
                        # create a new UDP socket with a different source port.
                        DSUClientAddr = addr
                        if is_new_client:
                            print("DSU Client connected !")
            else:
                #print(f"Received unexpected data from {addr}: {data.hex()}")
                continue
            # Process data here if needed
        except ConnectionResetError:
            with _state_lock:
                _clients.clear()
                DSUClientAddr = None
                isReadyToSend = False
                sendWaitClientMsg = False
                sendClientConnectedMsg = False
            continue
        except socket.timeout:
            continue
        except OSError as exc:
            if _stop_event.is_set():
                break
            # Keep the listener alive for recoverable UDP/socket errors.
            print(f"DSU receive failed: {exc}")
            time.sleep(0.1)
        except Exception as exc:
            # A malformed client packet must not permanently stop the server.
            print(f"DSU listener error: {type(exc).__name__}: {exc}")
            time.sleep(0.1)
    return

async def controller_update(timestampBytes, accelBytes, gyroBytes, slot=0):
    global DSUClientAddr, isReadyToSend
    if not 0 <= slot < DSU_SLOT_COUNT:
        return
    with _state_lock:
        _prune_clients_locked()
        clients = list(_clients.items()) if isReadyToSend else []
    if not clients:
        return
    response = await responseDataController(timestampBytes, accelBytes, gyroBytes, slot)
    for client_addr, (flags, requested_slot, requested_mac, last_seen) in clients:
        slot_matches = not (flags & 0x01) or requested_slot == slot
        mac_matches = not (flags & 0x02) or requested_mac == _slot_mac(slot)
        if slot_matches and mac_matches:
            await send_message(response, client_addr)

def main_dsu():
    global sendWaitClientMsg, sock, _dsu_thread
    with _socket_lock:
        if sock is None:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.bind((IP_ADDRESS, PORT))
            sock.settimeout(1)
            print(f"DSU Server listening on {IP_ADDRESS}:{PORT}")
    # Start (or restart) the listener thread if not running
    if _dsu_thread is None or not _dsu_thread.is_alive():
        _stop_event.clear()
        sendWaitClientMsg = True
        print("Waiting for DSU client to connect...")
        _dsu_thread = threading.Thread(target=lambda: asyncio.run(wait_response()), daemon=True)
        _dsu_thread.start()


def stop_dsu():
    """Stop the listener and release the UDP port; safe to call repeatedly."""
    global sock, DSUClientAddr, isReadyToSend, sendWaitClientMsg, sendClientConnectedMsg
    _stop_event.set()
    with _socket_lock:
        current_sock, sock = sock, None
        if current_sock is not None:
            try:
                current_sock.close()
            except OSError:
                pass
    with _state_lock:
        _clients.clear()
        DSUClientAddr = None
        isReadyToSend = False
        sendWaitClientMsg = False
        sendClientConnectedMsg = False
