# -*- coding: utf-8 -*-
"""
Joy2Win-vgamepad GUI
A modern UI for Joy-Con 2 Windows compatibility
"""

import sys
import asyncio
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTextEdit, QGroupBox, QCheckBox,
    QProgressBar, QFrame, QSplitter, QMessageBox, QSystemTrayIcon, QMenu,
    QComboBox, QFormLayout, QDialog, QGridLayout, QListWidget, QListWidgetItem,
    QScrollArea, QTabWidget
)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal, QMetaObject, QPoint, Q_ARG
from PyQt5.QtGui import QFont, QIcon, QPixmap, QPainter, QColor, QBrush, QPolygon, QPen

import os

# Import logging module
from logger_config import info, warning, error, debug

# Import controller manager
from controller_manager import get_controller_manager

# Xbox button mapping options
XBOX_BUTTONS = {
    "": "不映射",
    "XUSB_GAMEPAD_A": "A",
    "XUSB_GAMEPAD_B": "B",
    "XUSB_GAMEPAD_X": "X",
    "XUSB_GAMEPAD_Y": "Y",
    "XUSB_GAMEPAD_LEFT_SHOULDER": "LB",
    "XUSB_GAMEPAD_RIGHT_SHOULDER": "RB",
    "XUSB_GAMEPAD_LEFT_THUMB": "L3",
    "XUSB_GAMEPAD_RIGHT_THUMB": "R3",
    "XUSB_GAMEPAD_BACK": "Back",
    "XUSB_GAMEPAD_START": "Start",
    "XUSB_GAMEPAD_GUIDE": "Guide",
    "XUSB_GAMEPAD_DPAD_UP": "↑",
    "XUSB_GAMEPAD_DPAD_DOWN": "↓",
    "XUSB_GAMEPAD_DPAD_LEFT": "←",
    "XUSB_GAMEPAD_DPAD_RIGHT": "→",
}


class ButtonMappingDialog(QDialog):
    """Dialog for configuring SL/SR button mappings per pair"""

    def __init__(self, pair_id, parent=None):
        super().__init__(parent)
        self.pair_id = pair_id
        self.setWindowTitle(f"手柄组 {pair_id + 1} - SL/SR 按键映射设置")
        self.setGeometry(200, 200, 400, 300)
        self.setStyleSheet("""
            QDialog {
                background-color: #2b2b2b;
            }
            QLabel {
                color: white;
            }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #555;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
                color: #4CAF50;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        self.init_ui()
        self.load_config()
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        # Left Joy-Con SL/SR
        left_group = QGroupBox("左手柄 SL/SR")
        left_layout = QFormLayout()
        
        self.sll_combo = QComboBox()
        self.srl_combo = QComboBox()
        
        for value, label in XBOX_BUTTONS.items():
            self.sll_combo.addItem(label, value)
            self.srl_combo.addItem(label, value)
        
        self._style_combo(self.sll_combo)
        self._style_combo(self.srl_combo)
        
        left_layout.addRow("SL (左侧):", self.sll_combo)
        left_layout.addRow("SR (右侧):", self.srl_combo)
        left_group.setLayout(left_layout)
        layout.addWidget(left_group)
        
        # Right Joy-Con SL/SR
        right_group = QGroupBox("右手柄 SL/SR")
        right_layout = QFormLayout()
        
        self.slr_combo = QComboBox()
        self.srr_combo = QComboBox()
        
        for value, label in XBOX_BUTTONS.items():
            self.slr_combo.addItem(label, value)
            self.srr_combo.addItem(label, value)
        
        self._style_combo(self.slr_combo)
        self._style_combo(self.srr_combo)
        
        right_layout.addRow("SL (左侧):", self.slr_combo)
        right_layout.addRow("SR (右侧):", self.srr_combo)
        right_group.setLayout(right_layout)
        layout.addWidget(right_group)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        save_btn = QPushButton("保存")
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 8px 20px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        save_btn.clicked.connect(self.save_config)
        
        cancel_btn = QPushButton("取消")
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #555;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 8px 20px;
            }
            QPushButton:hover {
                background-color: #666;
            }
        """)
        cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addStretch()
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)
        
        self.setLayout(layout)
    
    def _style_combo(self, combo):
        combo.setStyleSheet("""
            QComboBox {
                padding: 5px;
                border: 1px solid #555;
                border-radius: 3px;
                background-color: #333;
                color: white;
                min-width: 120px;
            }
            QComboBox::drop-down {
                border: none;
                padding-right: 10px;
            }
        """)
    
    def load_config(self):
        """Load current configuration for this pair"""
        try:
            import configparser

            # Read config from per-pair section
            parser = configparser.ConfigParser()
            if os.path.exists('config.ini'):
                parser.read('config.ini')

            section = f'Pair_{self.pair_id}'
            if section in parser:
                self._set_combo_value(self.sll_combo, parser[section].get('sll_mapping', ''))
                self._set_combo_value(self.srl_combo, parser[section].get('srl_mapping', ''))
                self._set_combo_value(self.slr_combo, parser[section].get('slr_mapping', ''))
                self._set_combo_value(self.srr_combo, parser[section].get('srr_mapping', ''))
            else:
                # Fallback to global config for backward compatibility
                from config import Config
                config = Config().getConfig()
                self._set_combo_value(self.sll_combo, config.get('sll_mapping', ''))
                self._set_combo_value(self.srl_combo, config.get('srl_mapping', ''))
                self._set_combo_value(self.slr_combo, config.get('slr_mapping', ''))
                self._set_combo_value(self.srr_combo, config.get('srr_mapping', ''))
        except Exception as e:
            error(f"Error loading button mapping config: {e}")

    def _set_combo_value(self, combo, value):
        """Set combo box by data value"""
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)

    def save_config(self):
        """Save configuration to config.ini for this pair"""
        try:
            import configparser

            # Get current values
            sll = self.sll_combo.currentData()
            srl = self.srl_combo.currentData()
            slr = self.slr_combo.currentData()
            srr = self.srr_combo.currentData()

            # Read existing config
            parser = configparser.ConfigParser()
            if os.path.exists('config.ini'):
                parser.read('config.ini')

            # Ensure per-pair section exists
            section = f'Pair_{self.pair_id}'
            if section not in parser:
                parser[section] = {}

            # Update mappings for this pair
            parser[section]['sll_mapping'] = sll
            parser[section]['srl_mapping'] = srl
            parser[section]['slr_mapping'] = slr
            parser[section]['srr_mapping'] = srr

            # Write back
            with open('config.ini', 'w') as f:
                parser.write(f)

            # Update the control mappings in memory for this pair
            from control_type.duo_joycon import update_sl_sr_mappings_for_pair as duo_update
            from control_type.single_joycon import update_sl_sr_mappings_for_pair as single_update
            duo_update(self.pair_id, sll, srl, slr, srr)
            single_update(self.pair_id, sll, srl, slr, srr)

            QMessageBox.information(self, "成功", f"手柄组 {self.pair_id + 1} 按键映射已保存！")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存失败：{str(e)}")


