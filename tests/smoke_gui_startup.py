"""Headless startup smoke test for the GUI.

Runs gui.py with the offscreen Qt platform, waits a few seconds, then checks
whether the process is still alive and whether any traceback was printed.
The process is terminated afterwards; BLE connections are never opened.
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = os.path.join(ROOT, "venv", "Scripts", "python.exe")
if not os.path.exists(PY):
    PY = sys.executable

env = os.environ.copy()
env["QT_QPA_PLATFORM"] = "offscreen"
env["PYTHONUNBUFFERED"] = "1"

proc = subprocess.Popen(
    [PY, "gui.py"],
    cwd=ROOT,
    env=env,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
    errors="replace",
)

try:
    out, _ = proc.communicate(timeout=8)
    alive = False
except subprocess.TimeoutExpired:
    alive = True
    proc.terminate()
    try:
        out, _ = proc.communicate(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        out, _ = proc.communicate()

print("ALIVE_AFTER_8S:", alive)
print("EXIT_CODE:", proc.returncode)
print("-" * 60)
print((out or "").strip()[-4000:])
print("-" * 60)

bad = [ln for ln in (out or "").splitlines()
       if "Traceback" in ln or "Error" in ln or "CRITICAL" in ln]
if alive and not bad:
    print("RESULT: STARTUP_OK")
elif alive:
    print("RESULT: STARTUP_SUSPECT (alive but logged errors)")
else:
    print("RESULT: STARTUP_FAILED")
