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
        # Pointer speed. 100 keeps the original 6-frame smoothing; higher is
        # faster, lower is slower. Clamped to 10..400.
        "mouse_sensitivity": 100,
        # Lift-off distance for automatic mouse mode. The Joy-Con reports a
        # smaller distance the closer it is to a surface; raise this if mouse
        # mode refuses to engage, lower it if it engages while held in the air.
        "mouse_surface_threshold": 512,
        # How pointer events reach the OS: auto (WinUHid when available),
        # standard (SendInput only) or winuhid (require the virtual HID mouse).
        "mouse_output": "auto",
        # HD Rumble amplitude scaling, 0-100 (% of AMPLITUDE_DEFAULT).
        # Lower this if the LRA feels too strong or produces a clicking sound.
        "rumble_strength": 100,
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
            try:
                self.rumble_strength = int(controller_section.get(
                    'rumble_strength', self.rumble_strength))
                self.rumble_strength = max(0, min(100, self.rumble_strength))
            except ValueError:
                print(f"Invalid 'rumble_strength' in {self._config_path}. Using default: 100")
                self.rumble_strength = 100
            try:
                self.mouse_sensitivity = int(controller_section.get(
                    'mouse_sensitivity', self.mouse_sensitivity))
                self.mouse_sensitivity = max(10, min(400, self.mouse_sensitivity))
            except ValueError:
                print(f"Invalid 'mouse_sensitivity' in {self._config_path}. Using default: 100")
                self.mouse_sensitivity = 100
            try:
                self.mouse_surface_threshold = int(controller_section.get(
                    'mouse_surface_threshold', self.mouse_surface_threshold))
                self.mouse_surface_threshold = max(8, min(4095, self.mouse_surface_threshold))
            except ValueError:
                print(f"Invalid 'mouse_surface_threshold' in {self._config_path}. Using default: 512")
                self.mouse_surface_threshold = 512
            self.mouse_output = str(
                controller_section.get('mouse_output', self.mouse_output)
            ).strip().lower()
            if self.mouse_output not in ("auto", "standard", "winuhid"):
                print(f"Invalid 'mouse_output' in {self._config_path}. Using default: auto")
                self.mouse_output = "auto"
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

    def set_and_save(self, key, value, section=None):
        """Update one attribute and persist it to config.ini.

        Only that key changes: the file is read back with configparser and
        rewritten, so the other sections ([Bluetooth], [Pair_N]) survive. The
        previous file is kept as config.ini.bak in case anything goes wrong.

        ``section`` defaults to whichever section already holds the key, falling
        back to [Controller]. Writing everything into [Controller] would make
        e.g. mac_address vanish on the next load, since it is read from
        [Bluetooth].

        Returns False when the file is missing or cannot be written; the
        in-memory value is still updated so the change applies immediately.
        """
        setattr(self, key, value)
        path = self._config_path
        if not os.path.exists(path):
            return False
        try:
            import shutil
            shutil.copyfile(path, path + ".bak")
        except OSError:
            pass
        parser = configparser.ConfigParser()
        parser.optionxform = str          # keep key case as written
        try:
            parser.read(path, encoding="utf-8")
        except (OSError, configparser.Error):
            return False

        if section is None:
            for name in parser.sections():
                if key in parser[name]:
                    section = name
                    break
            else:
                for name in ("Controller", "controller"):
                    if name in parser:
                        section = name
                        break
        if section is None or section not in parser:
            return False

        parser[section][key] = str(value)
        try:
            with open(path, "w", encoding="utf-8") as handle:
                parser.write(handle)
            return True
        except OSError:
            return False

    def getConfig(self):
        return {
            "controller": self.controller,
            "orientation": self.orientation,
            "led_player": self.led_player,
            "save_mac_address": self.save_mac_address,
            "enable_dsu": self.enable_dsu,
            "mouse_mode": self.mouse_mode,
            "mouse_sensitivity": self.mouse_sensitivity,
            "mouse_surface_threshold": self.mouse_surface_threshold,
            "mouse_output": self.mouse_output,
            "rumble_strength": self.rumble_strength,
            "mac_address": self.mac_address,
            "sll_mapping": self.sll_mapping,
            "srl_mapping": self.srl_mapping,
            "slr_mapping": self.slr_mapping,
            "srr_mapping": self.srr_mapping,
        }