class ControllerPairTab(QWidget):
    """Tab page for a single controller pair"""
    
    def __init__(self, pair_id, parent=None):
        super().__init__(parent)
        self.pair_id = pair_id
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        # Connection status group
        status_group = QGroupBox("连接状态")
        status_layout = QVBoxLayout()
        
        # Mode display
        self.mode_label = QLabel("未连接")
        self.mode_label.setStyleSheet("color: gray; font-size: 16px; font-weight: bold;")
        self.mode_label.setAlignment(Qt.AlignCenter)
        status_layout.addWidget(self.mode_label)
        
        # Left and Right status
        joycon_layout = QHBoxLayout()
        
        # Left Joy-Con
        left_group = QGroupBox("左手柄")
        left_layout = QVBoxLayout()
        self.left_status = QLabel("未连接")
        self.left_status.setStyleSheet("color: gray;")
        self.left_status.setAlignment(Qt.AlignCenter)
        left_layout.addWidget(self.left_status)
        self.left_battery = QProgressBar()
        self.left_battery.setRange(0, 100)
        self.left_battery.setValue(0)
        self.left_battery.setTextVisible(True)
        self.left_battery.setStyleSheet("""
            QProgressBar {
                border: 1px solid gray;
                border-radius: 3px;
                text-align: center;
                height: 20px;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
            }
        """)
        left_layout.addWidget(self.left_battery)
        left_group.setLayout(left_layout)
        joycon_layout.addWidget(left_group)
        
        # Right Joy-Con
        right_group = QGroupBox("右手柄")
        right_layout = QVBoxLayout()
        self.right_status = QLabel("未连接")
        self.right_status.setStyleSheet("color: gray;")
        self.right_status.setAlignment(Qt.AlignCenter)
        right_layout.addWidget(self.right_status)
        self.right_battery = QProgressBar()
        self.right_battery.setRange(0, 100)
        self.right_battery.setValue(0)
        self.right_battery.setTextVisible(True)
        self.right_battery.setStyleSheet("""
            QProgressBar {
                border: 1px solid gray;
                border-radius: 3px;
                text-align: center;
                height: 20px;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
            }
        """)
        right_layout.addWidget(self.right_battery)
        right_group.setLayout(right_layout)
        joycon_layout.addWidget(right_group)
        
        status_layout.addLayout(joycon_layout)
        status_group.setLayout(status_layout)
        layout.addWidget(status_group)
        
        # Settings group (per-pair settings)
        settings_group = QGroupBox("手柄组设置")
        settings_layout = QFormLayout()

        # Connection mode
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("自动检测", "auto")
        self.mode_combo.addItem("仅左手柄", "left")
        self.mode_combo.addItem("仅右手柄", "right")
        self.mode_combo.addItem("双手柄", "both")
        self.mode_combo.setStyleSheet("""
            QComboBox {
                padding: 5px;
                border: 1px solid #555;
                border-radius: 3px;
                background-color: #333;
                color: white;
            }
        """)
        settings_layout.addRow("连接模式:", self.mode_combo)

        # Orientation
        self.orientation_combo = QComboBox()
        self.orientation_combo.addItem("垂直", 0)
        self.orientation_combo.addItem("水平", 1)
        self.orientation_combo.setStyleSheet("""
            QComboBox {
                padding: 5px;
                border: 1px solid #555;
                border-radius: 3px;
                background-color: #333;
                color: white;
            }
        """)
        self.orientation_combo.currentIndexChanged.connect(self.on_orientation_changed)
        settings_layout.addRow("方向:", self.orientation_combo)
        
        # Mouse mode
        self.mouse_check = QCheckBox("启用手柄控制鼠标")
        self.mouse_check.setStyleSheet("color: white;")
        self.mouse_check.stateChanged.connect(self.on_mouse_changed)
        settings_layout.addRow("", self.mouse_check)
        
        # DSU slot
        self.dsu_check = QCheckBox("启用 DSU 体感映射")
        self.dsu_check.setStyleSheet("color: white;")
        self.dsu_check.setChecked(True)
        self.dsu_check.stateChanged.connect(self.on_dsu_changed)
        settings_layout.addRow("", self.dsu_check)
        
        # Vibration
        self.vibration_check = QCheckBox("启用震动反馈")
        self.vibration_check.setStyleSheet("color: white;")
        self.vibration_check.setChecked(True)
        self.vibration_check.stateChanged.connect(self.on_vibration_changed)
        settings_layout.addRow("", self.vibration_check)
        
        # Button mapping button
        self.mapping_btn = QPushButton("SL/SR 按键映射")
        self.mapping_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 5px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)
        settings_layout.addRow("", self.mapping_btn)
        
        settings_group.setLayout(settings_layout)
        layout.addWidget(settings_group)
        
        # Control buttons for this pair
        btn_layout = QHBoxLayout()
        
        self.add_btn = QPushButton("+ 添加手柄")
        self.add_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 10px;
            }
            QPushButton:hover {
                background-color: #F57C00;
            }
        """)
        
        self.disconnect_btn = QPushButton("- 断开手柄")
        self.disconnect_btn.setStyleSheet("""
            QPushButton {
                background-color: #F44336;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 10px;
            }
            QPushButton:hover {
                background-color: #D32F2F;
            }
        """)
        
        btn_layout.addWidget(self.add_btn)
        btn_layout.addWidget(self.disconnect_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        # Log output for this pair
        log_group = QGroupBox("手柄组日志")
        log_layout = QVBoxLayout()
        
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.document().setMaximumBlockCount(100)  # Limit log lines
        self.log_output.setStyleSheet("""
            QTextEdit {
                background-color: #1a1a1a;
                color: #00ff00;
                border: 1px solid #555;
                border-radius: 3px;
                font-family: Consolas, monospace;
                font-size: 11px;
            }
        """)
        self.log_output.setFixedHeight(120)
        log_layout.addWidget(self.log_output)
        log_group.setLayout(log_layout)
        layout.addWidget(log_group)
        
        self.setLayout(layout)
    
    def update_status(self, pair):
        """Update display with pair status"""
        if not pair or not pair.is_active():
            self.mode_label.setText("未连接")
            self.mode_label.setStyleSheet("color: gray; font-size: 16px; font-weight: bold;")
            self.left_status.setText("未连接")
            self.left_status.setStyleSheet("color: gray;")
            self.left_battery.setValue(0)
            self.right_status.setText("未连接")
            self.right_status.setStyleSheet("color: gray;")
            self.right_battery.setValue(0)
            return
        
        # Update mode
        mode_text = pair.get_mode_display()
        self.mode_label.setText(mode_text)
        
        if pair.mode.value == 3:  # BOTH
            self.mode_label.setStyleSheet("color: #4CAF50; font-size: 16px; font-weight: bold;")
        elif pair.mode.value in [1, 2]:  # LEFT_ONLY or RIGHT_ONLY
            self.mode_label.setStyleSheet("color: #FF9800; font-size: 16px; font-weight: bold;")
        else:
            self.mode_label.setStyleSheet("color: gray; font-size: 16px; font-weight: bold;")
        
        # Update Left
        if pair.left.is_connected:
            self.left_status.setText("已连接")
            self.left_status.setStyleSheet("color: #4CAF50;")
            self.left_battery.setValue(pair.left.battery_level)
        else:
            self.left_status.setText("未连接")
            self.left_status.setStyleSheet("color: gray;")
            self.left_battery.setValue(0)
        
        # Update Right
        if pair.right.is_connected:
            self.right_status.setText("已连接")
            self.right_status.setStyleSheet("color: #4CAF50;")
            self.right_battery.setValue(pair.right.battery_level)
        else:
            self.right_status.setText("未连接")
            self.right_status.setStyleSheet("color: gray;")
            self.right_battery.setValue(0)

    def on_mouse_changed(self, state):
        """Handle mouse control checkbox change"""
        enabled = state == Qt.Checked
        from control_type.duo_joycon import set_mouse_enabled as duo_set_mouse
        from control_type.single_joycon import set_mouse_enabled as single_set_mouse
        duo_set_mouse(self.pair_id, enabled)
        single_set_mouse(self.pair_id, enabled)
    
    def on_orientation_changed(self, index):
        """Handle orientation combo box change"""
        orientation = self.orientation_combo.currentData()
        info(f"Orientation changed to: {'水平' if orientation == 1 else '垂直'} (value={orientation})")
        
        # Update controller orientation
        from controller_manager import get_controller_manager
        manager = get_controller_manager()
        pair = manager.get_pair(self.pair_id)
        
        if pair:
            # Update left joycon orientation
            if pair.left.is_connected and hasattr(pair.left, 'orientation'):
                pair.left.orientation = orientation
                info(f"Updated Left Joy-Con orientation to {orientation}")
            
            # Update right joycon orientation
            if pair.right.is_connected and hasattr(pair.right, 'orientation'):
                pair.right.orientation = orientation
                info(f"Updated Right Joy-Con orientation to {orientation}")
    
    def on_dsu_changed(self, state):
        """Handle DSU checkbox change"""
        enabled = state == Qt.Checked
        info(f"DSU {'enabled' if enabled else 'disabled'}")
        
        # Update config
        try:
            from config import Config
            config = Config()
            config.enable_dsu = enabled
            
            # Save to config file
            import configparser
            parser = configparser.ConfigParser()
            parser['Controller'] = {
                'controller': str(config.controller),
                'orientation': str(config.orientation),
                'led_player': str(config.led_player),
                'save_mac_address': '1' if config.save_mac_address else '0',
                'enable_dsu': '1' if enabled else '0',
                'mouse_mode': str(config.mouse_mode),
                'sll_mapping': config.sll_mapping,
                'srl_mapping': config.srl_mapping,
                'slr_mapping': config.slr_mapping,
                'srr_mapping': config.srr_mapping,
            }
            
            with open('config.ini', 'w') as configfile:
                parser.write(configfile)
            info(f"DSU setting saved to config")
        except Exception as e:
            error(f"Failed to save DSU setting: {e}")
    
    def on_vibration_changed(self, state):
        """Handle vibration checkbox change"""
        enabled = state == Qt.Checked
        info(f"Vibration {'enabled' if enabled else 'disabled'}")
        
        # Update vibration in both duo and single mode
        try:
            from control_type.duo_joycon import set_vibration_enabled as duo_set_vib
            from control_type.single_joycon import set_vibration_enabled as single_set_vib
            
            duo_set_vib(enabled)
            single_set_vib(enabled)
            info(f"Vibration setting applied")
        except Exception as e:
            error(f"Failed to set vibration: {e}")
    
    def log_message(self, message):
        """Add message to this pair's log output"""
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_output.append(f"[{timestamp}] {message}")
        # Auto scroll to bottom
        scrollbar = self.log_output.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def clear_log(self):
        """Clear this pair's log output"""
        self.log_output.clear()


