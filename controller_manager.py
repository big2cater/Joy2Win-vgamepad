# -*- coding: utf-8 -*-
"""
Controller Manager for multiple Joy-Con pairs
Supports up to 4 pairs (8 Joy-Cons)
"""

import asyncio
import vgamepad
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable
from enum import Enum
import time


class ControllerMode(Enum):
    """Controller connection mode"""
    DISCONNECTED = 0
    LEFT_ONLY = 1
    RIGHT_ONLY = 2
    BOTH = 3


@dataclass
class JoyConInfo:
    """Information about a connected Joy-Con"""
    client: object = None
    side: str = ""  # "Left" or "Right"
    mac_address: str = ""
    battery_level: Optional[int] = None
    is_charging: bool = False
    external_power: bool = False
    is_connected: bool = False
    last_seen: float = 0
    orientation: int = 0  # 0=Vertical, 1=Horizontal


@dataclass
class ControllerPair:
    """A pair of Joy-Cons (Left + Right) forming one virtual gamepad"""
    pair_id: int = 0
    left: JoyConInfo = field(default_factory=lambda: JoyConInfo(side="Left"))
    right: JoyConInfo = field(default_factory=lambda: JoyConInfo(side="Right"))
    gamepad: Optional[vgamepad.VX360Gamepad] = None
    mode: ControllerMode = ControllerMode.DISCONNECTED
    led_player: int = 1
    
    def get_mode_display(self) -> str:
        """Get display string for current mode"""
        if self.mode == ControllerMode.BOTH:
            return "双手柄"
        elif self.mode == ControllerMode.LEFT_ONLY:
            return "仅左手柄"
        elif self.mode == ControllerMode.RIGHT_ONLY:
            return "仅右手柄"
        return "未连接"
    
    def is_active(self) -> bool:
        """Check if at least one Joy-Con is connected"""
        return self.left.is_connected or self.right.is_connected
    
    def update_mode(self):
        """Update connection mode based on connected Joy-Cons"""
        left_connected = self.left.is_connected
        right_connected = self.right.is_connected
        
        if left_connected and right_connected:
            self.mode = ControllerMode.BOTH
        elif left_connected:
            self.mode = ControllerMode.LEFT_ONLY
        elif right_connected:
            self.mode = ControllerMode.RIGHT_ONLY
        else:
            self.mode = ControllerMode.DISCONNECTED


