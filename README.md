# 🎮 Joy-Con 2 Windows compatibility
使用Lingma IDE修改
https://lingma.aliyun.com
去除了原项目使用的vjoy并添加了vigembus的支持，双手柄体感正常，游戏震动目前也能实现了。

This temporary project allows you to connect your **Nintendo Switch 2 Joy-Con** to a Windows PC using BLE and vgamepad (virtual Xbox 360 controller).

---

## 🚀 Installation

1. Clone this repository :
   ```bash
   git clone https://github.com/big2cater/Joy2Win-vgamepad.git
   cd Joy2Win-vgamepad
   ```

2. Install Python dependencies :
    ```
    pip install vgamepad
    ```

4.  Install ViGEmBus driver (required for vgamepad) :
    https://github.com/ViGEm/ViGEmBus/releases
    - Download and install the latest ViGEmBus setup
    - Restart your computer  



## ✨ Features

- Select usage type and Joy-Con orientation (single or paired, horizontal or vertical (only for single joycon))
- Player LED indicator support (By default, player 1)
- Vibration feedback when Joy-Con is successfully connected.
- Use motion sensor with DSU server (For emulators)
- Automatic mouse control

## Repositories
- [vgamepad](https://github.com/yannbouteiller/vgamepad)
- [ViGEmBus](https://github.com/ViGEm/ViGEmBus)
- [switch2_controller_research](https://github.com/ndeadly/switch2_controller_research)


## Original author
Made by **Octokling**

Helped by :  
- narr_the_reg
- ndeadly
