# 🎮 Joy2Win-vgamepad

使用灵码编辑器修改，去除了 vjoy 并添加了 ViGEmBus 的支持。支持多组 Joy-Con 2 同时连接，连接后可从 GATT 表自动识别左右手柄（BLE 广播本身不含 L/R），双手柄体感正常。震动已改为 Joy-Con 2 原生 HD Rumble 输出（12 ms 帧流、双马达通道、中性帧停止）；由于 XInput / SDL 只提供两个马达强度，这是本地合成，不是游戏原始波形透传。

---

## ✨ 主要功能

### 🖥️ GUI 界面（PyQt5）
- **多选项卡界面**：支持最多 4 组手柄（8 个 Joy-Con）同时连接
- **每组独立设置**：
  - 连接模式（自动/仅左手柄/仅右手柄/双手柄）
  - SL/SR 按键自定义映射
  - 手柄方向（垂直/水平）
  - 鼠标控制开关
  - DSU 体感映射开关
  - 震动反馈开关
- **实时状态显示**：连接状态、电量显示（绿/橙/红）
- **系统托盘支持**：最小化到托盘，双击恢复
- **日志输出窗口**：实时显示运行日志

### 🎮 手柄功能
- **多手柄支持**：最多 4 组 Joy-Con 同时连接
- **虚拟 Xbox 360 手柄**：游戏识别为 Xbox 手柄
- **体感映射**：DSU 协议支持（Cemu、Yuzu 等模拟器）
- **震动反馈**：游戏震动同步到 Joy-Con
- **鼠标控制**：手柄作为鼠标使用
- **SL/SR 按键映射**：可自定义映射到任意 Xbox 按键

### 📦 打包成 EXE
- 支持打包成独立可执行文件
- 无需安装 Python 环境
- 方便分享给朋友使用

---

## 🚀 快速开始（5 分钟上手）

