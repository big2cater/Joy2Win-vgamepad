"""
Joy-Con 到 DS4 按钮映射配置文件
修改此文件来自定义按钮映射
"""

import vgamepad

# ==================== 双手柄模式映射 (duo_joycon.py) ====================
# DS4 DPad 值: 0=N, 1=NE, 2=E, 3=SE, 4=S, 5=SW, 6=W, 7=NW, 8=none
DUO_MAPPING = {
    "Left": {
        # Joy-Con 按钮: DS4 按钮
        "ZL": "LEFT_TRIGGER",  # 左扳机 (模拟量)
        "L": vgamepad.DS4_BUTTONS.DS4_BUTTON_SHOULDER_LEFT,   # L1
        "L3": vgamepad.DS4_BUTTONS.DS4_BUTTON_THUMB_LEFT,      # L3 (左摇杆按下)
        "Up": "DPAD_UP",        # 十字键上
        "Down": "DPAD_DOWN",    # 十字键下
        "Left": "DPAD_LEFT",    # 十字键左
        "Right": "DPAD_RIGHT",  # 十字键右
        "Minus": vgamepad.DS4_BUTTONS.DS4_BUTTON_SHARE,        # Share
        "Capture": vgamepad.DS4_SPECIAL_BUTTONS.DS4_SPECIAL_BUTTON_TOUCHPAD,  # 触摸板
    },
    "Right": {
        # Joy-Con 按钮: DS4 按钮
        "ZR": "RIGHT_TRIGGER",  # 右扳机 (模拟量)
        "R": vgamepad.DS4_BUTTONS.DS4_BUTTON_SHOULDER_RIGHT,  # R1
        "R3": vgamepad.DS4_BUTTONS.DS4_BUTTON_THUMB_RIGHT,     # R3 (右摇杆按下)
        "A": vgamepad.DS4_BUTTONS.DS4_BUTTON_CROSS,            # ✕
        "B": vgamepad.DS4_BUTTONS.DS4_BUTTON_CIRCLE,           # ○
        "X": vgamepad.DS4_BUTTONS.DS4_BUTTON_SQUARE,           # □
        "Y": vgamepad.DS4_BUTTONS.DS4_BUTTON_TRIANGLE,         # △
        "Plus": vgamepad.DS4_BUTTONS.DS4_BUTTON_OPTIONS,       # Options
        "Home": vgamepad.DS4_SPECIAL_BUTTONS.DS4_SPECIAL_BUTTON_PS,  # PS 键
        "GameChat": vgamepad.DS4_SPECIAL_BUTTONS.DS4_SPECIAL_BUTTON_TOUCHPAD,
    }
}

