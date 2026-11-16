# -*- coding: utf-8 -*-
"""Mouse output backends.

``StandardMouse`` injects events with pynput, which uses Win32 ``SendInput``.
That works for SDL-based software and most games, but applications reading the
mouse through Raw Input (``WM_INPUT``) may ignore synthetic events.

``WinUHidMouse`` asks the WinUHid driver for a real virtual HID mouse, so those
applications see genuine hardware. WinUHid is optional: it needs its
test-signed driver installed and the two DLLs shipped next to the program. When
either is missing, everything silently stays on ``StandardMouse``.

The device is created with ``WinUHidMouseCreate(NULL)`` on purpose. The preset
info struct would have to match the DLL's layout exactly; passing NULL lets the
DLL use its built-in Microsoft Precision Mouse identifiers, which removes a
whole class of ctypes layout bugs.
"""

import ctypes
import sys
import threading
from pathlib import Path

from config import Config
from logger_config import info, warning, debug

BTN_LEFT = 0
BTN_RIGHT = 1
BTN_MIDDLE = 2

# WinUHidMouseReportScroll takes 1/120th of a detent, same scale as WHEEL_DELTA.
SCROLL_UNITS_PER_NOTCH = 120
# Logical min/max of the motion fields in the mouse report descriptor.
DELTA_LIMIT = 32767


def _find_dll(name):
    """Locate a WinUHid DLL next to the program or in its runtime folders.

    A frozen build has to look beside the executable as well: when the DLLs are
    bundled into the onefile archive they land in sys._MEIPASS, but users who
    drop their own build next to the exe expect that to win.
    """
    candidates = []
    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).resolve().parent)
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(Path(meipass))
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
    candidates.extend((root, root / "runtime", root / "drivers"))
    for directory in candidates:
        candidate = directory / name
        if candidate.is_file():
            return candidate
    return None


class _WinUHidApi:
    """ctypes binding for the mouse subset of WinUHidDevs.dll."""

    def __init__(self):
        self.core = None
        self.devs = None
        self.version = 0
        self._load()

    def _load(self):
        core_path = _find_dll("WinUHid.dll")
        devs_path = _find_dll("WinUHidDevs.dll")
        if core_path is None or devs_path is None:
            debug("WinUHid DLLs not found; staying on SendInput mouse output")
            return
        try:
            self.core = ctypes.CDLL(str(core_path))
            self.devs = ctypes.CDLL(str(devs_path))
        except OSError as exc:
            debug(f"WinUHid DLL load failed: {exc}")
            self.core = self.devs = None
            return
        try:
            self.version = int(self.core.WinUHidGetDriverInterfaceVersion())
        except Exception as exc:
            debug(f"WinUHidGetDriverInterfaceVersion failed: {exc}")
            self.version = 0
        if self.version <= 0:
            info("WinUHid driver not installed; mouse output stays on SendInput")
            self.core = self.devs = None
            return
        self._bind()
        info(f"WinUHid mouse available (driver interface {self.version})")

    def _bind(self):
        devs = self.devs
        devs.WinUHidMouseCreate.argtypes = [ctypes.c_void_p]
        devs.WinUHidMouseCreate.restype = ctypes.c_void_p
        devs.WinUHidMouseReportMotion.argtypes = [
            ctypes.c_void_p, ctypes.c_short, ctypes.c_short
        ]
        devs.WinUHidMouseReportMotion.restype = ctypes.c_bool
        devs.WinUHidMouseReportButton.argtypes = [
            ctypes.c_void_p, ctypes.c_ubyte, ctypes.c_bool
        ]
        devs.WinUHidMouseReportButton.restype = ctypes.c_bool
        devs.WinUHidMouseReportScroll.argtypes = [
            ctypes.c_void_p, ctypes.c_short, ctypes.c_bool
        ]
        devs.WinUHidMouseReportScroll.restype = ctypes.c_bool
        devs.WinUHidMouseDestroy.argtypes = [ctypes.c_void_p]
        devs.WinUHidMouseDestroy.restype = None


class _Backend:
    """Common surface used by the duo and single mouse paths."""

    name = "?"

    def move(self, dx, dy):
        raise NotImplementedError

    def button(self, index, down):
        raise NotImplementedError

    def scroll(self, notches_x, notches_y):
        raise NotImplementedError

    def close(self):
        pass