### 方式一：使用预编译 EXE（最简单）
1. 下载 `Joy2Win-vgamepad.exe` 和 `config.ini`
2. 确保已安装 [ViGEmBus 驱动](https://github.com/ViGEm/ViGEmBus/releases)
3. 双击运行 `Joy2Win-vgamepad.exe`
4. 按提示连接手柄即可

### 方式二：从源码运行

> **必须使用 Python 3.12。** `requirements-gui.txt` 锁定的 `bleak==0.21.1` 要求
> `>=3.8,<3.13`，用 3.13 或更新版本在安装阶段就会失败；若直接拿系统里已装的
> 新版 bleak（3.x）启动，连接手柄时会因 API 变更报错。
>
> 启动后日志第一行会打印实际使用的解释器和依赖版本，可据此确认环境是否正确。

```bash
# 1. 克隆仓库
git clone https://github.com/big2cater/Joy2Win-vgamepad.git
cd Joy2Win-vgamepad

# 2. 用 Python 3.12 创建虚拟环境
py -3.12 -m venv venv

# 3. 在虚拟环境里安装依赖
venv\Scripts\python.exe -m pip install -r requirements-gui.txt

# 4. 运行程序（不要用系统的 python）
venv\Scripts\python.exe gui.py
```

Windows 用户也可以直接双击 `start-gui.bat`，它会自动激活 `venv`。

---

## 📖 详细安装指南

### 1. 克隆仓库
```bash
git clone https://github.com/big2cater/Joy2Win-vgamepad.git
cd Joy2Win-vgamepad
```

### 2. 安装依赖
```bash
# 先创建 3.12 虚拟环境（3.13+ 装不了 bleak 0.21.1）
py -3.12 -m venv venv
venv\Scripts\python.exe -m pip install -r requirements-gui.txt
```

### 3. 安装 ViGEmBus 驱动（必需）
下载地址：https://github.com/ViGEm/ViGEmBus/releases
- 下载并安装最新版 ViGEmBus
- 重启电脑

---

## 🕹️ 使用方法

### 方法 1：使用 GUI 界面（推荐）

#### 启动程序
```bash
venv\Scripts\python.exe gui.py
```
或者双击运行 `start-gui.bat`（推荐，会自动激活 venv）

#### 连接手柄
1. 选择要使用的选项卡（手柄组 1-4）
2. 选择连接模式：
   - **自动检测**：自动识别左右手柄
   - **仅左手柄**：只连接左手柄
   - **仅右手柄**：只连接右手柄
   - **双手柄**：连接左右一对
3. 点击"+ 添加手柄"按钮
4. 按 Joy-Con 的同步按钮（侧面的小圆点）
5. 在弹出的列表中选择手柄并连接

#### SL/SR 按键映射设置
1. 在选项卡中点击"SL/SR 按键映射"按钮
2. 为 SLL、SRL、SLR、SRR 选择要映射的 Xbox 按键
3. 点击保存

#### 断开手柄
- 点击"- 断开手柄"按钮断开当前选项卡的手柄

### 方法 2：打包成 EXE

#### 打包
```bash
build-exe.bat
```

#### 使用
1. 打包完成后，在 `dist` 目录中找到 `Joy2Win-vgamepad.exe`
2. 确保 `config.ini` 在同一目录
3. 双击运行即可

### 方法 3：命令行模式
```bash
python main.py
```
注意：命令行模式只支持手动连接，没有持续扫描功能。

---

## 🔧 常见问题排查流程

### 手柄无法连接？
1. **检查蓝牙是否开启**
   - Windows 设置 → 蓝牙和其他设备 → 确保蓝牙已打开

2. **检查手柄是否进入配对模式**
   - 按下手柄侧面的 SYNC 按钮（小圆点）
   - 手柄 LED 灯会开始闪烁

3. **检查 ViGEmBus 驱动**
   - 确保已安装并重启电脑
   - 设备管理器中应看到 "Nefarius Virtual Gamepad Emulation Bus"

4. **查看日志文件**
   - 程序目录下会生成 `joy2win.log`
   - 查看具体错误信息

### 摇杆方向反了？
1. 在 GUI 中调整"方向"设置
2. 垂直模式：正常竖直握持
3. 水平模式：横向握持，X/Y 轴会互换

### 没有震动反馈？
1. 确保 GUI 中"启用震动反馈"已勾选
2. 确保游戏支持手柄震动
3. 检查 ViGEmBus 驱动是否安装正确
4. 调整 `config.ini` 的 `rumble_strength`（0-100）；默认取社区实测的安全振幅，太强会听到敲击声
5. 日志出现 `HD rumble characteristic unavailable` 时会自动降级为固件预置震动，说明该手柄不响应 rumble 特征
6. 正常震动时，日志每次起停各有一行：`[RUMBLE] pair=0 Left: rumble on (large=..., small=...)` 与 `rumble off`。若只看到 `rumble on` 没有 `rumble off`，把日志发我

### 震动停不下来？
- 正常路径下不会：停止帧写入失败会重试 3 次，且 1.5 秒收不到新强度会自动补发零振幅帧
- 如果日志出现 `stop packet not delivered` 或 `gave up sending the stop packet`，说明 BLE 链路已经不通（手柄休眠、走远、被系统挂起）。此时手柄会自行超时，也可关机重连
- 点「断开手柄」时程序会先发停止帧再断链，所以断开后不该继续震

### 电量显示不准确？
- Joy-Con 2 原生上报 0-9 级电量，界面映射为约 11% 一级（权威值）
- 连接时短时订阅左右手柄各自的电量/充电状态报告，读完即退订，避免影响按键与体感流
- 原生报告未到达时才退化为 report 0x05 的电压估算；该电压比电芯低约 0.6 V（满电约 3.6 V 而非 4.2 V），曲线已按此修正
- 红色 = 低于 30%
- 橙色 = 30-70%
- 绿色 = 70% 以上

### SL/SR 按键没有反应？
1. 检查是否在"SL/SR 按键映射"中设置了映射
2. 默认情况下 SL/SR 是不映射的（空）
3. **注意**：SL/SR 不能映射为 L/R 按钮，会冲突

### 程序崩溃或无法启动？
1. 检查 `config.ini` 是否存在且格式正确
2. 删除 `config.ini` 让程序重新生成默认配置
3. 查看 `joy2win.log` 日志文件

---

## ⚙️ 配置说明

### config.ini
```ini
[Controller]
# 默认连接模式: 0=双手柄, 1=左手柄, 2=右手柄
controller = 0

# 方向: 0=垂直, 1=水平（仅单手柄模式有效）
orientation = 0

# 是否启用 DSU 服务器
enable_dsu = false

# 鼠标模式: 0=禁用, 1=启用
mouse_mode = 0

[Pair_0]
# 手柄组 1 的 SL/SR 映射（空字符串表示不映射）
sll_mapping = 
srl_mapping = 
slr_mapping = 
srr_mapping = 

[Pair_1]
# 手柄组 2 的 SL/SR 映射
sll_mapping = 
srl_mapping = 
slr_mapping = 
srr_mapping = 

# ... Pair_2, Pair_3 同理
```

---

## 🖱️ Raw Input 鼠标（可选，需要装驱动）

默认的鼠标输出走 `SendInput`。SDK 和模拟器都能收到，多数游戏也正常。但**用 Raw Input（`WM_INPUT`）读取鼠标的应用会忽略合成事件**——如果你的游戏里鼠标完全不动，就是它。

这时可以启用 WinUHid 虚拟 HID 鼠标，让系统看到一只真实硬件鼠标。

### 前提

WinUHid 的驱动是**测试签名**的，必须在 Windows 上开启测试签名模式：

```powershell
# 管理员 PowerShell
bcdedit /set testsigning on
# 然后重启
```

重启后桌面右下角会出现「测试模式」水印，这是正常的。

> 开启测试签名会降低系统对驱动签名的校验强度，部分带反作弊的游戏可能拒绝启动。如果你主要玩这类游戏，建议不要开启。

### 安装

**第一步：装驱动**（如果设备管理器里已经有 `WinUHid Virtual HID Enumerator` 就跳过）

WinUHid 官方仓库的 Releases 是空的，没有预编译产物。现成的安装器只有第三方打包的这一个：

```
tools\WinUHid_Manager.exe
```

来源：`https://github.com/TommyWabg/Switch2Connect/releases/download/v1.8_MicrosoftStore/WinUHid_Manager.exe`
SHA-256：`f7ae2a2340dcfc944d3a431cadf4ee01c044c826136e9d348ad8fb3ba478b808`

右键以管理员身份运行，完成后重启。它会开启测试签名、安装证书、注册驱动。

**第二步：编译用户态 DLL**

驱动装好后，`WinUHid.dll` 和 `WinUHidDevs.dll` 仍然缺失——它们是用户态 SDK，不在驱动包里，官方也不提供预编译版本。

双击 **`tools\build-winuhid.bat`**，脚本会：

1. 自动克隆 WinUHid 源码到 `tools\WinUHid-src`
2. 用本机 MSBuild 编译 `WinUHid.dll` 和 `WinUHidDevs.dll`（只编译这两个用户态库，不需要 WDK）
3. 把产物复制到程序目录

需要 Visual Studio 2022 的「使用 C++ 的桌面开发」工作负载。什么都没装的话，脚本会提示去 Visual Studio Installer 补装。

### 确认生效

启动日志里应该出现：

```
INFO - WinUHid mouse available (driver interface 2)
INFO - Raw Input virtual mouse created
INFO - Mouse output: WinUHid (Raw Input)
```

如果出现 `WinUHid driver not installed` 或 `WinUHid DLLs not found`，说明驱动没装好或 DLL 位置不对——程序会自动退回 `SendInput`，不会影响其他功能。

### 配置

```ini
[Controller]
# auto = 有驱动就用虚拟 HID，没有就用 SendInput（默认）
# standard = 只用 SendInput
# winuhid = 强制要求虚拟 HID，缺失时警告并回退
mouse_output = auto
```

---

## 🎮 Steam 配置（可选）

1. 打开 Steam → 设置 → 控制器
2. 选择"基本布局"或"自定义布局"
3. 可以映射 SL/SR 按钮为额外功能

---

## 🔧 常见问题

### Q: 手柄无法连接？
**A:**
1. 确保手柄已开机（按任意键唤醒）
2. 确保电脑蓝牙已开启
3. 按下手柄侧面的同步按钮（小圆点）
4. 重启程序再试

### Q: 没有震动反馈？
**A:**
1. 确保 GUI 中"启用震动反馈"已勾选
2. 确保游戏支持手柄震动
3. 检查 ViGEmBus 驱动是否安装

### Q: 电量显示不准确？
**A:**
- Joy-Con 2 电量是 0-9 级离散值，不是精确到 1% 的连续值
- 红色 = 低于 30%
- 橙色 = 30-70%
- 绿色 = 70% 以上

### Q: SL/SR 按键没有反应？
**A:**
1. 检查是否在"SL/SR 按键映射"中设置了映射
2. 默认情况下 SL/SR 是不映射的（空）
3. 可以映射到 LB/RB、LT/RT 或其他 Xbox 按键

### Q: 可以连接几组手柄？
**A:**
- 最多支持 4 组手柄（8 个 Joy-Con）
- 每组手柄对应一个虚拟 Xbox 360 手柄
- 游戏会识别为 4 个独立的 Xbox 手柄

---

## 📝 更新日志

### v2.2.25（外部审查报告 14 条逐条核查）
按实测与代码证据核查了外部静态审查报告的 14 条，**确认并修复 3 条真问题**，驳回 3 条误报：

- **BUG-09 修复**：右手柄横握（orientation=1）的 `R3` 映射到 `XUSB_GAMEPAD_LEFT_THUMB`，而竖握用的 `RIGHT_THUMB`。同一个按键两种模式不一致，属复制粘贴错误
- **BUG-14 修复**：双手柄鼠标模式切换死角。原逻辑用 `if mode is None ... elif 两侧都抬起`，当「当前侧抬起、另一侧放下」时两个分支都不命中，模式卡在已抬起的那一侧，指针冻结
- **BUG-04 修复**：`Config.set_and_save` 把键写死到 `[Controller]` 段，写 `mac_address` 这类属于 `[Bluetooth]` 的键会被忽略。改为优先定位已包含该键的段
- **驳回 BUG-01（并发）**：`clientSending` 只在 `async with lock` 内读写，左右手柄的命令严格串行，不存在指针失配
- **驳回 BUG-03（振动路由）**：报告数错了参数位置。lambda 有 6 个形参，`pair_id` 传在第 6 个（`user_data`），而 callback 读的正是 `user_data`
- **BUG-08（相对路径）** 属实，但已在 v2.2.20 用 frozen 时 `chdir` 修复
- 其余条目为设计选择或影响极小（详见补丁注释），未做改动

### v2.2.24（回滚 v2.2.23 的 DSU 长度字段改动）
- **v2.2.23 是错的，已回滚**。把长度字段改成「整包长度」后，Eden 完全识别不到体感输入
- 原因：DSU 客户端把这个字段当作 **header 之后的字节数**，自己去加 16。传总长会让它等待一个永远不会完整到达的数据报
- 结论：这里以**实测行为**为准，不以 cemuhook 的文字描述为准。代码里已留下注释警告，避免以后再被"修正"一次
- 保留 v2.2.23 新增的 CRC 回归测试（那条结论是对的：CRC 覆盖完整包且字段清零）

### v2.2.23（DSU 包长度字段修正 —— 已回滚，见 v2.2.24）
- **`_build_packet` 的长度字段写的是 payload 长度**，而 DSU 协议要求整个包的长度（含 16 字节 header）。实测：响应实际 28 字节，字段却声明 12。宽容的客户端（Eden、DS4Windows）不读这个字段所以一直能用，严格的客户端会截断 payload 或把下一个包的头部吞进去
- 修正为 `len(payload) + 16`
- 顺带修正一个把错误行为固化下来的旧测试：`test_dsu_info_is_one_packet_per_slot` 原先断言长度字段等于 16（payload 长度），与实际协议相反
- 新增两条回归：长度字段必须等于真实包长；CRC32 必须能由「CRC 字段清零后的完整包」重新算出来

### v2.2.22（修复调整震动强度闪退）
- **闪退原因**：`on_rumble_strength_changed` 与 `on_mouse_sensitivity_changed` 把 `controller_tabs` 当成 dict 用了 `.values()`，而它是 **list**。`AttributeError` 抛在 Qt 槽函数里，PyQt5 从 5.5 起会直接调用 `qFatal()`，进程无提示退出、也没有 traceback
- 修正为遍历 list；两处同步逻辑都受影响，所以改鼠标灵敏度其实也会崩
- **新增全局异常钩子** `_install_exception_hooks()`：接管 `sys.excepthook` 与 `threading.excepthook`，把堆栈写进 `joy2win.log` 并弹窗提示，而不是让窗口消失。这类错误以后不会再把程序直接带走
- 新增 GUI 槽回归测试：真实构造 `ControllerPairTab` 并调用两个回调，防止同类「属性类型假设错误」再次溜过

### v2.2.21（GUI 震动强度）
- 每个手柄组页面新增「震动强度」数值框（0–100%，步进 5），与「启用震动反馈」并列
- 改动**立即生效**：调用 `RumbleStream.set_strength()` 改振幅缩放，下一帧即使用新值，不需要重连或重启
- 该值全局共享（所有手柄组一个配置键），改一个页面会同步到其余页面，并写回 `config.ini` 的 `rumble_strength`
- `0` 等于静音；`100` 是协议安全上限（约满幅的 44%，与 joy2con `RUMBLE_MAX=450` 一致）。出现敲击声时调低到 70~80 通常即可

### v2.2.20（全项目检查 + 单文件 exe）
- **修复 `reset_pair_state` 的 `NameError`**：批量替换鼠标调用时，`old_state['mouse'].release(...)` 被子串规则误伤成 `old_get_mouse_output()`，重连清理时会抛异常
- **修复虚拟鼠标设备泄漏**：`release_mouse_output()` 定义了却从未调用，退出时 `WinUHidMouseDestroy` 不执行。现已在 `main.shutdown()` 末尾释放
- **修复退出时按键卡住**：新增 `release_all_buttons()`，退出前释放左右中键——否则退出瞬间按着鼠标键，系统会一直处于按下状态
- 补齐 `control_type/__init__.py` 与 `controllers/__init__.py`：此前依赖隐式命名空间包，PyInstaller 收集不可靠，打包后可能 `ModuleNotFoundError`
- 打包配置补充 `WinUHid.dll` / `WinUHidDevs.dll` 与新模块的 `hiddenimports`；frozen 时 `_find_dll` 会先查 exe 所在目录，用户可以覆盖内置版本
- `gui.main()` 在 frozen 模式下把工作目录锚定到 exe 所在目录，`config.ini` 与 `joy2win.log` 不再受启动方式影响
- 移除托盘「停止震动」菜单项（`RumbleStream.silence_all()` 保留，需要时可恢复入口）
- 产物：`dist\Joy2Win-vgamepad.exe`，单文件 40 MB，内置 Python、PyQt5、bleak、vgamepad、pynput、ViGEmClient 与 WinUHid SDK

### v2.2.19（Raw Input 鼠标实测通过）
- **实测确认可用**：本机编译出 `WinUHid.dll` / `WinUHidDevs.dll` 后，日志输出
  `WinUHid mouse available (driver interface 1)` → `Raw Input virtual mouse created` → `Mouse output: WinUHid (Raw Input)`，`move()` 返回成功
- 修复 `build-winuhid.bat` 的产物路径：每个项目输出到 `<Project>\build\Release\x64`，脚本原来查的是 `<源码根>\build\Release\x64`，所以编译成功但复制失败
- `.gitignore` 增加 `WinUHid.dll`、`WinUHidDevs.dll`、`tools/WinUHid-src/`、`tools/*.exe`，避免本地构建产物进入仓库
- 单元测试改为 stub 掉驱动检测，避免在有驱动的机器上反复创建/销毁真实虚拟设备

### v2.2.18（WinUHid 一键构建脚本）
- 新增 `tools/build-winuhid.bat`：自动克隆源码、编译 `WinUHid.dll` 与 `WinUHidDevs.dll`、复制到程序目录。只编译用户态库，不碰驱动项目，因此不需要 WDK
- 新增 `tools/WinUHid_Manager.exe`（第三方驱动安装器，10.5 MB，SHA-256 已核对）。背景：WinUHid 官方 Releases **为空**，没有任何预编译产物；这是目前唯一现成的一键驱动安装器
- README 的「Raw Input 鼠标」章节改为两步流程：先装驱动，再编译用户态 DLL，并说明各自的来源与校验值

### v2.2.17（鼠标输出后端：可选 Raw Input 虚拟 HID）
- 新增 `mouse_output`（`auto` / `standard` / `winuhid`）。`auto` 在检测到 WinUHid 驱动与 DLL 时创建真实虚拟 HID 鼠标，否则退回 `SendInput`
- 为什么需要：`SendInput` 注入的是合成事件，SDK/模拟器都能收到，但**用 Raw Input（`WM_INPUT`）读鼠标的应用可能直接忽略**。WinUHid 走的是真实 HID 协议栈，这类应用看到的就是硬件
- 抽象为 `control_type/virtual_mouse.py`：`StandardMouse`（pynput）与 `WinUHidMouse`（ctypes）共用同一接口（`move` / `button` / `scroll`），双手柄与单手柄的 19 处调用点统一走它
- 设备用 `WinUHidMouseCreate(NULL)` 创建：不构造 `WINUHID_PRESET_DEVICE_INFO`，避免 ctypes 结构体对齐错误导致 DLL 读越界崩溃
- 驱动或 DLL 缺失时静默降级并在日志里说明，功能不会因为缺驱动而不可用

### v2.2.16（GUI 鼠标灵敏度）
- 每个手柄组页面新增「鼠标灵敏度」数值框（10–400%，步进 10），改动即时生效并写回 `config.ini`，无需重启
- 该值是全局的（所有手柄组共用），改一个页面会同步刷新其余页面，避免界面与实际行为不一致
- `Config.set_and_save()` 只改单个键：用 configparser 读回再写，`[Bluetooth]`、`[Pair_N]` 等节原样保留；写前留 `config.ini.bak`。实测写入后另起进程能正确读回，其余键值不变
- 若 `config.ini` 缺失或只读，改动仍在内存生效，只是不持久化

### v2.2.15（鼠标灵敏度与触发距离可调）
- 新增 `mouse_sensitivity`（10–400，默认 100）：`100` 保持原来的 6 帧平滑手感，`200` 快一倍，`50` 慢一半。之前这个系数写死为 `/6`，只能接受
- 新增 `mouse_surface_threshold`（8–4095，默认 512）：自动鼠标模式的距离阈值。之前硬编码在两个模块里，手柄贴桌面不触发或拿在半空就触发时都无从调整
- 两者抽到 `control_type/mouse_scroll.py`，双手柄与单手柄共用，避免再次各自实现一套；每 6 ms 读一次单例配置，改 `config.ini` 无需重启
- 越界值自动收敛到合法区间，不会因为写入错误数值而失控

### v2.2.14（鼠标模式配置生效）
- **`config.ini` 的 `mouse_mode` 从未被读取**：`config.py` 解析了 0/1/2 三档并做校验，但没有任何代码读它。实际行为只由 GUI 复选框的布尔值决定，文档承诺的 "Automatic / Always" 两档等于不存在
- 现在 `is_mouse_enabled()` 会回落到 `config.mouse_mode`：0 关闭、1 自动（贴桌面才进入鼠标模式）、2 始终（跳过距离传感器）。GUI 复选框作为运行时覆盖，勾选对应模式 1
- 模式 2 下两只 Joy-Con 同时贴桌面时由左手柄驱动指针（与自动模式的优先顺序一致）
- 顺带修正 `config-example.ini` 的说明，去掉"对双手柄无用"这句已经不成立的注释

### v2.2.13（鼠标滚轮修复）
- **滚轮从未工作**：`scroll_decoder` 返回 `-32767..32767`，而消费端做 `int(value / 32768)`——这个区间内所有值都截断为 `0`，只有恰好 `-32768` 才得到 `-1`。双手柄模式和单手柄模式都是这个写法，所以滚轮完全无效
- 改为累积余数并输出整格（`control_type/mouse_scroll.py` 的 `scroll_notches`，`SCROLL_NOTCH = 131072`）：满偏约 15 格/秒，小幅倾斜也能累积出格子而不是每次被舍掉
- 顺带确认无问题的部分：鼠标位移来自传感器增量（`struct.unpack("<hh", mouseDatas[:4])`）经差分累加、`mouse.move` 走 pynput 的相对移动（SendInput），断开时释放左右键并清零目标

### v2.2.12（功能位 FEATSEL：幻影 ZL/ZR）
- `JOY2_INIT/FINALIZE/START_SENSOR_DATA` 的功能位 `0xFF` → `0xB7`，即只清掉 bit3(`0x08`) 与 bit6(`0x40`)
- 依据：Switch2Connect 注明「开启全部功能位会让 Joy-Con 输出额外报告字段，表现为 ZL/ZR 幻影按下、持续触发」，其可用版本用 `0x94`；jacc/joy2con 用 `0x37`。两者唯一的共同点是 **bit3 与 bit6 保持关闭**，所以只清这两位，其余位维持原状，避免传感器或震动相关位被一起关掉
- 新增回归测试锁定这三位

### v2.2.11（震动节拍与链路，实测闭环）
- **最终节拍 30 ms**（原 12 ms）。12 ms 是 SDL/joy2con 为**波形透传**设的值；本项目从两个 XInput 标量合成，包络恒定，手柄收到一帧会保持到下一帧，20–30 fps 完全等效。而实测这条 Windows BLE 链路的上限只有约 44 fps（`max` 反复出现 16 ms = 一个连接事件），按 12 ms 发必然填满队列，零振幅停止帧只能排队等待——这正是「日志 off 了但手柄还在震」
- 取消失败的 GATT 写超时：`asyncio.wait_for` 取消 WinRT 操作会让该帧**数据丢失**并抛 `InvalidStateError`，停止帧一旦中招就永远到不了手柄。改为直接 await + `asyncio.shield()` 保护在途帧
- 修复 `_tune_report_rate()` 提前 `return`：descriptor 写完就返回，`throughput_optimized` 连接参数请求**从未执行**。现在两件事都做，且在 `connect()` 成功后立即请求
- 震动回调改走同步快路径 `update_sync()`：稳态只改两个整数（GIL 原子），不再每次 `run_coroutine_threadsafe` 投递协程，消除调度风暴
- 默认振幅 `0x060`(96) → `0x1C4`(452)，与 joy2con `RUMBLE_MAX=450`、JoeGeC、SDL 一致
- 启动调用 `timeBeginPeriod(1)` 提高定时器精度，退出还原
- **实机验证：长按震动，松开后立即停止**

### v2.2.8 – v2.2.10（连接参数、写超时、回调风暴）
- **Bug**：`_tune_report_rate()` 写完 report-rate descriptor 就 `return`，后面的首选连接参数请求**从未执行过**。日志里那句 `High report-rate descriptor written (85 00)` 是真的，但它只提高「手柄→PC 的上报率」，不影响「PC→手柄的写入速率」
- **机制**：BLE 的每次特征写入要等一个连接事件。Windows 默认连接间隔约 30 ms，而 `Switch2Connect` 项目实测健康链路单次 rumble 写入耗时 **11–38 ms**——比一包 HD 帧承载的约 12 ms 还长。于是帧与帧之间出现空白（听感"断续"），零振幅停止帧又要排在未完成的写之后（听感"停不下来"）
- **修复**：descriptor 与连接参数改为**两件事都做**，且在 `connect()` 成功后立即请求 `throughput_optimized`，让其后所有命令与震动写都跑在更短的连接间隔上；同时兼容 bleak 的 `_device` / `_requester` 两种落点和 `_async` 两种签名
- 新增日志 `BLE connection interval: throughput-optimized requested (SUCCESS)`；失败时明确提示「震动仍受默认连接间隔限制」，不再静默
- **移除写超时**：`asyncio.wait_for` 取消 WinRT 的 GATT 写会让该帧**数据丢失**，并在完成回调里抛 `InvalidStateError`。停止帧一旦被这样取消，手柄就永远收不到停止指令。改为直接 await，并用 `asyncio.shield()` 保护在途帧；取消流时先补发一次停止帧再退出
- **回调改同步快路径**：`vibration_callback` 原本每次 `run_coroutine_threadsafe` 投递协程，游戏每秒几十次回调造成调度风暴，把 12 ms 的发送任务挤到 37 ms/帧（实测 `write avg 0.7 ms` 却只跑 12 fps）。新增 `update_sync()`，稳态只改两个整数（GIL 原子），不碰事件循环
- 新增 `Detected Left/Right Joy-Con from GATT` 与广播 PID 判侧、`STOP_REPEAT` 宽间隔停止、托盘「停止震动」

### v2.2.7（振动振幅修正：默认值过小）
- 默认振幅 `0x060`（96，约 9%）→ `0x1C4`（452，约 44%）。所有参考实现的上限都落在同一档：joy2con `RUMBLE_MAX=450`、JoeGeC `SAFE_AMPLITUDE≈452`、SDL `29000/65535×1023≈452`。之前的 96 只有它们的两成，震动过弱导致连续性感知差（听起来"断续"），且强度变化太小时"停止"不易被感知
- `rumble_strength`（0-100）仍可下调；默认 100 表示使用协议安全上限
- 逐项复核了振动链路：左右特征 UUID、`00` + `0x50|seq` + 3×5B 帧结构、40-bit 位布局、`0x187`/`0x112` 频率码、XInput 大小马达映射、连接提示音 sample `0x03` —— 均与 joy2con 一致，无偏差

### v2.2.6（震动链路自适应 + 一键静音）
- **停止帧改为宽间隔**：从「12 帧 × 12 ms」改为「4 帧 × 40 ms」。原来那 12 帧是在 12 ms 间隔下连发，等于继续往同一个已经拥塞的 Windows BLE 队列里塞包，后面的停止帧反而更难发出。宽间隔让每一帧独立竞争队列
- **发送节拍自适应**：连续 5 帧写入耗时接近节拍时，自动把间隔放宽到 30 ms 并写一条日志，避免链路跟不上时持续积压
- **补零仅在 MTU 足够时启用**：MTU < 45 时直接发原始 17 字节（这个长度已验证可用），不再生成 20 字节这种从未实测过的中间长度
- **托盘菜单新增「停止震动」**：随时强制所有手柄静音。它同时是一个诊断手段——若它也不能停，说明停止包根本没到达手柄，问题在链路而不是流的逻辑
- 移除 v2.2.5 引入的中性载频帧（那是 Switch 2 **Pro** 手柄的实现，不适用于 Joy-Con 2）

### v2.2.5（对齐 joy2con：更正停止帧、广播判侧、节拍诊断）
- **更正**：`0x0E1`/`0x1E1` 那套"中性载频"是 **Switch 2 Pro 手柄**（NS2Pro-Bridge）的静止帧，不能套到 Joy-Con 2。Joy-Con 2 的停止就是 `0x187`/`0x112` 载频 + 零振幅——joy2con 的 `Rumbler` 停止时发 `(freq_code(320), 0, freq_code(160), 0)` 后就不再发送。本项目已恢复为此做法
- **数据包补零到 42 字节**（上限受 MTU-3 约束）：对齐 joy2con 的 `pkt + bytes(42 - len(pkt))`
- **发送节拍改为绝对时间调度**：原来 `await write; await sleep(12ms)` 会把每次写入耗时叠加进周期，实际节拍越跑越慢且忽长忽短
- **广播阶段判定左右**：Nintendo 广播厂商数据的第 5-6 字节（小端）是产品 ID，`0x2067` 左 / `0x2066` 右 / `0x2069` Pro，与 joy2con 一致。扫描时即可确定，不必等连接
- 连接后再用振动特征 UUID 复核一次（左 `289326cb…` / 右 `fa19b0fb…`），覆盖 UI 里缺失或选错的值
- **新增节拍诊断日志**（每 2 秒，仅震动期间）：`[RUMBLE] pair=0 Left: 83 fps, write avg 8.2 ms, max 31.0 ms`。帧率明显低于 1/间隔，或写入耗时接近间隔，说明 BLE 链路跟不上，停止包只能排在过期帧后面

### v2.2.3 / v2.2.4（实机震动修复：停不下来）
- **根因 1**：向 rumble 特征写入时用了 bleak 默认的 write-with-response，每帧都要等 ATT 确认，12 ms 节拍根本跑不动 → 发送队列积压 → 零振幅停止帧排在几百个旧帧后面发不出去。改为按 GATT 属性判定，默认 write-without-response
- **根因 2**：`_send_stop` 无论成功与否都把状态标记为"已停止"，失败后不再重试。现在只有写成功才置位，失败按 50 ms 间隔重试 3 次
- **根因 3**：断开手柄时只取消发送任务、从不发停止帧，链路一断就再也发不出去。现在 `disconnect_pair_by_id` 在断开前先对左右两侧 `await stream.stop()`
- **根因 4**：停止帧用无应答写发出，本质是"发完就不管"，单帧丢失后手柄只能等自身看门狗超时——表现为日志已 `rumble off` 但手柄还在震一两秒。现在停止时连发 12 帧零振幅（144 ms），第一帧请求应答确认；burst 期间若游戏重新开始震动会立即中断 burst 恢复输出
- 每次写入加 250 ms 超时，单次 GATT 写卡住不再拖死整个流（这也是 idle 兜底失效的原因）
- 无新强度时的自动停止从 5 秒缩短到 1.5 秒，避免手柄长时间空转
- 新增起停日志：`[RUMBLE] pair=0 Left: rumble on (large=.., small=..)` / `rumble off`，便于确认震动是否真的下发；`rumble off` 现在是在整串停止帧发完之后才打印
- 修复 GUI「断开出错: 」显示空消息：并发超时的异常字符串为空，现在给出明确文案并把等待上限提到 8 秒
- 退出收尾对已关闭的事件循环做了保护，避免 `call_soon_threadsafe` 抛错跳过 DSU 清理
- 新增回归测试：rumble 必须用 write-without-response、只有 write 属性时回退到应答写

### v2.2.2（环境与测试修复）
- 新增 `tests/__init__.py`：系统的 site-packages 里若存在同名 `tests` 包（例如 `color-matcher` 会装一个），`python -m unittest tests.test_core` 会解析到那个包并报 `ModuleNotFoundError`
- 修复降级路径的真实缺陷：legacy 震动帧写入失败时也会被标记为"已播放"，导致一次瞬时 GATT 错误后彻底静音；现在只有写成功才置位，失败按 0.1 s 节拍重试
- 手柄重连（client 对象变化）时重置降级标志与失败计数，重新尝试 HD 通道
- 启动日志打印实际解释器与 bleak/PyQt5/vgamepad/pynput 版本，bleak 主版本不是 0 时给出明确警告
- README 的源码安装步骤改为强制使用 Python 3.12 + venv，并新增 `tests/smoke_gui_startup.py` 无头启动冒烟脚本

### v2.2.1（生命周期与死代码清理）
- 鼠标线程加 stop event + join，退出时由 `main.shutdown()` 统一停止，不再靠 daemon 线程随进程消失
- 接通低电量告警：连续 3 帧低于 20% 且未在充电时写一条日志，回升到 30% 以上重新布防；只记日志，不弹模态框
- 删除从未调用的 `notify_low_battery()` / `alertSent` 及冗余 import
- 删除无人引用的 `button_mapping.py`（DS4 残留，与实际 XUSB 映射不一致）

### v2.2.0（HD Rumble 输出改造）
- 移除固定 stored effect（每次都播放约 1 秒的提示音）以及非法的停止帧 `0a0000…`
- 改为向 L/R 各自的 rumble 特征写原生 HD 帧：`00` + 16 字节 group（`0x50|counter` + 3 个 5 字节子帧），12 ms 节拍、零振幅停止帧、5 秒无更新自动停
- 保留 XInput 低频/高频双通道（不再合并成 `max(large, small)`），左右手柄各写自己的特征
- 振幅上限默认取社区实机值，可用 `config.ini` 的 `rumble_strength` 调；写入失败 3 次自动降级回固件预置震动
- 退出时先发停止帧再断开 BLE，断开手柄时取消对应流

### v2.1.2（连接与协议优化）
- 修复 Win11 提频代码直接依赖 `winrt` 私有 API 导致连接被误判为失败的问题，改为优先写 report-rate descriptor，整段异常隔离
- 修复主动断开触发 disconnected_callback 重复清理、以及 GUI/管理器 MAC 格式不一致导致「断开手柄」不生效
- 扫描加超时/取消与必停 scanner；连接超时取消后台协程；退出改为正常释放 BLE、DSU 端口与事件循环
- 摇杆改为按手柄自适应校准（静止窗口学中位 + 四方向独立行程），死区由 3000 降到 1200
- 电量曲线按 Joy-Con 2 上报电压偏低 0.6 V 修正；µs 时间戳改无符号；IMU 系数对齐社区文档
- DSU 改为每组独立开关、体感在鼠标模式下持续上报、包序号按槽位独立；端口占用不再抛异常
- 命令响应订阅保持到连接结束，LED 写入重发，响应按 client 隔离

### v2.0.0
- ✅ 支持最多 4 组手柄同时连接
- ✅ 多选项卡界面，每组独立设置
- ✅ SL/SR 按键自定义映射
- ✅ 每组独立的鼠标控制开关
- ✅ 每组独立的 DSU 体感映射
- ✅ 系统托盘最小化支持
- ✅ 手动连接模式（非持续扫描）

### v1.0.0
- ✅ PyQt5 GUI 界面
- ✅ 实时显示手柄状态和电量
- ✅ 震动反馈支持
- ✅ DSU 体感服务器
- ✅ 打包成 EXE

---

## 📚 依赖项目

- [vgamepad](https://github.com/yannbouteiller/vgamepad) - 虚拟 Xbox 360 手柄
- [ViGEmBus](https://github.com/ViGEm/ViGEmBus) - 虚拟手柄驱动
- [Bleak](https://github.com/hbldh/bleak) - 蓝牙 BLE 通信
- [PyQt5](https://www.riverbankcomputing.com/software/pyqt/) - GUI 界面

---

## ⚠️ 注意事项

**为什么这个项目是临时的？**
目前 Joy-Con 2 手柄仅在 Windows 上工作。其他操作系统由于手柄通信协议的原因不支持。

> [!NOTE]
> 我不是蓝牙通信专家，在开发过程中得到了很多人的帮助。

---

## 👥 作者

**Made by Octokling;big2cat**

感谢以下人员的帮助：
- narr_the_reg
- ndeadly
