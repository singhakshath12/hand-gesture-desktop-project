import json
import pyautogui
import subprocess
import os
import time

COOLDOWN = 3
last_trigger_time = 0

with open("action_map.json") as f:
    action_map = json.load(f)


def trigger_action(gesture):
    global last_trigger_time

    current_time = time.time()
    if current_time - last_trigger_time < COOLDOWN:
        return

    if gesture not in action_map:
        return

    action = action_map[gesture]
    action_type = action["type"]

    # 🔹 Keyboard Hotkey (ctrl+alt+del etc.)
    if action_type == "hotkey":
        pyautogui.hotkey(*action["keys"])

    # 🔹 Single Key Press
    elif action_type == "press":
        pyautogui.press(action["key"])

    # 🔹 Alt + Tab multiple times
    elif action_type == "alt_tab":
        pyautogui.keyDown("alt")
        pyautogui.press("tab", presses=action["count"])
        pyautogui.keyUp("alt")

    # 🔹 Volume Control
    elif action_type == "volume":
        if action["direction"] == "up":
            pyautogui.press("volumeup")
        elif action["direction"] == "down":
            pyautogui.press("volumedown")

    # 🔹 Brightness Control
    elif action_type == "brightness":
        if action["direction"] == "up":
            pyautogui.press("brightnessup")
        elif action["direction"] == "down":
            pyautogui.press("brightnessdown")

    # 🔹 Open Application
    elif action_type == "open_app":
        subprocess.Popen(action["path"])

    # 🔹 System Command
    elif action_type == "system_command":
        os.system(action["command"])

    last_trigger_time = current_time