class ScanThread(QThread):
    """Thread for scanning Joy-Cons"""
    scan_finished = pyqtSignal(list)
    scan_error = pyqtSignal(str)

    def run(self):
        """Run the scan"""
        try:
            import main
            # Run async scan in new event loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # Scan for first device (original Joy2Win style)
            device = loop.run_until_complete(main.scan_for_joycons())
            loop.close()
            
            # Convert to list format for compatibility
            devices = []
            if device:
                mac = device.address
                device_name = device.name if device.name else "Joy-Con"
                
                # Detect side from name - comprehensive detection
                side = "Unknown"
                if device_name:
                    name_upper = device_name.upper()
                    # Check for Joy-Con (L) / Joy-Con (R) pattern
                    if '(L)' in name_upper or 'LEFT' in name_upper or name_upper.endswith(' L') or ' L ' in name_upper:
                        side = 'Left'
                    elif '(R)' in name_upper or 'RIGHT' in name_upper or name_upper.endswith(' R') or ' R ' in name_upper:
                        side = 'Right'
                    # Also check for "Joy-Con L" or "Joy-Con R" without parentheses
                    elif 'JOY' in name_upper:
                        if ' L' in name_upper or name_upper.endswith('L'):
                            side = 'Left'
                        elif ' R' in name_upper or name_upper.endswith('R'):
                            side = 'Right'
                
                devices.append({
                    'name': device_name,
                    'address': device.address,
                    'mac': mac,
                    'side': side,
                    'rssi': -50,  # Default RSSI
                    'device': device
                })
                
                debug(f"Scan found: {device_name} ({side}) [{mac}]")
            
            self.scan_finished.emit(devices)
        except Exception as e:
            self.scan_error.emit(str(e))