# ==================== 单手柄模式映射 (single_joycon.py) ====================
# 格式: "方向": {按钮映射}
SINGLE_MAPPING = {
    "Left": {
        "0": {  # 垂直握持
            "ZL": "LEFT_TRIGGER",
            "L3": vgamepad.DS4_BUTTONS.DS4_BUTTON_THUMB_LEFT,
            "Up": "DPAD_UP",
            "Down": "DPAD_DOWN",
            "Left": "DPAD_LEFT",
            "Right": "DPAD_RIGHT",
            "Minus": vgamepad.DS4_BUTTONS.DS4_BUTTON_SHARE,
            "SLL": vgamepad.DS4_BUTTONS.DS4_BUTTON_SHOULDER_LEFT,   # SL -> L1
            "SRL": vgamepad.DS4_BUTTONS.DS4_BUTTON_SHOULDER_RIGHT,  # SR -> R1
            "Capture": vgamepad.DS4_SPECIAL_BUTTONS.DS4_SPECIAL_BUTTON_TOUCHPAD,
        },
        "1": {  # 水平握持 (方向键旋转90度)
            "ZL": "LEFT_TRIGGER",
            "L3": vgamepad.DS4_BUTTONS.DS4_BUTTON_THUMB_LEFT,
            "Up": "DPAD_LEFT",      # 物理上变成左
            "Down": "DPAD_RIGHT",   # 物理上变成右
            "Left": "DPAD_DOWN",    # 物理上变成下
            "Right": "DPAD_UP",     # 物理上变成上
            "Minus": vgamepad.DS4_BUTTONS.DS4_BUTTON_OPTIONS,
            "SLL": vgamepad.DS4_BUTTONS.DS4_BUTTON_SHOULDER_LEFT,
            "SRL": vgamepad.DS4_BUTTONS.DS4_BUTTON_SHOULDER_RIGHT,
            "Capture": vgamepad.DS4_SPECIAL_BUTTONS.DS4_SPECIAL_BUTTON_TOUCHPAD,
        },
    },
    "Right": {
        "0": {  # 垂直握持
            "ZR": "RIGHT_TRIGGER",
            "R3": vgamepad.DS4_BUTTONS.DS4_BUTTON_THUMB_RIGHT,
            "A": vgamepad.DS4_BUTTONS.DS4_BUTTON_CROSS,
            "B": vgamepad.DS4_BUTTONS.DS4_BUTTON_CIRCLE,
            "X": vgamepad.DS4_BUTTONS.DS4_BUTTON_SQUARE,
            "Y": vgamepad.DS4_BUTTONS.DS4_BUTTON_TRIANGLE,
            "Plus": vgamepad.DS4_BUTTONS.DS4_BUTTON_OPTIONS,
            "SRR": vgamepad.DS4_BUTTONS.DS4_BUTTON_SHOULDER_RIGHT,
            "SLR": vgamepad.DS4_BUTTONS.DS4_BUTTON_SHOULDER_LEFT,
            "Home": vgamepad.DS4_SPECIAL_BUTTONS.DS4_SPECIAL_BUTTON_PS,
            "GameChat": vgamepad.DS4_SPECIAL_BUTTONS.DS4_SPECIAL_BUTTON_TOUCHPAD,
        },
        "1": {  # 水平握持
            "ZR": "RIGHT_TRIGGER",
            "R3": vgamepad.DS4_BUTTONS.DS4_BUTTON_THUMB_LEFT,
            "A": vgamepad.DS4_BUTTONS.DS4_BUTTON_CIRCLE,
            "B": vgamepad.DS4_BUTTONS.DS4_BUTTON_TRIANGLE,
            "X": vgamepad.DS4_BUTTONS.DS4_BUTTON_SQUARE,
            "Y": vgamepad.DS4_BUTTONS.DS4_BUTTON_CROSS,
            "Plus": vgamepad.DS4_BUTTONS.DS4_BUTTON_OPTIONS,
            "SRR": vgamepad.DS4_BUTTONS.DS4_BUTTON_SHOULDER_RIGHT,
            "SLR": vgamepad.DS4_BUTTONS.DS4_BUTTON_SHOULDER_LEFT,
            "Home": vgamepad.DS4_SPECIAL_BUTTONS.DS4_SPECIAL_BUTTON_PS,
            "GameChat": vgamepad.DS4_SPECIAL_BUTTONS.DS4_SPECIAL_BUTTON_TOUCHPAD,
        },
    }
}

# 可用的 DS4 按钮列表（供参考）
AVAILABLE_DS4_BUTTONS = {
    # 普通按钮
    "CROSS": vgamepad.DS4_BUTTONS.DS4_BUTTON_CROSS,           # ✕
    "CIRCLE": vgamepad.DS4_BUTTONS.DS4_BUTTON_CIRCLE,         # ○
    "SQUARE": vgamepad.DS4_BUTTONS.DS4_BUTTON_SQUARE,         # □
    "TRIANGLE": vgamepad.DS4_BUTTONS.DS4_BUTTON_TRIANGLE,     # △
    "L1": vgamepad.DS4_BUTTONS.DS4_BUTTON_SHOULDER_LEFT,      # L1
    "R1": vgamepad.DS4_BUTTONS.DS4_BUTTON_SHOULDER_RIGHT,     # R1
    "L3": vgamepad.DS4_BUTTONS.DS4_BUTTON_THUMB_LEFT,         # L3
    "R3": vgamepad.DS4_BUTTONS.DS4_BUTTON_THUMB_RIGHT,        # R3
    "SHARE": vgamepad.DS4_BUTTONS.DS4_BUTTON_SHARE,           # Share
    "OPTIONS": vgamepad.DS4_BUTTONS.DS4_BUTTON_OPTIONS,       # Options
    # 特殊按钮
    "PS": vgamepad.DS4_SPECIAL_BUTTONS.DS4_SPECIAL_BUTTON_PS,
    "TOUCHPAD": vgamepad.DS4_SPECIAL_BUTTONS.DS4_SPECIAL_BUTTON_TOUCHPAD,
    # 扳机（模拟量，不是按钮）
    "L2": "LEFT_TRIGGER",
    "R2": "RIGHT_TRIGGER",
}
