import pyautogui
import time
import subprocess

COOLDOWN = 3
last_trigger_time = 0

def trigger_action(gesture):
    global last_trigger_time

    current_time = time.time()

    if current_time - last_trigger_time < COOLDOWN:
        return

    print("gesutre shown:", gesture)

    if gesture == "fist":
        pyautogui.hotkey('alt', 'f4')

    elif gesture == "UP":
        pyautogui.keyDown('alt')
        pyautogui.press('tab')
        pyautogui.keyUp('alt')

    elif gesture == "two_fingers":
        pyautogui.keyDown('alt')
        pyautogui.press('tab', presses=2)
        pyautogui.keyUp('alt')

    elif gesture == "three_fingers":
        pyautogui.keyDown('alt')
        pyautogui.press('tab', presses=3)
        pyautogui.keyUp('alt')

    elif gesture == "four_fingers":
        pyautogui.keyDown('alt')
        pyautogui.press('tab', presses=4)
        pyautogui.keyUp('alt')

    elif gesture == "LEFT":
        pyautogui.press('printscreen')

    last_trigger_time = current_time