class ConnectThread(QThread):
    """Thread for connecting to a Joy-Con"""
    connect_finished = pyqtSignal(str, int, bool)  # device_name, pair_id, success
    connect_error = pyqtSignal(str, int, str)  # device_name, pair_id, error

    def __init__(self, device_info, pair_id, mode="auto", orientation=0):
        super().__init__()
        self.device_info = device_info
        self.pair_id = pair_id
        self.mode = mode
        self.orientation = orientation

    def run(self):
        """Run the connection using global event loop"""
        try:
            import main
            # Get or create the global event loop
            loop = main.get_event_loop()
            
            if not loop:
                # Create a new event loop if none exists (shouldn't happen)
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                main.set_event_loop(loop)
            
            # Set mode in device_info
            self.device_info['mode'] = self.mode
            
            # Set orientation in device_info
            self.device_info['orientation'] = self.orientation
            
            # Run connection in the global loop
            future = asyncio.run_coroutine_threadsafe(
                main.connect_device(self.device_info),
                loop
            )
            
            # Wait for result with timeout
            success = future.result(timeout=15.0)
            
            # Emit result
            self.connect_finished.emit(self.device_info.get('name', 'Unknown'), self.pair_id, success)
            
        except Exception as e:
            self.connect_error.emit(self.device_info.get('name', 'Unknown'), self.pair_id, str(e))


class DisconnectThread(QThread):
    """Thread for disconnecting a pair"""
    disconnect_finished = pyqtSignal(int)  # pair_id
    disconnect_error = pyqtSignal(int, str)  # pair_id, error

    def __init__(self, pair_id):
        super().__init__()
        self.pair_id = pair_id

    def run(self):
        """Run the disconnection using global event loop"""
        try:
            import main
            # Get or create the global event loop
            loop = main.get_event_loop()
            
            if not loop:
                # Create a new event loop if none exists (shouldn't happen)
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                main.set_event_loop(loop)
            
            # Run disconnect in the global loop
            future = asyncio.run_coroutine_threadsafe(
                main.disconnect_pair_by_id(self.pair_id),
                loop
            )
            
            # Wait for result with timeout
            future.result(timeout=5.0)
            
            # Emit result
            self.disconnect_finished.emit(self.pair_id)
            
        except Exception as e:
            self.disconnect_error.emit(self.pair_id, str(e))


