import os
import json
import time
import threading
import csv
import numpy as np
from flask import Flask, request, jsonify, Response, render_template
from flask_socketio import SocketIO
import pandas as pd

import runtime_state as rs
import action_engine
import trainer
from camera_engine import CameraEngine

app = Flask(__name__, static_folder='static', static_url_path='/static')
app.config['SECRET_KEY'] = 'gesture-control-secret'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Constants
ACTION_MAP_PATH = "action_map.json"
BUILTIN_PATH = "config/builtin_gestures.json"
CUSTOM_DATA_PATH = "model/custom_gesture_data.csv"
SETTINGS_PATH = "config/settings.json"
DISPLAY_NAMES_PATH = "config/display_names.json"

# ── Initialize Camera Engine ─────────────────────────────────────────────────
engine = CameraEngine(socketio)

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
    # Invalidate engine's cache so it picks up the new names
    engine.invalidate_caches()

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/system/status')
def system_status():
    return jsonify({
        "camera_running": rs.camera_running,
        "system_active": rs.system_active,
        "model_loaded": engine.model_loaded
    })

@app.route('/api/camera/start', methods=['POST'])
def start_camera():
    rs.camera_running = True
    rs.system_active = True
    # Start engine if not already running
    engine.start()
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
    # Start engine on first feed request if not already running
    if not engine.running:
        engine.start()
    return Response(engine.generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

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
    
    # Invalidate caches after writing config
    engine.invalidate_caches()
        
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
    
    # Invalidate caches after writing config
    engine.invalidate_caches()
        
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
    
    # Invalidate caches after writing config
    engine.invalidate_caches()
                
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
    
    # Start engine if not already running (needed for data collection)
    if not engine.running:
        engine.start()
    
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
            print("Training completed. Hot-reloading TFLite model...")
            engine.reload_model()
            
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
    engine.reload_model()
    return jsonify({"success": engine.model_loaded})

if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)