class ControllerManager:
    """Manager for multiple Joy-Con pairs"""
    
    MAX_PAIRS = 4  # Maximum 4 pairs (8 Joy-Cons)

    @staticmethod
    def _normalize_mac(mac_address: str) -> str:
        """Normalize colon, dash, and compact Bluetooth address formats."""
        return (mac_address or "").replace(":", "").replace("-", "").upper()
    
    def __init__(self):
        self.pairs: Dict[int, ControllerPair] = {}
        self._mac_to_pair: Dict[str, int] = {}  # MAC address -> pair_id mapping
        self._callbacks: List[Callable] = []
        self._lock = asyncio.Lock()
        
        # Pair records are cheap.  Creating VX360Gamepad is not: each instance
        # appears to Windows as a real controller, so create it only on use.
        for i in range(self.MAX_PAIRS):
            self.pairs[i] = ControllerPair(
                pair_id=i,
                led_player=i + 1
            )

    @staticmethod
    def _ensure_gamepad(pair: ControllerPair):
        if pair.gamepad is None:
            pair.gamepad = vgamepad.VX360Gamepad()
    
    def register_callback(self, callback: Callable):
        """Register a callback for controller status changes"""
        self._callbacks.append(callback)
    
    def unregister_callback(self, callback: Callable):
        """Unregister a callback"""
        if callback in self._callbacks:
            self._callbacks.remove(callback)
    
    def _notify_callbacks(self):
        """Notify all registered callbacks"""
        for callback in self._callbacks:
            try:
                callback()
            except Exception as e:
                pass  # Silent fail
    
    async def assign_joycon(self, client, side: str, mac_address: str, preferred_pair: Optional[int] = None) -> Optional[int]:
        """
        Assign a Joy-Con to a pair
        Args:
            client: BLE client
            side: "Left" or "Right"
            mac_address: MAC address of the Joy-Con
            preferred_pair: Optional preferred pair_id (from GUI selection)
        Returns:
            The pair_id if successful, None otherwise
        """
        mac_address = self._normalize_mac(mac_address)
        async with self._lock:
            # Check if this MAC is already assigned
            if mac_address in self._mac_to_pair:
                pair_id = self._mac_to_pair[mac_address]
                pair = self.pairs[pair_id]
                
                # Update existing assignment
                if side == "Left":
                    pair.left.client = client
                    pair.left.mac_address = mac_address
                    pair.left.is_connected = True
                    pair.left.last_seen = time.time()
                else:
                    pair.right.client = client
                    pair.right.mac_address = mac_address
                    pair.right.is_connected = True
                    pair.right.last_seen = time.time()
                
                pair.update_mode()
                self._ensure_gamepad(pair)
                self._notify_callbacks()
                return pair_id
            
            # If a preferred pair is specified, try to use it first
            if preferred_pair is not None and preferred_pair in self.pairs:
                pair = self.pairs[preferred_pair]
                
                # Check if this pair can accept the Joy-Con
                if side == "Left" and not pair.left.is_connected:
                    pair.left.client = client
                    pair.left.mac_address = mac_address
                    pair.left.is_connected = True
                    pair.left.last_seen = time.time()
                    self._mac_to_pair[mac_address] = preferred_pair
                    pair.update_mode()
                    self._ensure_gamepad(pair)
                    self._notify_callbacks()
                    return preferred_pair
                elif side == "Right" and not pair.right.is_connected:
                    pair.right.client = client
                    pair.right.mac_address = mac_address
                    pair.right.is_connected = True
                    pair.right.last_seen = time.time()
                    self._mac_to_pair[mac_address] = preferred_pair
                    pair.update_mode()
                    self._ensure_gamepad(pair)
                    self._notify_callbacks()
                    return preferred_pair
            
            # Find an available pair (original logic)
            for pair_id, pair in self.pairs.items():
                # Check if this pair can accept the Joy-Con
                if side == "Left" and not pair.left.is_connected:
                    pair.left.client = client
                    pair.left.mac_address = mac_address
                    pair.left.is_connected = True
                    pair.left.last_seen = time.time()
                    self._mac_to_pair[mac_address] = pair_id
                    pair.update_mode()
                    self._ensure_gamepad(pair)
                    self._notify_callbacks()
                    return pair_id
                elif side == "Right" and not pair.right.is_connected:
                    pair.right.client = client
                    pair.right.mac_address = mac_address
                    pair.right.is_connected = True
                    pair.right.last_seen = time.time()
                    self._mac_to_pair[mac_address] = pair_id
                    pair.update_mode()
                    self._ensure_gamepad(pair)
                    self._notify_callbacks()
                    return pair_id
            
            # No available slot
            print(f"No available slot for {side} Joy-Con {mac_address}")
            return None
    
    async def remove_joycon(self, mac_address: str):
        """Remove a Joy-Con from its pair"""
        mac_address = self._normalize_mac(mac_address)
        async with self._lock:
            if mac_address not in self._mac_to_pair:
                return
            
            pair_id = self._mac_to_pair[mac_address]
            pair = self.pairs[pair_id]
            
            # Determine which side
            if pair.left.mac_address == mac_address:
                # Clear the left joycon connection state
                pair.left.is_connected = False
                pair.left.client = None
                pair.left.mac_address = ""
                pair.left.battery_level = None
                pair.left.is_charging = False
                pair.left.external_power = False
            elif pair.right.mac_address == mac_address:
                # Clear the right joycon connection state
                pair.right.is_connected = False
                pair.right.client = None
                pair.right.mac_address = ""
                pair.right.battery_level = None
                pair.right.is_charging = False
                pair.right.external_power = False
            
            # A disconnected controller must not retain an old-pair mapping;
            # otherwise a later GUI-selected reconnect is silently ignored.
            del self._mac_to_pair[mac_address]

            # Check if pair is now empty
            if not pair.is_active():
                if pair.gamepad is not None:
                    try:
                        pair.gamepad.reset()
                        pair.gamepad.update()
                    except Exception:
                        pass
                    pair.gamepad = None
            
            pair.update_mode()
            self._notify_callbacks()
    
    def get_pair(self, pair_id: int) -> Optional[ControllerPair]:
        """Get a controller pair by ID"""
        return self.pairs.get(pair_id)
    
    def get_pair_by_mac(self, mac_address: str) -> Optional[ControllerPair]:
        """Get a controller pair by MAC address"""
        mac_address = self._normalize_mac(mac_address)
        if mac_address in self._mac_to_pair:
            return self.pairs[self._mac_to_pair[mac_address]]
        return None
    
    def get_active_pairs(self) -> List[ControllerPair]:
        """Get all active controller pairs"""
        return [pair for pair in self.pairs.values() if pair.is_active()]
    
    def get_connected_count(self) -> int:
        """Get number of connected pairs"""
        return len(self.get_active_pairs())
    
    def update_battery(self, mac_address: str, battery_level: int,
                       is_charging: bool = False, external_power: bool = False):
        """Update battery level for a Joy-Con"""
        mac_address = self._normalize_mac(mac_address)
        if mac_address in self._mac_to_pair:
            pair_id = self._mac_to_pair[mac_address]
            pair = self.pairs[pair_id]
            joycon = None
            if pair.left.mac_address == mac_address:
                joycon = pair.left
            elif pair.right.mac_address == mac_address:
                joycon = pair.right

            if joycon is not None:
                changed = (
                    joycon.battery_level != battery_level
                    or joycon.is_charging != is_charging
                    or joycon.external_power != external_power
                )
                joycon.battery_level = battery_level
                joycon.is_charging = is_charging
                joycon.external_power = external_power
                if changed:
                    self._notify_callbacks()
    
    def get_gamepad(self, pair_id: int) -> Optional[vgamepad.VX360Gamepad]:
        """Get the virtual gamepad for a pair"""
        pair = self.pairs.get(pair_id)
        if pair:
            return pair.gamepad
        return None


# Global controller manager instance
_controller_manager: Optional[ControllerManager] = None


def get_controller_manager() -> ControllerManager:
    """Get the global controller manager instance"""
    global _controller_manager
    if _controller_manager is None:
        _controller_manager = ControllerManager()
    return _controller_manager


def reset_controller_manager():
    """Reset the global controller manager (for testing)"""
    global _controller_manager
    _controller_manager = None