class AddControllerDialog(QDialog):
    """Dialog for scanning and adding new controllers"""

    device_selected = pyqtSignal(dict)  # Signal emitted when device is selected

    def __init__(self, parent=None, connection_mode="auto", pair_state=None, pair_id=None):
        super().__init__(parent)
        self.connection_mode = connection_mode  # "auto", "left", "right", "both"
        self.pair_state = pair_state or {}  # Current pair connection state
        self.pair_id = pair_id  # Store the pair_id (0-based)
        self.setWindowTitle(f"添加手柄 - 手柄组 {pair_id + 1 if pair_id is not None else '?'}")
        self.setGeometry(200, 200, 400, 250)
        self.setStyleSheet("""
            QDialog {
                background-color: #2b2b2b;
            }
            QLabel {
                color: white;
            }
        """)
        self.found_device = None
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)

        # Instructions based on connection mode
        mode_text = {
            "auto": "请确保手柄已关机\n然后长按同步按钮（顶部滑轨内侧小孔）3-5 秒\n直到指示灯左右滚动闪烁",
            "left": "请确保左手柄已关机\n然后长按同步按钮（顶部滑轨内侧小孔）3-5 秒\n直到指示灯左右滚动闪烁",
            "right": "请确保右手柄已关机\n然后长按同步按钮（顶部滑轨内侧小孔）3-5 秒\n直到指示灯左右滚动闪烁",
            "both": "请确保手柄已关机\n然后长按同步按钮（顶部滑轨内侧小孔）3-5 秒\n直到指示灯左右滚动闪烁"
        }
        
        # For dual mode, show which Joy-Con to connect
        if self.connection_mode == "both":
            # Check if any Joy-Con is already connected
            manager = get_controller_manager()
            pair = manager.get_pair(self.pair_id)
            
            if pair:
                left_connected = pair.left.is_connected
                right_connected = pair.right.is_connected
                
                if left_connected and not right_connected:
                    mode_text["both"] = "第一个手柄（左手柄）已连接\n\n请确保右手柄已关机\n然后长按同步按钮（顶部滑轨内侧小孔）3-5 秒\n直到指示灯左右滚动闪烁"
                elif right_connected and not left_connected:
                    mode_text["both"] = "第一个手柄（右手柄）已连接\n\n请确保左手柄已关机\n然后长按同步按钮（顶部滑轨内侧小孔）3-5 秒\n直到指示灯左右滚动闪烁"
                else:
                    mode_text["both"] = "双手柄模式\n\n请先连接左手柄或右手柄\n长按同步按钮 3-5 秒直到指示灯左右滚动闪烁"
        
        instructions = QLabel(mode_text.get(self.connection_mode, mode_text["auto"]))
        instructions.setStyleSheet("color: #4CAF50; font-size: 13px; qproperty-alignment: AlignCenter;")
        instructions.setWordWrap(True)
        layout.addWidget(instructions)
        
        # Status label
        self.status_label = QLabel("请长按同步按钮...")
        self.status_label.setStyleSheet("color: #FF9800; font-size: 12px; qproperty-alignment: AlignCenter;")
        layout.addWidget(self.status_label)
        
        # Side selection (if auto-detection fails)
        self.side_widget = QWidget()
        side_layout = QHBoxLayout()
        side_layout.setContentsMargins(0, 0, 0, 0)
        
        side_label = QLabel("请选择手柄侧:")
        side_label.setStyleSheet("color: white;")
        side_layout.addWidget(side_label)
        
        self.side_combo = QComboBox()
        self.side_combo.addItem("自动检测", "auto")
        self.side_combo.addItem("左手柄 (L)", "Left")
        self.side_combo.addItem("右手柄 (R)", "Right")
        self.side_combo.setStyleSheet("""
            QComboBox {
                background-color: #444;
                color: white;
                border: 1px solid #555;
                border-radius: 3px;
                padding: 5px;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
        """)
        side_layout.addWidget(self.side_combo)
        side_layout.addStretch()
        
        self.side_widget.setLayout(side_layout)
        self.side_widget.setVisible(False)  # Hidden by default
        layout.addWidget(self.side_widget)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        self.ok_btn = QPushButton("连接")
        self.ok_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 10px 30px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #555;
            }
        """)
        self.ok_btn.setEnabled(False)  # Disabled until device found
        
        self.ok_btn.clicked.connect(self.connect_device)
        
        cancel_btn = QPushButton("取消")
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #555;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 10px 30px;
            }
            QPushButton:hover {
                background-color: #666;
            }
        """)
        cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addWidget(self.ok_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)
        
        self.setLayout(layout)
        
        # Auto-start scanning
        QTimer.singleShot(100, self.start_scan)
    
    def start_scan(self):
        """Start scanning for devices"""
        self.status_label.setText("正在扫描...请长按同步按钮")
        self.status_label.setStyleSheet("color: #FF9800;")
        
        # Run scan in background using QThread
        self.scan_thread = ScanThread()
        self.scan_thread.scan_finished.connect(self.on_scan_finished)
        self.scan_thread.scan_error.connect(self.on_scan_error)
        self.scan_thread.start()
    
    def on_scan_finished(self, devices):
        """Handle scan completion - show device and let user confirm side"""
        
        if devices:
            device = devices[0]
            self.found_device = device
            
            # Show device info
            side = device.get('side', 'Unknown')
            device_name = device.get('name', 'Unknown')
            
            if side != 'Unknown':
                # Auto-detected side
                self.status_label.setText(f"找到：{device_name} ({side})")
                self.status_label.setStyleSheet("color: #4CAF50;")
                self.side_widget.setVisible(False)
            else:
                # Could not detect side - show selection
                self.status_label.setText(f"找到设备，但无法识别左右")
                self.status_label.setStyleSheet("color: #FF9800;")
                self.side_widget.setVisible(True)
                
                # Auto-select based on connection mode if possible
                if self.connection_mode == "left":
                    self.side_combo.setCurrentIndex(1)  # Left
                elif self.connection_mode == "right":
                    self.side_combo.setCurrentIndex(2)  # Right
            
            # Enable connect button
            self.ok_btn.setEnabled(True)
            
        else:
            self.status_label.setText("未找到设备，请重新长按同步按钮")
            self.status_label.setStyleSheet("color: #F44336;")
            self.ok_btn.setEnabled(False)
            self.side_widget.setVisible(False)
    
    def on_scan_error(self, error_msg):
        """Handle scan error"""
        self.status_label.setText(f"扫描出错：{error_msg}")
        self.status_label.setStyleSheet("color: #F44336;")
    
    def connect_device(self):
        """Emit signal with device and close"""
        
        # Always use found_device
        device = self.found_device
        
        if device:
            # Update side based on user selection
            selected_side = self.side_combo.currentData()
            
            if selected_side == "auto":
                # Use detected side
                pass
            elif selected_side in ["Left", "Right"]:
                device['side'] = selected_side
                
            # Add pair_id to device info
            if self.pair_id is not None:
                device['pair_id'] = self.pair_id
                
            self.device_selected.emit(device)
            self.accept()
        else:
            pass  # No device found


