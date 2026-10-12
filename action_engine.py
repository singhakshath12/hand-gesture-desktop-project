import json
import pyautogui
import subprocess
import os
import time
import math
import collections

try:
    import win32api
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False

pyautogui.PAUSE = 0
pyautogui.FAILSAFE = False

last_action_time = 0

class OneEuroFilter:
    def __init__(self, t0, x0, dx0=0.0, min_cutoff=1.0, beta=0.007, d_cutoff=1.0):
        self.min_cutoff = min_cutoff
        self.beta = beta
        self.d_cutoff = d_cutoff
        self.x_prev = x0
        self.dx_prev = dx0
        self.t_prev = t0

    def smoothing_factor(self, t_e, cutoff):
        r = 2 * math.pi * cutoff * t_e
        return r / (r + 1)

    def __call__(self, t, x):
        t_e = t - self.t_prev
        if t_e <= 0:
            return x
        
        dx = (x - self.x_prev) / t_e
        alpha_d = self.smoothing_factor(t_e, self.d_cutoff)
        dx_hat = alpha_d * dx + (1 - alpha_d) * self.dx_prev
        
        cutoff = self.min_cutoff + self.beta * abs(dx_hat)
        alpha = self.smoothing_factor(t_e, cutoff)
        x_hat = alpha * x + (1 - alpha) * self.x_prev
        
        self.x_prev = x_hat
        self.dx_prev = dx_hat
        self.t_prev = t
        return x_hat

class CursorTracker:
    def __init__(self):
        self.filter_x = None
        self.filter_y = None
        self.state = "TRACKING"
        self.release_start_time = 0
        self.screen_w, self.screen_h = pyautogui.size()
        
    def update(self, landmark_9, should_track):
        t = time.time()
        
        # Mirror X coordinate
        raw_x = 1.0 - landmark_9.x
        raw_y = landmark_9.y
        
        # Edge Acceleration Zone (Comfort Zone: 0.15 to 0.85)
        def apply_edge_accel(norm_val):
            if norm_val < 0.15:
                overshoot = 0.15 - norm_val
                return 0.0 - (overshoot ** 1.5) * 2.0
            elif norm_val > 0.85:
                overshoot = norm_val - 0.85
                return 1.0 + (overshoot ** 1.5) * 2.0
            else:
                return (norm_val - 0.15) / 0.70

        mapped_x = max(0, min(self.screen_w - 1, apply_edge_accel(raw_x) * self.screen_w))
        mapped_y = max(0, min(self.screen_h - 1, apply_edge_accel(raw_y) * self.screen_h))
        
        if self.filter_x is None:
            self.filter_x = OneEuroFilter(t, mapped_x, min_cutoff=1.0, beta=0.007)
            self.filter_y = OneEuroFilter(t, mapped_y, min_cutoff=1.0, beta=0.007)
            return

        smooth_x = self.filter_x(t, mapped_x)
        smooth_y = self.filter_y(t, mapped_y)
        
        # State Machine: TRACKING -> TRANSITIONING -> FROZEN -> RELEASING
        if not should_track:
            if self.state == "TRACKING":
                self.state = "TRANSITIONING"
            elif self.state == "TRANSITIONING":
                self.state = "FROZEN"
        else:
            if self.state in ["FROZEN", "TRANSITIONING"]:
                self.state = "RELEASING"
                self.release_start_time = t
            elif self.state == "RELEASING":
                if t - self.release_start_time > 0.0:  # 0ms blend-back for instant resume
                    self.state = "TRACKING"
            else:
                self.state = "TRACKING"
                
        if self.state == "TRACKING":
            if HAS_WIN32:
                win32api.SetCursorPos((int(smooth_x), int(smooth_y)))
            else:
                pyautogui.moveTo(smooth_x, smooth_y)

cursor_tracker = CursorTracker()

def update_cursor(hand_landmarks, is_gesture_active):
    if len(hand_landmarks.landmark) > 9:
        cursor_tracker.update(hand_landmarks.landmark[9], is_gesture_active)

_action_map_cache = None
_action_map_mtime = 0

