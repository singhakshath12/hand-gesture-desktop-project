import os
import json
import time
import pickle
import threading
import csv
import cv2
import numpy as np
import tensorflow as tf
from flask import Flask, request, jsonify, Response, render_template
from flask_socketio import SocketIO
import mediapipe as mp
import pandas as pd

import runtime_state as rs
import action_engine
import trainer

app = Flask(__name__, static_folder='static', static_url_path='/static')
app.config['SECRET_KEY'] = 'gesture-control-secret'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Constants & Initialization
MODEL_PATH = "model/gesture_ann.keras"
ENCODER_PATH = "model/label_encoder.pkl"
ACTION_MAP_PATH = "action_map.json"
BUILTIN_PATH = "config/builtin_gestures.json"
CUSTOM_DATA_PATH = "model/custom_gesture_data.csv"
SETTINGS_PATH = "config/settings.json"
DISPLAY_NAMES_PATH = "config/display_names.json"

# Mediapipe Hands
mp_hands = mp.solutions.hands
hands = mp_hands.Hands(static_image_mode=False, max_num_hands=1, min_detection_confidence=0.7)
mp_drawing = mp.solutions.drawing_utils

model = None
encoder = None

def load_ml_assets():
    global model, encoder
    try:
        if os.path.exists(MODEL_PATH):
            model = tf.keras.models.load_model(MODEL_PATH)
        if os.path.exists(ENCODER_PATH):
            with open(ENCODER_PATH, "rb") as f:
                encoder = pickle.load(f)
        print("ML Assets loaded successfully.")
    except Exception as e:
        print(f"Error loading ML assets: {e}")

load_ml_assets()

def load_settings():
    if os.path.exists(SETTINGS_PATH):
        try:
            with open(SETTINGS_PATH, "r") as f:
                rs.settings.update(json.load(f))
        except:
            pass

load_settings()

def save_settings():
    os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
    with open(SETTINGS_PATH, "w") as f:
        json.dump(rs.settings, f, indent=4)

def load_builtin_gestures():
    try:
        with open(BUILTIN_PATH, "r") as f:
            return json.load(f)
    except:
        return []

def load_display_names():
    try:
        if os.path.exists(DISPLAY_NAMES_PATH):
            with open(DISPLAY_NAMES_PATH, "r") as f:
                return json.load(f)
    except:
        pass
    return {}

def save_display_names(names):
    os.makedirs(os.path.dirname(DISPLAY_NAMES_PATH), exist_ok=True)
    with open(DISPLAY_NAMES_PATH, "w") as f:
        json.dump(names, f, indent=4)

def normalize_landmarks(landmarks):
    base_x, base_y, base_z = landmarks.landmark[0].x, landmarks.landmark[0].y, landmarks.landmark[0].z
    features = []
    for lm in landmarks.landmark:
        features.extend([lm.x - base_x, lm.y - base_y, lm.z - base_z])
    features = np.array(features)
    
    # Hand-scale normalization: distance from wrist (0) to middle finger MCP (9)
    # The middle MCP is at index 9 * 3 = 27 in the flattened features array
    scale_dist = np.linalg.norm(features[27:30])
    
    if scale_dist > 0:
        features = features / scale_dist
    return features.reshape(1, -1)

def compute_finger_states(landmarks):
    lm = landmarks.landmark
    i_ty, i_py, i_my = lm[8].y, lm[6].y, lm[5].y
    m_ty, m_py, m_my = lm[12].y, lm[10].y, lm[9].y
    r_ty, r_py, r_my = lm[16].y, lm[14].y, lm[13].y
    p_ty, p_py, p_my = lm[20].y, lm[18].y, lm[17].y

    th_tx = lm[4].x; th_ix = lm[3].x; w_x = lm[0].x
    thumb_dist_tip = abs(th_tx - w_x)
    thumb_dist_ip  = abs(th_ix - w_x)

    return {
        "thumb":  thumb_dist_tip > thumb_dist_ip * 1.1,
        "index":  i_ty < i_py or i_ty < i_my,
        "middle": m_ty < m_py or m_ty < m_my,
        "ring":   r_ty < r_py or r_ty < r_my,
        "pinky":  p_ty < p_py or p_ty < p_my,
    }

