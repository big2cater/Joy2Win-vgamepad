# 🎮 Joy-Con 2 Windows compatibility
使用灵码编辑器修改，去除了vjoy并添加了vigembus的支持，双手柄体感正常，游戏震动目前也能实现了。

This temporary project allows you to connect your **Nintendo Switch 2 Joy-Con** to a Windows PC using BLE and vgamepad (virtual Xbox 360 controller).

---

## 🚀 Installation

1. Clone this repository :
   ```bash
   git clone https://github.com/big2cater/Joy2Win-vgamepad.git
   cd Joy2Win
   ```

2. Install Python dependencies :
    ```
    pip install vgamepad
    ```

4.  Install ViGEmBus driver (required for vgamepad) :
    https://github.com/ViGEm/ViGEmBus/releases
    - Download and install the latest ViGEmBus setup
    - Restart your computer  

## 🕹️ Usage

1. Copy the `config-exemple.ini` file, rename it to `config.ini`, and edit it according to your needs.

2. Run the script in the Joy2Win directory (wherever you cloned it):
    ```bash
    python main.py
    ```

3. Follow the instructions displayed when the script starts.

4. Confirm that the controller is connected.
        - Search in Windows for "Set up USB game controllers".
        - You should see "Controller (Xbox 360 For Windows)" there.

Your Joy-Con 2 controllers are now connected to your Windows computer.

## 🎮 (Optional) Next Steps - Steam

To connect your controller for use with Steam games, In Steam, navigate to Settings > Controller > Begin Setup.

If you're using Both Joy-Cons, you can quickly configure every button (inlcuding the C button and the SL/SR buttons) by first copying the below:
```
a:b4,b:b5,x:b6,y:b7,dpleft:b9,dpright:b8,dpup:b10,dpdown:b11,leftx:a0,lefty:a1,leftstick:b18,rightx:a3,righty:a4,rightstick:b19,leftshoulder:b2,lefttrigger:b0,rightshoulder:b3,righttrigger:b1,back:b13,start:b12,misc1:b21,misc3:b22,guide:b20,paddle1:b14,paddle2:b16,paddle3:b15,paddle4:b17,
```
Then during Setup, select **Paste from Clipboard**.

(If you've already set up your controller, then **Paste from Clipboard** can be found under **Settings** > **Controller** > (your JoyCon 2 pair) > **Test Device Inputs**.)

If successful, it should look like this:

<img width="1600" height="1000" alt="image" src="https://github.com/user-attachments/assets/8ecd941a-8cf5-4140-bab1-2684fa39523a" />

The Capture button will be identified as "M1", the C button will be identified as "M2", and the SL/SR buttons on each JoyCon will be identified as "L4"/"L5"/"R4"/"R5".

Note: There are other options under Settings > Controller that you can enable / explore, like:
- Use Nintendo Button Layout
- Universal Face Button Glyphs (to match Nintendo's UI)
- Test Device Inputs

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

## **NOTICE !**
**Why is this project temporary ?**  
Currently, Joy-Con 2 controllers only work on Windows. Other operating systems are not supported due to how the controllers communicate. (Due to Joy-Con 2 communication protocol ?)  
  
On this project's [Discord's server](https://discord.gg/LINK_TEMPORARY_REMOVED_BECAUSE_SOME_PEOPLE_DONT_READ_THE_WARNING!!!) somes people work hard to figure out how Switch 2 controllers communicate.  

> [!WARNING]
> **!! This Discord's server is not part of this project, so no help will be provided there !!**  
> For questions or issues, please contact ``octokling`` on Discord or by Issues.

> [!NOTE]  
> I am not a Bluetooth communication expert. I have been helped multiple times to understand how it works. 


## Author
Made by **Octokling**

Helped by :  
- narr_the_reg
- ndeadly