def load_action_map():
    global _action_map_cache, _action_map_mtime
    try:
        path = "action_map.json"
        mtime = os.path.getmtime(path)
        if _action_map_cache is None or mtime != _action_map_mtime:
            with open(path, "r") as f:
                _action_map_cache = json.load(f)
            _action_map_mtime = mtime
    except (FileNotFoundError, OSError):
        if _action_map_cache is None:
            _action_map_cache = {}
    return _action_map_cache

def invalidate_cache():
    global _action_map_cache, _action_map_mtime
    _action_map_cache = None
    _action_map_mtime = 0

def trigger_action(gesture, cooldown):
    global last_action_time
    
    current_time = time.time()
    if current_time - last_action_time < cooldown:
        return None
        
    action_map = load_action_map()
    
    if gesture not in action_map:
        return None
        
    action_data = action_map[gesture]
    
    if isinstance(action_data, dict):
        action_type = action_data.get("type")
        params = action_data.get("params", {})
    else:
        action_type = action_data
        params = {}
    
    # Check for unassigned/none action
    if action_type.lower() in ["none", "unassigned"]:
        last_action_time = current_time
        return {"action": "none", "description": "No Action Assigned"}

    executed = False
    action_desc = ""

    try:
        if action_type == "hotkey":
            keys = params.get("keys", action_data.get("keys", []))
            if isinstance(keys, str):
                keys = [k.strip() for k in keys.split('+')]
            pyautogui.hotkey(*keys)
            action_desc = f"Hotkey: {'+'.join(keys)}"
            executed = True
            
        elif action_type == "press":
            key = params.get("key", action_data.get("key", ""))
            pyautogui.press(key)
            action_desc = f"Press: {key}"
            executed = True
            
        elif action_type == "alt_tab":
            count = params.get("count", action_data.get("count", 1))
            try:
                count = int(count)
            except:
                count = 1
            pyautogui.keyDown('alt')
            for _ in range(count):
                pyautogui.press('tab')
                time.sleep(0.02)
            pyautogui.keyUp('alt')
            action_desc = f"Alt+Tab ({count}x)"
            executed = True
            
        elif action_type == "volume":
            direction = params.get("direction", action_data.get("direction", "up"))
            if direction == "up":
                pyautogui.press('volumeup')
                action_desc = "Volume Up"
            else:
                pyautogui.press('volumedown')
                action_desc = "Volume Down"
            executed = True
            
        elif action_type == "type_text":
            text = params.get("text", action_data.get("text", ""))
            if text:
                pyautogui.write(text, interval=0.03)
                action_desc = f"Typed: {text[:30]}{'...' if len(text) > 30 else ''}"
                executed = True

        elif action_type == "open_app":
            app_path = params.get("path", action_data.get("path", ""))
            if app_path:
                try:
                    subprocess.Popen(app_path, shell=True)
                    action_desc = f"Opened: {os.path.basename(app_path)}"
                    executed = True
                except Exception as e:
                    print(f"Failed to open app: {e}")
                
        elif action_type == "left_click":
            pyautogui.click(button='left')
            return {"status": "success", "description": "Left Click"}

        elif action_type == "system_command":
            cmd = params.get("command", action_data.get("command", ""))
            if cmd:
                os.system(cmd)
                action_desc = f"System Cmd: {cmd}"
                executed = True
                
        elif isinstance(action_data, str) and action_data.startswith("hotkey:"):
            keys_str = action_data.split(":", 1)[1].strip()
            keys = [k.strip() for k in keys_str.split('+')]
            pyautogui.hotkey(*keys)
            action_desc = f"Hotkey: {keys_str}"
            executed = True
        elif isinstance(action_data, str) and action_data.startswith("press:"):
            key = action_data.split(":", 1)[1].strip()
            pyautogui.press(key)
            action_desc = f"Press: {key}"
            executed = True
        elif isinstance(action_data, str) and action_data.startswith("alt_tab:"):
            count = int(action_data.split(":", 1)[1].strip())
            pyautogui.keyDown('alt')
            for _ in range(count):
                pyautogui.press('tab')
                time.sleep(0.02)
            pyautogui.keyUp('alt')
            action_desc = f"Alt+Tab ({count}x)"
            executed = True
            
    except Exception as e:
        print(f"Error executing action for {gesture}: {e}")
        return None
        
    if executed:
        last_action_time = current_time
        return {"action": action_type, "description": action_desc}
        
    return None