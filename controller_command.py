import asyncio

UUID_NOTIFY = "ab7de9be-89fe-49ad-828f-118f09df7fd2"
UUID_CMD = "649d4ac9-8eb7-4e6c-af44-1ea54fe5f005"
UUID_CMD_RESPONSE = "c765a961-d9d8-4d36-a20a-5315b111836a"
UUID_POWER_LEFT = "cc1bbbb5-7354-4d32-a716-a81cb241a32a"
UUID_POWER_RIGHT = "d5a9e01e-2ffc-4cca-b20c-8b67142bf442"

COMMAND_TYPE = {
    "JOY2_CONNECTED_VIBRATION": {"data": "0A9101020004000003000000", "wait_response": True, "args": None},

    "JOY2_SET_PLAYER_LED": {"data": "09910007000800000X00000000000000", "wait_response": True, "args": [{"name": "led_player", "letter": "X", "length": 1}]},

    "JOY2_INIT_SENSOR_DATA": {"data": "0c91010200040000FF000000", "wait_response": True, "args": None}, #Thanks to "Narr the Reg" and "ndeadly"

    "JOY2_FINALIZE_SENSOR_DATA": {"data": "0c91010300040000FF000000", "wait_response": True, "args": None}, #Thanks to "Narr the Reg" and "ndeadly"

    "JOY2_START_SENSOR_DATA": {"data": "0c91010400040000FF000000", "wait_response": True, "args": None}, #Thanks to "Narr the Reg" and "ndeadly"

    # Official Joy-Con 2 battery-voltage query. The four-byte payload begins
    # at response offset 8 and stores millivolts as little-endian uint16.
    "JOY2_GET_BATTERY_VOLTAGE": {"data": "0b91000300000000", "wait_response": True, "args": None},

    # Save mac address
    # Found info : switch2_controller_research by ndeadly
    "JOY2_SAVE_MC_ADDR_STEP1": {"data": "15910101000e00000002XY", "wait_response": True, "args": [{"name": "mac-addr1", "letter": "X", "length": 12},{"name": "mac-addr2", "letter": "Y", "length": 12}]},
    "JOY2_SAVE_MC_ADDR_STEP2": {"data": "15910104001100000008065a60e902e4e102029e3fa39a78d1", "wait_response": True, "args": None},
    "JOY2_SAVE_MC_ADDR_STEP3": {"data": "159101020011000000934e580f163aeecfb575fc9136b22fbb", "wait_response": True, "args": None},
    "JOY2_SAVE_MC_ADDR_STEP4": {"data": "159101030001000000", "wait_response": True, "args": None},

}

class ControllerCommand:
    _instance = None
    onSendCmd = False
    cmdAnswered = False
    responseSucceeded = False
    clientSending = None
    expectedResponse = None
    lastResponse = None
    _lock = asyncio.Lock()
    RESPONSE_TIMEOUT = 3.0
    MAX_ATTEMPTS = 2

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ControllerCommand, cls).__new__(cls)
        return cls._instance

    async def send_command(self, client, commandType, args=None):
        async with self._lock:
            try:
                self.onSendCmd = True
                self.clientSending = client

                command = COMMAND_TYPE[commandType] # Get the command details
                data = command["data"] # Get the command data

                if command.get("args") and args: # If command requires arguments
                    for arg in command["args"]: # Get all required arguments
                        letter = arg["letter"] # Get the letter to replace in hex string
                        name = arg["name"] # Get the argument name
                        if name in args: # Check args has the argument
                            value = str(args[name])
                            if len(value) == arg["length"]: # Check if the argument length is valid
                                data = data.replace(letter, value)
                            else: # If the argument length is invalid
                                raise ValueError(f"Invalid argument length for: {name}")
                        else: # If the argument is missing
                            raise ValueError(f"Missing argument: {name}")

                # Convert hex string to bytes
                data_bytes = bytes.fromhex(data)
                self.expectedResponse = (data_bytes[0], data_bytes[2], data_bytes[3])
                self.lastResponse = None

                #print(f"Sending command: {commandType} with data: {data_bytes.hex()}")

                attempts = self.MAX_ATTEMPTS if command["wait_response"] else 1
                for attempt in range(1, attempts + 1):
                    self.cmdAnswered = False
                    self.responseSucceeded = False
                    await client.write_gatt_char(UUID_CMD, data_bytes)

                    if not command["wait_response"]:
                        return True

                    loop = asyncio.get_running_loop()
                    deadline = loop.time() + self.RESPONSE_TIMEOUT
                    while not self.cmdAnswered and loop.time() < deadline:
                        await asyncio.sleep(0.05)

                    if self.cmdAnswered and self.responseSucceeded:
                        return True

                    if attempt < attempts:
                        await asyncio.sleep(0.1)

                raise asyncio.TimeoutError(
                    f"No successful response for {commandType} after {attempts} attempts"
                )

            except Exception as e:
                print(f"Failed to send command: {e}")
                return False
            finally:
                self.onSendCmd = False
                self.clientSending = None
                self.expectedResponse = None

    def receive_response(self, client, data):
        if (data and len(data) >= 4 and self.clientSending == client
                and self.expectedResponse == (data[0], data[2], data[3])):
            self.responseSucceeded = data[1] == 0x01
            self.lastResponse = bytes(data)
            self.cmdAnswered = True