# Camera Generator
def generate_frames():
    cap = None
    frame_count = 0
    start_time = time.time()
    last_predict_time = 0
    last_collect_time = 0
    was_pinching = False
    import collections
    class GestureSmoother:
        def __init__(self, window_size=5):
            self.window = collections.deque(maxlen=window_size)
            
        def add_and_get_majority(self, gesture):
            if not gesture:
                self.window.append("None")
            else:
                self.window.append(gesture)
                
            if len(self.window) < self.window.maxlen:
                return None
                
            counts = collections.Counter(self.window)
            most_common, count = counts.most_common(1)[0]
            if count / len(self.window) >= 0.55 and most_common != "None":
                return most_common
            return None

    gesture_smoother = GestureSmoother(5)
    is_gesture_active = False
    
    try:
        cap = cv2.VideoCapture(rs.settings["camera_index"])
        
        while True:
            success, frame = cap.read()
            if not success:
                time.sleep(0.1)
                continue
                
            frame = cv2.resize(frame, (640, 480))
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # FPS tracking
            frame_count += 1
            if time.time() - start_time >= 1.0:
                fps = frame_count
                socketio.emit('fps_update', {'fps': fps})
                frame_count = 0
                start_time = time.time()

            # Process MediaPipe if engine is running OR collecting data
            if rs.camera_running or rs.collection_target is not None:
                results = hands.process(rgb_frame)
                if results.multi_hand_landmarks:
                    for hand_landmarks in results.multi_hand_landmarks:
                        mp_drawing.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)
                        
                        # Data Collection Mode
                        if rs.collection_target is not None:
                            current_time = time.time()
                            if current_time - last_collect_time > 0.03: # Capture roughly ~30 fps for diversity
                                last_collect_time = current_time
                                features = normalize_landmarks(hand_landmarks)
                                
                                rs.collection_buffer.append(features[0].tolist() + [rs.collection_target])
                                rs.collection_status["samples"] = len(rs.collection_buffer)
                                
                                MAX_SAMPLES = 400
                                progress = int((rs.collection_status["samples"] / MAX_SAMPLES) * 100)
                                rs.collection_status["progress"] = progress
                                
                                if rs.collection_status["samples"] % 10 == 0:
                                    socketio.emit('collection_progress', {
                                        'status': 'collecting', 
                                        'progress': progress, 
                                        'samples': rs.collection_status["samples"], 
                                        'total': MAX_SAMPLES
                                    })
                                    
                                if rs.collection_status["samples"] >= MAX_SAMPLES:
                                    # Save to CSV
                                    with open(CUSTOM_DATA_PATH, "a", newline="") as f:
                                        writer = csv.writer(f)
                                        writer.writerows(rs.collection_buffer)
                                        
                                    rs.collection_target = None
                                    rs.collection_buffer = []
                                    rs.collection_status["status"] = "completed"
                                    socketio.emit('collection_progress', {
                                        'status': 'completed', 
                                        'progress': 100, 
                                        'samples': MAX_SAMPLES, 
                                        'total': MAX_SAMPLES
                                    })
                                
                        # Normal Prediction Engine Mode
                        elif rs.camera_running:
                            current_time = time.time()
                            
                            # Instant Pinch-to-Click Detection (Bypasses ML 10FPS + Smoother)
                            th_tip = hand_landmarks.landmark[4]
                            idx_tip = hand_landmarks.landmark[8]
                            pinch_dist = ((th_tip.x - idx_tip.x)**2 + (th_tip.y - idx_tip.y)**2)**0.5
                            is_pinching = pinch_dist < 0.05
                            
                            if is_pinching and not was_pinching:
                                action_result = action_engine.trigger_action("ok", 0) # 0 cooldown for instant trigger
                                if action_result:
                                    log_entry = {
                                        "gesture": "ok (Instant)", 
                                        "action": action_result["description"], 
                                        "timestamp": time.time()
                                    }
                                    rs.action_log.insert(0, log_entry)
                                    if len(rs.action_log) > rs.MAX_LOG_SIZE:
                                        rs.action_log.pop()
                                    socketio.emit('action_triggered', log_entry)
                            was_pinching = is_pinching
                            
                            # Full FPS Cursor Tracking (Instantly freeze if pinching)
                            effective_track = is_gesture_active and not is_pinching
                            action_engine.update_cursor(hand_landmarks, effective_track)
                            
                            if current_time - last_predict_time > 0.1: # 10FPS prediction
                                last_predict_time = current_time
                                features = normalize_landmarks(hand_landmarks)
                                
                                if model and encoder:
                                    prediction = model.predict(features, verbose=0)
                                    class_idx = np.argmax(prediction)
                                    confidence = float(np.max(prediction))
                                    gesture = encoder.classes_[class_idx]
                                    
                                    # Dual Shape-Gating
                                    states = compute_finger_states(hand_landmarks)
                                    if gesture == "palm" and not (states["index"] and states["middle"] and states["ring"] and states["pinky"]):
                                        confidence = 0.0
                                    elif gesture == "fist" and (states["index"] or states["middle"] or states["ring"] or states["pinky"]):
                                        confidence = 0.0
                                    elif gesture == "two_fingers" and not (states["index"] and states["middle"]):
                                        confidence = 0.0
                                    
                                    display_names = load_display_names()
                                    display_gesture = display_names.get(gesture, gesture)
                                    
                                    rs.current_prediction = {"gesture": display_gesture, "confidence": confidence}
                                    socketio.emit('prediction', rs.current_prediction)
                                    
                                    if confidence >= rs.settings["confidence_threshold"]:
                                        smoothed_gesture = gesture_smoother.add_and_get_majority(gesture)
                                        if smoothed_gesture:
                                            action_map = action_engine.load_action_map()
                                            action_info = action_map.get(smoothed_gesture, {})
                                            
                                            should_track = (action_info.get("type") == "tracking")
                                            is_gesture_active = should_track
                                            
                                            if not should_track:
                                                action_result = action_engine.trigger_action(smoothed_gesture, rs.settings["action_cooldown"])
                                                if action_result:
                                                    log_entry = {
                                                        "gesture": display_gesture, 
                                                        "action": action_result["description"], 
                                                        "timestamp": time.time()
                                                    }
                                                    rs.action_log.insert(0, log_entry)
                                                    if len(rs.action_log) > rs.MAX_LOG_SIZE:
                                                        rs.action_log.pop()
                                                    socketio.emit('action_triggered', log_entry)
                                        else:
                                            is_gesture_active = False
                                    else:
                                        gesture_smoother.add_and_get_majority(None)
                                        is_gesture_active = False
                else:
                    if rs.collection_target is None and rs.camera_running:
                        rs.current_prediction = {"gesture": None, "confidence": 0}
                        socketio.emit('prediction', rs.current_prediction)
                        gesture_smoother.window.clear()
                        is_gesture_active = False
            
            ret, buffer = cv2.imencode('.jpg', frame)
            frame_bytes = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
                   
    except GeneratorExit:
        print("Client disconnected stream")
    finally:
        if cap is not None:
            cap.release()

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/system/status')
def system_status():
    return jsonify({
        "camera_running": rs.camera_running,
        "system_active": rs.system_active,
        "model_loaded": model is not None
    })