class StandardMouse(_Backend):
    """pynput / SendInput backend."""

    name = "SendInput"

    def __init__(self):
        self._controller = None
        self._buttons = {}
        try:
            from pynput.mouse import Button, Controller
            self._controller = Controller()
            self._buttons = {
                BTN_LEFT: Button.left,
                BTN_RIGHT: Button.right,
                BTN_MIDDLE: Button.middle,
            }
        except Exception as exc:
            warning(f"Mouse control unavailable: {exc}")

    def move(self, dx, dy):
        if self._controller is None or (not dx and not dy):
            return False
        self._controller.move(int(dx), int(dy))
        return True

    def button(self, index, down):
        if self._controller is None:
            return False
        target = self._buttons.get(int(index))
        if target is None:
            return False
        if down:
            self._controller.press(target)
        else:
            self._controller.release(target)
        return True

    def scroll(self, notches_x, notches_y):
        if self._controller is None or (not notches_x and not notches_y):
            return False
        self._controller.scroll(int(notches_x), int(notches_y))
        return True


class WinUHidMouse(_Backend):
    """Virtual HID mouse; visible to Raw Input consumers."""

    name = "WinUHid (Raw Input)"

    def __init__(self, api):
        self._api = api
        self._device = None
        self._lock = threading.Lock()
        device = api.devs.WinUHidMouseCreate(None)
        if not device:
            warning("WinUHid mouse creation failed (error "
                    f"{ctypes.GetLastError()}); falling back to SendInput")
            return
        self._device = device
        info("Raw Input virtual mouse created")

    @property
    def available(self):
        return self._device is not None

    @staticmethod
    def _clamp(value):
        return max(-DELTA_LIMIT, min(DELTA_LIMIT, int(value)))

    def move(self, dx, dy):
        dx, dy = self._clamp(dx), self._clamp(dy)
        if not dx and not dy:
            return False
        with self._lock:
            if not self._device:
                return False
            return bool(self._api.devs.WinUHidMouseReportMotion(
                self._device, dx, dy))

    def button(self, index, down):
        with self._lock:
            if not self._device:
                return False
            return bool(self._api.devs.WinUHidMouseReportButton(
                self._device, int(index), bool(down)))

    def scroll(self, notches_x, notches_y):
        with self._lock:
            if not self._device:
                return False
            ok = True
            if notches_x:
                ok = bool(self._api.devs.WinUHidMouseReportScroll(
                    self._device,
                    self._clamp(int(notches_x) * SCROLL_UNITS_PER_NOTCH),
                    True)) and ok
            if notches_y:
                ok = bool(self._api.devs.WinUHidMouseReportScroll(
                    self._device,
                    self._clamp(int(notches_y) * SCROLL_UNITS_PER_NOTCH),
                    False)) and ok
            return ok

    def close(self):
        with self._lock:
            device, self._device = self._device, None
        if device:
            try:
                self._api.devs.WinUHidMouseDestroy(device)
            except Exception as exc:
                debug(f"WinUHid mouse destroy failed: {exc}")


_lock = threading.RLock()
_output = None


def _requested_mode():
    try:
        return str(Config().mouse_output or "auto").strip().lower()
    except Exception:
        return "auto"


def _select_backend():
    mode = _requested_mode()
    if mode in ("standard", "sendinput", "win32"):
        return StandardMouse()
    if mode not in ("auto", "winuhid", "rawinput", "raw"):
        debug(f"Unknown mouse_output '{mode}', treating it as auto")
    api = _WinUHidApi()
    if api.devs is not None:
        candidate = WinUHidMouse(api)
        if candidate.available:
            return candidate
        if mode != "auto":
            warning("mouse_output asks for WinUHid but the virtual mouse "
                    "could not be created; using SendInput")
    elif mode != "auto":
        warning("mouse_output asks for WinUHid but the driver or DLLs are "
                "missing; using SendInput")
    return StandardMouse()


def get_mouse_output():
    """Return the process-wide mouse backend, creating it on first use."""
    global _output
    with _lock:
        if _output is None:
            _output = _select_backend()
            info(f"Mouse output: {_output.name}")
        return _output


def mouse_output_name():
    """Name of the active backend without forcing creation."""
    with _lock:
        return _output.name if _output is not None else "not started"


def release_all_buttons():
    """Release every mouse button before the backend is torn down.

    Exiting while the user holds the mouse button mapped to a Joy-Con would
    otherwise leave the OS with a stuck button, which the user has to clear by
    clicking. Does nothing when no backend was ever created.
    """
    with _lock:
        if _output is None:
            return
        for index in (BTN_LEFT, BTN_RIGHT, BTN_MIDDLE):
            try:
                _output.button(index, False)
            except Exception as exc:
                debug(f"Mouse button release failed: {exc}")


def release_mouse_output():
    """Tear the backend down (called on shutdown)."""
    global _output
    with _lock:
        if _output is not None:
            _output.close()
            _output = None
