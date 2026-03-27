"""
Joy-Con 到 DS4 按钮映射配置工具
交互式配置，按提示按下对应按钮即可
"""

import asyncio
import json
import os
from bleak import BleakClient, BleakScanner
from controllers.JoyconL import JoyConLeft
from controllers.JoyconR import JoyConRight
from controller_command import ControllerCommand, UUID_NOTIFY, UUID_CMD_RESPONSE

# DS4 按钮定义
DS4_BUTTONS_TO_CONFIGURE = [
    ("L2 (左扳机)", "ZL"),
    ("L1 (左肩键)", "L"),
    ("L3 (左摇杆按下)", "L3"),
    ("R2 (右扳机)", "ZR"),
    ("R1 (右肩键)", "R"),
    ("R3 (右摇杆按下)", "R3"),
    ("✕ 键", "A"),
    ("○ 键", "B"),
    ("□ 键", "X"),
    ("△ 键", "Y"),
    ("Share 键", "Minus"),
    ("Options 键", "Plus"),
    ("PS 键", "Home"),
]

# 制造商数据
manufact = {
    "id": 0x0553,
    "data-prefix": bytes([0x01, 0x00, 0x03, 0x7e, 0x05])
}

class ButtonConfigurator:
    def __init__(self):
        self.mapping = {}
        self.current_button_index = 0
        self.joycon_left = JoyConLeft()
        self.joycon_right = JoyConRight()
        self.client_left = None
        self.client_right = None
        self.waiting_for_button = False
        self.connected_addresses = set()  # 已连接的手柄地址
        
    async def scan_and_connect(self, name, side, timeout=30):
        """扫描并连接 Joy-Con"""
        print(f"\n正在扫描 {name} {side}，请按下手柄的同步按钮...")
        
        device_controller = None
        
        def callback(device, advertisement_data):
            nonlocal device_controller
            data = advertisement_data.manufacturer_data.get(manufact["id"])
            if not data:
                return
            if data.startswith(manufact["data-prefix"]):
                # 检查是否已连接过
                if device_controller is None and device.address not in self.connected_addresses:
                    print(f"找到手柄: {device.address}")
                    device_controller = device
        
        scanner = BleakScanner(callback)
        await scanner.start()
        
        # 等待找到设备或超时
        start_time = asyncio.get_event_loop().time()
        while device_controller is None:
            await asyncio.sleep(0.1)
            if asyncio.get_event_loop().time() - start_time > timeout:
                print(f"扫描 {name} {side} 超时")
                break
        
        await scanner.stop()
        
        if device_controller is None:
            return None
        
        # 连接
        client = BleakClient(device_controller)
        await client.connect()
        
        if client.is_connected:
            print(f"{name} {side} 连接成功！")
            self.connected_addresses.add(device_controller.address)
            return client
        else:
            print(f"{name} {side} 连接失败")
            return None
    
    async def init_joycon(self, client, side):
        """初始化 Joy-Con"""
        controllerCommand = ControllerCommand()
        
        # 发送初始化命令
        await controllerCommand.send_command(client, "JOY2_CONNECTED_VIBRATION")
        await controllerCommand.send_command(client, "JOY2_SET_PLAYER_LED", {"led_player": "1"})
        await controllerCommand.send_command(client, "JOY2_INIT_SENSOR_DATA")
        await controllerCommand.send_command(client, "JOY2_START_SENSOR_DATA")
        
        # 启动通知
        async def notification_handler(sender, data):
            if side == "Left":
                await self.joycon_left.update(data)
            else:
                await self.joycon_right.update(data)
        
        await client.start_notify(UUID_NOTIFY, notification_handler)
    
    def get_pressed_button(self):
        """获取当前按下的 Joy-Con 按钮"""
        # 检查左 Joy-Con
        for btn_name, pressed in self.joycon_left.buttons.items():
            if pressed:
                return ("Left", btn_name)
        
        # 检查右 Joy-Con
        for btn_name, pressed in self.joycon_right.buttons.items():
            if pressed:
                return ("Right", btn_name)
        
        return None
    
    async def configure_buttons(self):
        """交互式配置按钮"""
        print("\n" + "="*60)
        print("Joy-Con 到 DS4 按钮映射配置")
        print("="*60)
        print("\n请按提示按下对应的 Joy-Con 按钮")
        print("按 Ctrl+C 可以跳过当前按钮")
        print("="*60 + "\n")
        
        for ds4_name, joycon_btn in DS4_BUTTONS_TO_CONFIGURE:
            print(f"\n请按下 Joy-Con 上对应 [{ds4_name}] 的按钮...")
            print("(等待按键，按 Ctrl+C 跳过)")
            
            self.waiting_for_button = True
            pressed = None
            
            try:
                # 等待按钮按下
                for _ in range(100):  # 最多等待 10 秒
                    await asyncio.sleep(0.1)
                    pressed = self.get_pressed_button()
                    if pressed:
                        break
                
                if pressed:
                    side, btn_name = pressed
                    print(f"  ✓ 映射: {ds4_name} -> Joy-Con {side}.{btn_name}")
                    self.mapping[joycon_btn] = {
                        "side": side,
                        "button": btn_name
                    }
                else:
                    print(f"  ✗ 跳过: {ds4_name}")
                    
            except asyncio.CancelledError:
                print(f"  ✗ 跳过: {ds4_name}")
                continue
            
            # 等待按钮释放
            while self.get_pressed_button():
                await asyncio.sleep(0.1)
        
        print("\n" + "="*60)
        print("配置完成！")
        print("="*60)
    
    def save_mapping(self):
        """保存映射到文件"""
        filename = "custom_mapping.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(self.mapping, f, indent=2, ensure_ascii=False)
        print(f"\n映射已保存到 {filename}")
    
    async def run(self):
        """运行配置器"""
        try:
            # 连接两个 Joy-Con
            self.client_left = await self.scan_and_connect("Joy-Con", "Left")
            if not self.client_left:
                print("左 Joy-Con 连接失败")
                return
            
            await self.init_joycon(self.client_left, "Left")
            
            self.client_right = await self.scan_and_connect("Joy-Con", "Right")
            if not self.client_right:
                print("右 Joy-Con 连接失败")
                return
            
            await self.init_joycon(self.client_right, "Right")
            
            # 开始配置
            await self.configure_buttons()
            
            # 保存配置
            self.save_mapping()
            
        except KeyboardInterrupt:
            print("\n\n配置已取消")
        finally:
            # 断开连接
            if self.client_left:
                await self.client_left.disconnect()
            if self.client_right:
                await self.client_right.disconnect()
            print("手柄已断开连接")


if __name__ == "__main__":
    configurator = ButtonConfigurator()
    asyncio.run(configurator.run())