class Joy2WinGUI(QMainWindow):
    """Main GUI window for Joy2Win"""
    
    # Signal for thread-safe log updates
    log_signal = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()

        # Global lock for adding controllers (prevent multiple tabs from scanning simultaneously)
        self.adding_controller_lock = False

        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.update_controller_status)
        self.status_timer.start(1000)  # Update every second

        self.init_ui()
        self.setup_tray_icon()

        # Start DSU server if enabled
        self.start_dsu_server()
    
    def init_ui(self):
        self.setWindowTitle("Joy2Win-vgamepad (多手柄版)")
        self.setGeometry(100, 100, 600, 700)
        self.setStyleSheet("""
            QMainWindow {
                background-color: #2b2b2b;
            }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #555;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
                color: #ffffff;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: #4CAF50;
            }
            QTabWidget::pane {
                border: 1px solid #555;
                background-color: #2b2b2b;
            }
            QTabBar::tab {
                background-color: #333;
                color: white;
                padding: 10px 20px;
                border: 1px solid #555;
                border-bottom: none;
                border-top-left-radius: 5px;
                border-top-right-radius: 5px;
            }
            QTabBar::tab:selected {
                background-color: #4CAF50;
            }
            QTabBar::tab:hover {
                background-color: #555;
            }
        """)
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # Set window icon
        self.setWindowIcon(QIcon(self.create_logo_pixmap()))

        # Title with logo
        title_layout = QHBoxLayout()
        logo_label = QLabel()
        logo_pixmap = self.create_logo_pixmap()
        logo_label.setPixmap(logo_pixmap)
        logo_label.setFixedSize(50, 50)
        title_layout.addWidget(logo_label)
        
        title_label = QLabel("Joy2Win-vgamepad")
        title_label.setFont(QFont("Arial", 20, QFont.Bold))
        title_label.setStyleSheet("color: #4CAF50;")
        title_layout.addWidget(title_label)
        title_layout.addStretch()

        main_layout.addLayout(title_layout)
        
        # Tab widget for 4 controller pairs
        self.tab_widget = QTabWidget()
        self.controller_tabs = []
        
        for i in range(4):
            tab = ControllerPairTab(i)
            self.controller_tabs.append(tab)
            self.tab_widget.addTab(tab, f"手柄组 {i+1}")
            
            # Connect tab buttons
            tab.add_btn.clicked.connect(lambda checked, idx=i: self.add_controller_to_pair(idx))
            tab.disconnect_btn.clicked.connect(lambda checked, idx=i: self.disconnect_pair(idx))
            tab.mapping_btn.clicked.connect(lambda checked, idx=i: self.open_button_mapping_for_pair(idx))
        
        main_layout.addWidget(self.tab_widget)
        
        # Status bar
        self.statusBar().showMessage("就绪 - 点击各选项卡的'添加手柄'按钮连接手柄")

    def start_dsu_server(self):
        """Start DSU server if enabled in config"""
        try:
            from config import Config
            config = Config().getConfig()
            if config.get('enable_dsu', False):
                from dsu_server import main_dsu
                main_dsu()
                # Log to all tabs
                for tab in self.controller_tabs:
                    tab.log_message("DSU 服务器已启动")
        except Exception as e:
            # Log to all tabs
            for tab in self.controller_tabs:
                tab.log_message(f"DSU 服务器启动失败: {str(e)}")

    def create_logo_pixmap(self):
        """Create cool cat with gamepad logo"""
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)

        # Cat face color (light beige/orange)
        face_color = QColor("#F4D03F")
        ear_inner_color = QColor("#F5B7B1")

        # Draw ears (triangles behind head)
        painter.setBrush(QBrush(face_color))
        painter.setPen(Qt.NoPen)
        # Left ear
        left_ear = QPolygon([
            QPoint(12, 18),
            QPoint(20, 5),
            QPoint(26, 16)
        ])
        painter.drawPolygon(left_ear)
        # Right ear
        right_ear = QPolygon([
            QPoint(38, 16),
            QPoint(44, 5),
            QPoint(52, 18)
        ])
        painter.drawPolygon(right_ear)

        # Draw inner ears (pink)
        painter.setBrush(QBrush(ear_inner_color))
        left_ear_inner = QPolygon([
            QPoint(16, 16),
            QPoint(20, 9),
            QPoint(23, 15)
        ])
        painter.drawPolygon(left_ear_inner)
        right_ear_inner = QPolygon([
            QPoint(41, 15),
            QPoint(44, 9),
            QPoint(48, 16)
        ])
        painter.drawPolygon(right_ear_inner)

        # Draw cat head (rounded shape)
        painter.setBrush(QBrush(face_color))
        painter.drawEllipse(10, 12, 44, 38)

        # Draw forehead stripes (two horizontal lines)
        painter.setPen(QPen(QColor("#D4AC0D"), 2))
        painter.drawLine(26, 20, 38, 20)
        painter.drawLine(28, 24, 36, 24)

        # Draw eyes (yellow with black pupils, half-closed cool look)
        painter.setPen(Qt.NoPen)
        # Left eye
        painter.setBrush(QBrush(QColor("#F1C40F")))
        painter.drawEllipse(18, 24, 10, 8)
        painter.setBrush(QBrush(Qt.black))
        painter.drawEllipse(21, 26, 4, 4)
        # Right eye
        painter.setBrush(QBrush(QColor("#F1C40F")))
        painter.drawEllipse(36, 24, 10, 8)
        painter.setBrush(QBrush(Qt.black))
        painter.drawEllipse(39, 26, 4, 4)

        # Draw eye highlights
        painter.setBrush(QBrush(Qt.white))
        painter.drawEllipse(22, 25, 2, 2)
        painter.drawEllipse(40, 25, 2, 2)

        # Draw nose (pink triangle)
        painter.setBrush(QBrush(QColor("#F1948A")))
        nose = QPolygon([
            QPoint(30, 36),
            QPoint(34, 36),
            QPoint(32, 40)
        ])
        painter.drawPolygon(nose)

        # Draw mouth with cigar
        painter.setPen(QPen(Qt.black, 2))
        # Mouth line
        painter.drawLine(26, 42, 38, 42)
        painter.drawLine(26, 42, 24, 40)
        painter.drawLine(38, 42, 40, 40)

        # Draw cigar
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor("#8B4513")))
        painter.drawRect(36, 38, 14, 5)
        # Cigar tip (red glowing)
        painter.setBrush(QBrush(QColor("#E74C3C")))
        painter.drawEllipse(48, 38, 4, 5)

        # Draw scar on right side (three lines)
        painter.setPen(QPen(QColor("#922B21"), 2))
        painter.drawLine(42, 28, 48, 34)
        painter.drawLine(44, 26, 50, 32)
        painter.drawLine(46, 24, 52, 30)

        # Draw whiskers
        painter.setPen(QPen(Qt.black, 1))
        # Left whiskers
        painter.drawLine(12, 34, 20, 36)
        painter.drawLine(12, 38, 20, 38)
        painter.drawLine(12, 42, 20, 40)
        # Right whiskers
        painter.drawLine(44, 36, 52, 34)
        painter.drawLine(44, 38, 52, 38)
        painter.drawLine(44, 40, 52, 42)

        # Draw gamepad at bottom
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor("#5D6D7E")))
        # Gamepad body
        painter.drawRoundedRect(18, 46, 28, 14, 3, 3)
        # D-pad (cross)
        painter.setBrush(QBrush(QColor("#2C3E50")))
        painter.drawRect(22, 50, 6, 2)
        painter.drawRect(24, 48, 2, 6)
        # Action buttons (colored circles)
        painter.setBrush(QBrush(QColor("#E74C3C")))  # Red (B)
        painter.drawEllipse(38, 52, 3, 3)
        painter.setBrush(QBrush(QColor("#F1C40F")))  # Yellow (Y)
        painter.drawEllipse(36, 49, 3, 3)
        painter.setBrush(QBrush(QColor("#3498DB")))  # Blue (X)
        painter.drawEllipse(41, 49, 3, 3)
        painter.setBrush(QBrush(QColor("#2ECC71")))  # Green (A)
        painter.drawEllipse(39, 47, 3, 3)

        painter.end()
        return pixmap
    
    def setup_tray_icon(self):
        """Setup system tray icon"""
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon(self.create_logo_pixmap()))

        tray_menu = QMenu()
        show_action = tray_menu.addAction("显示窗口")
        show_action.triggered.connect(self.show_and_raise)
        tray_menu.addSeparator()
        quit_action = tray_menu.addAction("退出程序")
        quit_action.triggered.connect(self.quit_application)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.tray_activated)
        self.tray_icon.show()

    def show_and_raise(self):
        """Show and raise window"""
        self.show()
        self.raise_()
        self.activateWindow()

    def tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.show_and_raise()

    def quit_application(self):
        """真正退出应用程序"""
        # Stop the status timer
        self.status_timer.stop()

        # Check if any controllers are connected
        manager = get_controller_manager()
        active_pairs = manager.get_active_pairs()

        if active_pairs:
            reply = QMessageBox.question(
                self, "确认退出",
                f"有 {len(active_pairs)} 个手柄组仍在连接中，确定要退出吗？",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.No:
                return

        # Restore stdout/stderr before exit
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__

        # Hide tray icon
        self.tray_icon.hide()

        # Force exit immediately
        info("Force exiting...")
        import os
        os._exit(0)

    def open_button_mapping_for_pair(self, pair_id: int):
        """Open button mapping dialog for specific pair"""
        dialog = ButtonMappingDialog(pair_id, self)
        dialog.exec_()
    
    def add_controller_to_pair(self, pair_id: int):
        """Open dialog to add a controller to specific pair"""
        # Check global lock
        if self.adding_controller_lock:
            QMessageBox.information(self, "提示", "另一个手柄组正在添加手柄，请稍后再试")
            return

        # Get the tab and check connection mode
        tab = self.controller_tabs[pair_id]
        connection_mode = tab.mode_combo.currentData()

        # Check if pair is full based on mode
        manager = get_controller_manager()
        pair = manager.get_pair(pair_id)

        if pair:
            if connection_mode == "left" and pair.left.is_connected:
                QMessageBox.information(self, "提示", f"手柄组 {pair_id + 1} 已连接左手柄")
                return
            elif connection_mode == "right" and pair.right.is_connected:
                QMessageBox.information(self, "提示", f"手柄组 {pair_id + 1} 已连接右手柄")
                return
            elif connection_mode == "both" and pair.mode.value == 3:  # BOTH connected
                QMessageBox.information(self, "提示", f"手柄组 {pair_id + 1} 已满（双手柄已连接）")
                return
            elif connection_mode == "auto" and pair.mode.value == 3:
                QMessageBox.information(self, "提示", f"手柄组 {pair_id + 1} 已满")
                return

        # Set lock
        self.adding_controller_lock = True
        self.statusBar().showMessage(f"手柄组 {pair_id + 1} 正在添加手柄...")

        # Get current pair state for filtering
        pair_state = {
            'left_connected': pair.left.is_connected if pair else False,
            'right_connected': pair.right.is_connected if pair else False,
        }

        dialog = AddControllerDialog(self, connection_mode, pair_state, pair_id=pair_id)
        dialog.device_selected.connect(lambda device: self.on_device_selected_for_pair(device, pair_id))
        dialog.finished.connect(self.on_add_dialog_finished)
        dialog.exec_()
    
    def on_device_selected_for_pair(self, device_info, pair_id: int):
        """Handle device selection for specific pair"""
        message = f"正在连接 {device_info['name']}..."
        self.log_message(f"{message} 到手柄组 {pair_id + 1}")
        # Also log to pair's own log
        if 0 <= pair_id < len(self.controller_tabs):
            self.controller_tabs[pair_id].log_message(message)

        # Get connection mode for this pair
        tab = self.controller_tabs[pair_id]
        mode = tab.mode_combo.currentData()
        orientation = tab.orientation_combo.currentData()
        
        # Create connect thread with mode and orientation
        self.connect_thread = ConnectThread(device_info, pair_id, mode=mode, orientation=orientation)
        self.connect_thread.connect_finished.connect(self.on_connect_finished)
        self.connect_thread.connect_error.connect(self.on_connect_error)
        self.connect_thread.start()

    def on_connect_finished(self, device_name, pair_id, success):
        """Handle connect completion"""
        if 0 <= pair_id < len(self.controller_tabs):
            if success:
                self.controller_tabs[pair_id].log_message(f"成功连接 {device_name}")
                
                # Check connection mode and auto-prompt for second Joy-Con
                tab = self.controller_tabs[pair_id]
                mode = tab.mode_combo.currentData()
                
                if mode == "both":
                    # Check which Joy-Cons are connected
                    manager = get_controller_manager()
                    pair = manager.get_pair(pair_id)
                    
                    if pair:
                        left_connected = pair.left.is_connected
                        right_connected = pair.right.is_connected
                        
                        # Auto-prompt for second Joy-Con
                        if left_connected and not right_connected:
                            self.show_dual_connect_prompt(pair_id, 'Right')
                        elif right_connected and not left_connected:
                            self.show_dual_connect_prompt(pair_id, 'Left')
            else:
                self.controller_tabs[pair_id].log_message(f"连接 {device_name} 失败")

    def on_connect_error(self, device_name, pair_id, error_msg):
        """Handle connect error"""
        if 0 <= pair_id < len(self.controller_tabs):
            self.controller_tabs[pair_id].log_message(f"连接出错：{error_msg}")
        
    def show_dual_connect_prompt(self, pair_id, second_side):
        """Show prompt to connect second Joy-Con in dual mode"""
        side_name = "左手柄" if second_side == "Left" else "右手柄"
            
        msg_box = QMessageBox()
        msg_box.setWindowTitle("连接第二个手柄")
        msg_box.setText(f"第一个手柄已连接")
        msg_box.setInformativeText(f"请长按{side_name}的同步按钮 3-5 秒，然后点击\"确定\"开始连接")
        msg_box.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
        msg_box.button(QMessageBox.Ok).setText("确定")
        msg_box.button(QMessageBox.Cancel).setText("取消")
        msg_box.setStyleSheet("""
            QMessageBox {
                background-color: #2b2b2b;
            }
            QLabel {
                color: white;
            }
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 8px 20px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)
            
        result = msg_box.exec_()
            
        if result == QMessageBox.Ok:
            # User wants to connect second Joy-Con now
            self.log_message(f"开始连接第二个手柄：{side_name}")
            # Simulate clicking add button for this pair
            if 0 <= pair_id < len(self.controller_tabs):
                self.controller_tabs[pair_id].add_btn.click()
        else:
            self.log_message(f"已取消连接第二个手柄")
        
    def on_add_dialog_finished(self):
        """Called when AddControllerDialog closes - release lock"""
        self.adding_controller_lock = False
        self.statusBar().showMessage("就绪")

    def disconnect_pair(self, pair_id: int):
        """Disconnect a specific pair"""
        manager = get_controller_manager()
        pair = manager.get_pair(pair_id)

        if not pair or not pair.is_active():
            QMessageBox.information(self, "提示", f"手柄组 {pair_id + 1} 未连接")
            return

        reply = QMessageBox.question(
            self, "确认断开",
            f"确定要断开车柄组 {pair_id + 1} 吗？",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.start_disconnect_thread(pair_id)
    
    def start_disconnect_thread(self, pair_id: int):
        """Start a thread to disconnect a pair"""
        self.disconnect_thread = DisconnectThread(pair_id)
        self.disconnect_thread.disconnect_finished.connect(self.on_disconnect_finished)
        self.disconnect_thread.disconnect_error.connect(self.on_disconnect_error)
        self.disconnect_thread.start()

    def on_disconnect_finished(self, pair_id):
        """Handle disconnect completion"""
        if 0 <= pair_id < len(self.controller_tabs):
            self.controller_tabs[pair_id].log_message("已断开连接")

    def on_disconnect_error(self, pair_id, error_msg):
        """Handle disconnect error"""
        if 0 <= pair_id < len(self.controller_tabs):
            self.controller_tabs[pair_id].log_message(f"断开出错: {error_msg}")
    
    def log_message(self, message, pair_id=None):
        """Add message to specific pair's log or current tab's log"""
        if pair_id is not None and 0 <= pair_id < len(self.controller_tabs):
            self.controller_tabs[pair_id].log_message(message)
        else:
            # Log to currently selected tab
            current_tab = self.tab_widget.currentIndex()
            if 0 <= current_tab < len(self.controller_tabs):
                self.controller_tabs[current_tab].log_message(message)

    def update_controller_status(self):
        """Update controller connection and battery status for all pairs"""
        try:
            manager = get_controller_manager()
            
            # Update title with count
            active_count = manager.get_connected_count()
            self.setWindowTitle(f"Joy2Win-vgamepad ({active_count}/4 组手柄)")
            
            # Update each tab
            for i, tab in enumerate(self.controller_tabs):
                pair = manager.get_pair(i)
                if pair:
                    tab.update_status(pair)
                    # Update tab text to show status
                    mode_short = ""
                    if pair.mode.value == 3:
                        mode_short = "[双]"
                    elif pair.mode.value == 1:
                        mode_short = "[左]"
                    elif pair.mode.value == 2:
                        mode_short = "[右]"
                    self.tab_widget.setTabText(i, f"手柄组 {i+1} {mode_short}")
                else:
                    tab.update_status(None)
                    self.tab_widget.setTabText(i, f"手柄组 {i+1}")
                
        except Exception as e:
            # Silently fail during shutdown
            pass
    
    def closeEvent(self, event):
        """Handle window close - minimize to tray instead of exit"""
        event.ignore()
        self.hide()
        self.tray_icon.showMessage(
            "Joy2Win",
            "程序已最小化到系统托盘，双击图标显示窗口",
            QSystemTrayIcon.Information,
            2000
        )


def main():
    import sys
    import threading
    
    app = QApplication(sys.argv)
    
    # Set application style
    app.setStyle("Fusion")
    
    # Validate config file on startup
    from error_handler import validate_config_file
    if not validate_config_file():
        QMessageBox.critical(None, "错误", "配置文件验证失败，请检查文件权限")
        sys.exit(1)
    
    # Create and start the global event loop (like original Joy2Win)
    import main as main_module
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    main_module.set_event_loop(loop)
    
    # Start the event loop in a background thread
    def run_event_loop():
        loop.run_forever()
    
    loop_thread = threading.Thread(target=run_event_loop, daemon=True)
    loop_thread.start()
    
    window = Joy2WinGUI()
    window.show()
    
    exit_code = app.exec_()
    
    # Stop the event loop on exit
    loop.call_soon_threadsafe(loop.stop)
    
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
