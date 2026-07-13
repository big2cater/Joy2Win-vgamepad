import configparser
import os

class Config:
    _instance = None
    _defaults = {
        "controller": 0,
        "orientation": 0,
        "led_player": "0001",
        "save_mac_address": False,
        "enable_dsu": False,
        "mouse_mode": 0,
        "mac_address": b'\xFF' * 6,  # Always bytes to avoid type mismatch
        "sll_mapping": "",      # SL Left mapping (empty = unmapped)
        "srl_mapping": "",      # SR Left mapping (empty = unmapped)
        "slr_mapping": "",      # SL Right mapping (empty = unmapped)
        "srr_mapping": "",      # SR Right mapping (empty = unmapped)
    }

    def __new__(cls, config_path="config.ini"):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._config_path = config_path
            cls._instance._init_defaults()
            cls._instance.load_config()
        return cls._instance

    def _init_defaults(self):
        for key, value in self._defaults.items():
            setattr(self, key, value)

    def load_config(self):
        config_parser = configparser.ConfigParser()
        if not os.path.exists(self._config_path):
            print(f"{self._config_path} not found. Using default values.")
            return

        config_parser.read(self._config_path)
        
        # Check for Controller section (case-insensitive)
        controller_section = None
        for section_name in ['Controller', 'controller']:
            if section_name in config_parser:
                controller_section = config_parser[section_name]
                break
        
        if controller_section:
            try:
                self.controller = int(controller_section.get('controller', self.controller))
            except ValueError:
                print(f"Invalid 'controller' value in {self._config_path}. Using default: {self.controller}")
            try:
                self.orientation = int(controller_section.get('orientation', self.orientation))
            except ValueError:
                print(f"Invalid 'orientation' value in {self._config_path}. Using default: {self.orientation}")
            self.led_player = str(controller_section.get('led_player', self.led_player))
            save_mac_val = controller_section.get('save_mac_address', '0')
            self.save_mac_address = save_mac_val.lower() in ['1', 'true', 'yes']
            enable_dsu_val = controller_section.get('enable_dsu', '0')
            self.enable_dsu = enable_dsu_val.lower() in ['1', 'true', 'yes']
            try:
                self.mouse_mode = int(controller_section.get('mouse_mode', self.mouse_mode if self.mouse_mode in [0, 1, 2] else 0))
                if self.mouse_mode not in [0, 1, 2]:
                    self.mouse_mode = 0
            except ValueError:
                print(f"Invalid 'mouse_mode' value in {self._config_path}. Using default: 0")
                self.mouse_mode = 0
            # SL/SR button mappings
            self.sll_mapping = controller_section.get('sll_mapping', self.sll_mapping)
            self.srl_mapping = controller_section.get('srl_mapping', self.srl_mapping)
            self.slr_mapping = controller_section.get('slr_mapping', self.slr_mapping)
            self.srr_mapping = controller_section.get('srr_mapping', self.srr_mapping)
        else:
            print(f"Section 'Controller' not found in {self._config_path}. Using default values.")
            self._init_defaults()
            return
        
        if "Bluetooth" in config_parser or "bluetooth" in config_parser:
            section = config_parser["Bluetooth"] if "Bluetooth" in config_parser else config_parser["bluetooth"]
            configMacAddress = section.get("mac_address", self.mac_address)
            if not configMacAddress:
                self.mac_address = self._defaults["mac_address"]
            elif(len(configMacAddress) == 12 and all(c in "0123456789ABCDEF" for c in configMacAddress.upper())): # Valid MAC address format like AABBCCDDEEFF
                self.mac_address = bytes.fromhex(configMacAddress)[::-1] # Convert mac to little-endian format
            else:
                print(f"Invalid MAC address in {self._config_path}. Using default: {self.mac_address}")
                self.mac_address = self._defaults["mac_address"]
        else:
            print(f"Section 'Bluetooth' not found in {self._config_path}. disabling save_mac_address.")
            self.save_mac_address = False

    def getConfig(self):
        return {
            "controller": self.controller,
            "orientation": self.orientation,
            "led_player": self.led_player,
            "save_mac_address": self.save_mac_address,
            "enable_dsu": self.enable_dsu,
            "mouse_mode": self.mouse_mode,
            "mac_address": self.mac_address,
            "sll_mapping": self.sll_mapping,
            "srl_mapping": self.srl_mapping,
            "slr_mapping": self.slr_mapping,
            "srr_mapping": self.srr_mapping,
        }
