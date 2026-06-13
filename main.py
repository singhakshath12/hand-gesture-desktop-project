import cv2
import mediapipe as mp
import numpy as np
import pickle
from tensorflow.keras.models import load_model
from action_engine import trigger_action
import os
import time
current_prediction = {
    "gesture": None,
    "confidence": 0
}

MODEL_PATH = "model/gesture_ann.keras"
ENCODER_PATH = "model/label_encoder.pkl"

CONF_THRESHOLD = 0.8
FRAME_CONFIRMATION = 2

last_detected_gesture = None
gesture_counter = 0

model = load_model(MODEL_PATH)

with open(ENCODER_PATH, "rb") as f:
    encoder = pickle.load(f)

model_timestamp = os.path.getmtime(MODEL_PATH)

def check_model_reload():
    global model, encoder, model_timestamp
    current_timestamp = os.path.getmtime(MODEL_PATH)

    if current_timestamp != model_timestamp:
        print("🔄 New model detected. Reloading...")
        model = load_model(MODEL_PATH)

        with open(ENCODER_PATH, "rb") as f:
            encoder = pickle.load(f)
        model_timestamp = current_timestamp
        print("Model reloaded successfully.")

mp_hands = mp.solutions.hands
mp_draw = mp.solutions.drawing_utils
hands = mp_hands.Hands(max_num_hands=1)

cap = cv2.VideoCapture(1, cv2.CAP_DSHOW)
print("loading cam")

def normalize_landmarks(lm):
    base_x = lm[0].x
    base_y = lm[0].y
    base_z = lm[0].z

    features = []
    for point in lm:
        features.extend([
            point.x - base_x,
            point.y - base_y,
            point.z - base_z])

    features = np.array(features)
    
    # Hand-scale normalization
    scale_dist = np.linalg.norm(features[27:30])
    if scale_dist > 0:
        features = features / scale_dist
        
    return features.reshape(1, -1)


while True:
    ret, frame = cap.read()
    check_model_reload()
    if not ret:
        continue

    frame = cv2.resize(frame, (320, 240))
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = hands.process(rgb)

    if results.multi_hand_landmarks:
        for hand_landmarks in results.multi_hand_landmarks:

            mp_draw.draw_landmarks(
                frame,
                hand_landmarks,
                mp_hands.HAND_CONNECTIONS
            )

            features = normalize_landmarks(hand_landmarks.landmark)

            prediction = model.predict(features, verbose=0)
            confidence = np.max(prediction)
            predicted_index = np.argmax(prediction)

            if confidence > CONF_THRESHOLD:
                gesture = encoder.inverse_transform([predicted_index])[0]
                current_prediction["gesture"] = gesture
                current_prediction["confidence"] = round(float(confidence), 3)

                if gesture == last_detected_gesture:
                    gesture_counter += 1
                else:
                    last_detected_gesture = gesture
                    gesture_counter = 1

                if gesture_counter >= FRAME_CONFIRMATION:
                    print(f"Confirmed: {gesture} ({confidence:.2f})")
                    trigger_action(gesture)
                    print (gesture)
                    gesture_counter = 0

                cv2.putText(
                    frame,
                    f"{gesture} ({confidence:.2f})",
                    (10, 40),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1,
                    (0, 255, 0),
                    2
                )
            else:
                last_detected_gesture = None
                gesture_counter = 0
                current_prediction["gesture"] = None
                current_prediction["confidence"] = 0


    cv2.imshow("Gesture Control", frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