@app.route('/api/camera/start', methods=['POST'])
def start_camera():
    rs.camera_running = True
    rs.system_active = True
    socketio.emit('system_status', {'camera_running': True, 'system_active': True})
    return jsonify({"success": True})

@app.route('/api/camera/stop', methods=['POST'])
def stop_camera():
    rs.camera_running = False
    rs.system_active = False
    socketio.emit('system_status', {'camera_running': False, 'system_active': False})
    return jsonify({"success": True})

@app.route('/api/camera/feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/api/gestures', methods=['GET'])
def get_gestures():
    builtin = load_builtin_gestures()
    action_map = action_engine.load_action_map()
    
    # Custom gestures: anything in action_map that isn't built-in
    custom = [g for g in action_map.keys() if g not in builtin]
    
    # Check what we have data for
    custom_with_data = []
    if os.path.exists(CUSTOM_DATA_PATH):
        try:
            df = pd.read_csv(CUSTOM_DATA_PATH, header=None)
            if not df.empty:
                custom_with_data = df.iloc[:, -1].unique().tolist()
        except pd.errors.EmptyDataError:
            pass
            
    # Add gestures from data that might not be mapped yet
    for c in custom_with_data:
        if c not in custom and c not in builtin:
            custom.append(c)
            
    return jsonify({
        "builtin": builtin,
        "custom": custom,
        "action_map": action_map,
        "display_names": load_display_names()
    })

