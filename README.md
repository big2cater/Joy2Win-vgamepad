# 🎮 Joy2Win-vgamepad

使用灵码编辑器修改，去除了 vjoy 并添加了 ViGEmBus 的支持。支持多组 Joy-Con 同时连接，双手柄体感正常，游戏震动也能实现。

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
```bash
# 1. 克隆仓库
git clone https://github.com/big2cater/Joy2Win-vgamepad.git
cd Joy2Win-vgamepad

# 2. 安装依赖
pip install -r requirements-gui.txt

# 3. 运行程序
python gui.py
```

---

## 📖 详细安装指南

### 1. 克隆仓库
```bash
git clone https://github.com/big2cater/Joy2Win-vgamepad.git
cd Joy2Win-vgamepad
```

### 2. 安装依赖
```bash
pip install -r requirements-gui.txt
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
python gui.py
```
或者双击运行 `start-gui.bat`

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

### 电量显示不准确？
- 电量显示可能有延迟，连接后几秒会更新
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
- 电量显示可能有延迟，连接后几秒会更新
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
