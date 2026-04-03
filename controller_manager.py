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
    battery_level: int = 100
    is_connected: bool = False
    last_seen: float = 0


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
    
    def __init__(self):
        self.pairs: Dict[int, ControllerPair] = {}
        self._mac_to_pair: Dict[str, int] = {}  # MAC address -> pair_id mapping
        self._callbacks: List[Callable] = []
        self._lock = asyncio.Lock()
        
        # Initialize pairs
        for i in range(self.MAX_PAIRS):
            self.pairs[i] = ControllerPair(
                pair_id=i,
                gamepad=vgamepad.VX360Gamepad(),
                led_player=i + 1
            )
    
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
                    self._notify_callbacks()
                    return preferred_pair
                elif side == "Right" and not pair.right.is_connected:
                    pair.right.client = client
                    pair.right.mac_address = mac_address
                    pair.right.is_connected = True
                    pair.right.last_seen = time.time()
                    self._mac_to_pair[mac_address] = preferred_pair
                    pair.update_mode()
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
                    self._notify_callbacks()
                    return pair_id
                elif side == "Right" and not pair.right.is_connected:
                    pair.right.client = client
                    pair.right.mac_address = mac_address
                    pair.right.is_connected = True
                    pair.right.last_seen = time.time()
                    self._mac_to_pair[mac_address] = pair_id
                    pair.update_mode()
                    self._notify_callbacks()
                    return pair_id
            
            # No available slot
            print(f"No available slot for {side} Joy-Con {mac_address}")
            return None
    
    async def remove_joycon(self, mac_address: str):
        """Remove a Joy-Con from its pair"""
        async with self._lock:
            if mac_address not in self._mac_to_pair:
                return
            
            pair_id = self._mac_to_pair[mac_address]
            pair = self.pairs[pair_id]
            
            # Determine which side
            if pair.left.mac_address == mac_address:
                # Clear the left joycon completely
                pair.left.is_connected = False
                pair.left.client = None
                pair.left.mac_address = None
                pair.left.device = None
                # Reset orientation and other state
                pair.left.orientation = 0
                pair.left.motionTimestamp = 0
                pair.left.accelerometer = [0.0, 0.0, 0.0]
                pair.left.gyroscope = [0.0, 0.0, 0.0]
            elif pair.right.mac_address == mac_address:
                # Clear the right joycon completely
                pair.right.is_connected = False
                pair.right.client = None
                pair.right.mac_address = None
                pair.right.device = None
                # Reset orientation and other state
                pair.right.orientation = 0
                pair.right.motionTimestamp = 0
                pair.right.accelerometer = [0.0, 0.0, 0.0]
                pair.right.gyroscope = [0.0, 0.0, 0.0]
            
            # Check if pair is now empty
            if not pair.is_active():
                del self._mac_to_pair[mac_address]
            
            pair.update_mode()
            self._notify_callbacks()
    
    def get_pair(self, pair_id: int) -> Optional[ControllerPair]:
        """Get a controller pair by ID"""
        return self.pairs.get(pair_id)
    
    def get_pair_by_mac(self, mac_address: str) -> Optional[ControllerPair]:
        """Get a controller pair by MAC address"""
        if mac_address in self._mac_to_pair:
            return self.pairs[self._mac_to_pair[mac_address]]
        return None
    
    def get_active_pairs(self) -> List[ControllerPair]:
        """Get all active controller pairs"""
        return [pair for pair in self.pairs.values() if pair.is_active()]
    
    def get_connected_count(self) -> int:
        """Get number of connected pairs"""
        return len(self.get_active_pairs())
    
    def update_battery(self, mac_address: str, battery_level: int):
        """Update battery level for a Joy-Con"""
        if mac_address in self._mac_to_pair:
            pair_id = self._mac_to_pair[mac_address]
            pair = self.pairs[pair_id]
            
            if pair.left.mac_address == mac_address:
                pair.left.battery_level = battery_level
            elif pair.right.mac_address == mac_address:
                pair.right.battery_level = battery_level
            
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