@app.route('/api/gestures', methods=['POST'])
def add_gesture():
    data = request.json
    name = data.get('name')
    display_name = data.get('display_name')
    action = data.get('action')
    
    if not name:
        return jsonify({"success": False, "error": "Name required"}), 400
        
    action_map = action_engine.load_action_map()
    action_map[name] = action
    
    with open(ACTION_MAP_PATH, "w") as f:
        json.dump(action_map, f, indent=4)
        
    names = load_display_names()
    names[name] = display_name or name
    save_display_names(names)
        
    return jsonify({"success": True})

@app.route('/api/gestures/<name>', methods=['PUT'])
def update_gesture(name):
    data = request.json
    action = data.get('action')
    display_name = data.get('display_name')
    
    action_map = action_engine.load_action_map()
    action_map[name] = action
    
    with open(ACTION_MAP_PATH, "w") as f:
        json.dump(action_map, f, indent=4)
        
    names = load_display_names()
    names[name] = display_name or name
    save_display_names(names)
        
    return jsonify({"success": True})

@app.route('/api/gestures/<name>', methods=['DELETE'])
def delete_gesture(name):
    builtin = load_builtin_gestures()
    if name in builtin:
        return jsonify({"success": False, "error": "Cannot delete built-in gesture"}), 400
        
    # Remove from action map
    action_map = action_engine.load_action_map()
    if name in action_map:
        del action_map[name]
        with open(ACTION_MAP_PATH, "w") as f:
            json.dump(action_map, f, indent=4)
            
    # Remove from custom data
    if os.path.exists(CUSTOM_DATA_PATH):
        try:
            df = pd.read_csv(CUSTOM_DATA_PATH, header=None)
            if not df.empty:
                df = df[df.iloc[:, -1] != name]
                if df.empty:
                    os.remove(CUSTOM_DATA_PATH)
                else:
                    df.to_csv(CUSTOM_DATA_PATH, index=False, header=False)
        except pd.errors.EmptyDataError:
            pass
                
    return jsonify({"success": True})

@app.route('/api/collect/start', methods=['POST'])
def start_collection():
    data = request.json
    gesture = data.get('gesture_name')
    if not gesture:
        return jsonify({"success": False, "error": "Gesture required"}), 400
        
    rs.collection_target = gesture
    rs.collection_buffer = []
    rs.collection_status = {"status": "collecting", "progress": 0, "samples": 0}
    return jsonify({"success": True})

@app.route('/api/collect/cancel', methods=['POST'])
def cancel_collection():
    rs.collection_target = None
    rs.collection_buffer = []
    rs.collection_status = {"status": "idle", "progress": 0, "samples": 0}
    socketio.emit('collection_progress', rs.collection_status)
    return jsonify({"success": True})

@app.route('/api/collect/status')
def get_collection_status():
    return jsonify(rs.collection_status)

@app.route('/api/train/start', methods=['POST'])
def start_training():
    def run_training_and_reload():
        trainer.train_model(rs.training_status, socketio)
        if rs.training_status.get("status") == "completed":
            print("Training completed. Hot-reloading model...")
            load_ml_assets()
            
    threading.Thread(target=run_training_and_reload).start()
    return jsonify({"success": True})

@app.route('/api/train/status')
def get_training_status():
    return jsonify(rs.training_status)

@app.route('/api/action-log')
def get_action_log():
    return jsonify(rs.action_log)

@app.route('/api/settings', methods=['GET'])
def get_settings():
    return jsonify(rs.settings)

@app.route('/api/settings', methods=['PUT'])
def update_settings():
    data = request.json
    rs.settings.update(data)
    save_settings()
    return jsonify({"success": True})

@app.route('/api/reload_model', methods=['POST'])
def reload_model_api():
    load_ml_assets()
    return jsonify({"success": model is not None})

if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)