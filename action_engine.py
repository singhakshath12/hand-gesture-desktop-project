import json
import pyautogui
import subprocess
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

    if action["type"] == "hotkey":
        pyautogui.hotkey(*action["keys"])

    elif action["type"] == "press":
        pyautogui.press(action["key"])

    elif action["type"] == "alt_tab":
        pyautogui.keyDown("alt")
        pyautogui.press("tab", presses=action["count"])
        pyautogui.keyUp("alt")

    elif action["type"] == "open_app":
        subprocess.Popen(action["path"])

    last_trigger_time = current_time
