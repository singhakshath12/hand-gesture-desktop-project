from flask import Flask, render_template, request, jsonify, Response
import json
import subprocess
from trainer import train_model
from runtime_state import current_prediction
import threading
import cv2
import numpy as np
import pickle
import mediapipe as mp
import os
from tensorflow.keras.models import load_model
import time
from action_engine import trigger_action
import pandas as pd
import collect
from collect import collect_gesture_data

MODEL_PATH = "model/gesture_ann.keras"
ENCODER_PATH = "model/label_encoder.pkl"
ACTION_MAP_PATH = "action_map.json"
BUILTIN_PATH = "config/builtin_gestures.json"
model = load_model(MODEL_PATH)

with open(ENCODER_PATH, "rb") as f:
    encoder = pickle.load(f)

mp_hands = mp.solutions.hands
mp_draw = mp.solutions.drawing_utils
hands = mp_hands.Hands(max_num_hands=1)

CONF_THRESHOLD = 0.85
FRAME_CONFIRMATION = 5
PREDICT_EVERY = 5
ACTION_COOLDOWN = 1.0

last_gesture = None
gesture_counter = 0
last_action_time = 0
frame_count = 0

# ------------------------
# Training state
# ------------------------
training_status = {
    "status": "idle",
    "accuracy": None
}

app = Flask(__name__)
camera_running = False

collection_status = {
    "status": "idle",
    "progress": 0
}


def generate_frames():
    global current_prediction

    cap = cv2.VideoCapture(0)

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 480)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 360)

    last_predict_time = 0
    PREDICT_INTERVAL = 0.2

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = hands.process(rgb)

        hand_detected = False

        if results.multi_hand_landmarks:
            hand_detected = True

            for hand_landmarks in results.multi_hand_landmarks:

                mp_draw.draw_landmarks(
                    frame,
                    hand_landmarks,
                    mp_hands.HAND_CONNECTIONS
                )

                lm = hand_landmarks.landmark
                base_x = lm[0].x
                base_y = lm[0].y
                base_z = lm[0].z

                features = []
                for point in lm:
                    features.extend([
                        point.x - base_x,
                        point.y - base_y,
                        point.z - base_z
                    ])

                features = np.array(features)

                max_value = np.max(np.abs(features))
                if max_value != 0:
                    features = features / max_value

                if time.time() - last_predict_time > PREDICT_INTERVAL:

                    prediction = model.predict(
                        np.array([features]),
                        verbose=0
                    )

                    predicted_index = np.argmax(prediction)
                    confidence = prediction[0][predicted_index]

                    if confidence > CONF_THRESHOLD:
                        gesture = encoder.inverse_transform([predicted_index])[0]

                        current_prediction["gesture"] = gesture
                        current_prediction["confidence"] = round(float(confidence), 3)

                        trigger_action(gesture)
                    else:
                        # Below confidence → clear
                        current_prediction["gesture"] = None
                        current_prediction["confidence"] = None

                    last_predict_time = time.time()

        if not hand_detected:
            current_prediction["gesture"] = None
            current_prediction["confidence"] = None

        if current_prediction["gesture"]:
            cv2.putText(
                frame,
                f'{current_prediction["gesture"]} ({current_prediction["confidence"]})',
                (10, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (0,255,0),
                2
            )

        ret, buffer = cv2.imencode(".jpg", frame)
        frame = buffer.tobytes()

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' +
               frame + b'\r\n')

def load_action_map():
    with open(ACTION_MAP_PATH) as f:
        return json.load(f)


def save_action_map(data):
    with open(ACTION_MAP_PATH, "w") as f:
        json.dump(data, f, indent=4)


def load_builtin():
    with open(BUILTIN_PATH) as f:
        return json.load(f)

@app.route("/")
def dashboard():
    action_map = load_action_map()
    builtin = load_builtin()

    data = pd.read_csv("model/desktop_gesture_data.csv", header=None)
    all_gestures = sorted(set(data.iloc[:, -1]))

    return render_template(
        "index.html",
        action_map=action_map,
        builtin=builtin,
        all_gestures=all_gestures
    )


@app.route("/start_camera", methods=["POST"])
def start_camera():
    global camera_running
    camera_running = True
    return jsonify({"status": "started"})


@app.route("/stop_camera", methods=["POST"])
def stop_camera():
    global camera_running
    camera_running = False
    return jsonify({"status": "stopped"})


@app.route("/video_feed")
def video_feed():
    return Response(
        generate_frames(),
        mimetype='multipart/x-mixed-replace; boundary=frame'
    )


@app.route("/update", methods=["POST"])
def update_action():
    data = request.json
    gesture = data["gesture"]
    action = data["action"]

    action_map = load_action_map()
    action_map[gesture] = action
    save_action_map(action_map)

    return jsonify({"status": "updated"})

@app.route("/collection_status")
def get_collection_status():
    return jsonify(collection_status)


@app.route("/delete", methods=["POST"])
def delete_gesture():
    data = request.json
    gesture = data["gesture"]

    action_map = load_action_map()

    if gesture in action_map:
        del action_map[gesture]

    save_action_map(action_map)

    return jsonify({"status": "deleted"})


@app.route("/collect", methods=["POST"])
def collect_gesture():
    gesture = request.json["gesture"]
    subprocess.Popen(["python", "collect.py", gesture])
    return jsonify({"status": "collection_started"})

@app.route("/add_new_gesture", methods=["POST"])
def add_new_gesture():

    data = request.json
    gesture_name = data["gesture"]
    action = data["action"]

    action_map = load_action_map()
    action_map[gesture_name] = action
    save_action_map(action_map)
    collect.collect_gesture_data(gesture_name)

    train_model(training_status)
    return jsonify({"message": "Gesture trained successfully!"})


@app.route("/retrain", methods=["POST"])
def retrain():
    if training_status["status"] == "training":
        return jsonify({"status": "already_running"})

    def background_train():
        train_model(training_status)

    thread = threading.Thread(target=background_train)
    thread.start()

    return jsonify({"status": "started"})


@app.route("/training_status")
def get_training_status():
    return jsonify(training_status)


@app.route("/live_prediction")
def live_prediction():
    return jsonify(current_prediction)


# =====================================================
if __name__ == "__main__":
    app.run(debug=True)