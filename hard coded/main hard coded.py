import cv2
import mediapipe as mp
import numpy as np
import pickle
import time
from tensorflow.keras.models import load_model
from action_mapping import trigger_action

CONF_THRESHOLD = 0.80
COOLDOWN = 1.5

model = load_model("model/gesture_ann.keras")

with open("model/label_encoder.pkl", "rb") as f:
    encoder = pickle.load(f)

mp_hands = mp.solutions.hands
mp_draw = mp.solutions.drawing_utils
hands = mp_hands.Hands(max_num_hands=1)

cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)

print("Checking camera...")

last_trigger_time = 0

def normalize_landmarks(lm):
    base_x = lm[0].x
    base_y = lm[0].y
    base_z = lm[0].z

    features = []

    for point in lm:
        features.append(point.x - base_x)
        features.append(point.y - base_y)
        features.append(point.z - base_z)

    features = np.array(features)

    # Hand-scale normalization
    scale_dist = np.linalg.norm(features[27:30])
    if scale_dist > 0:
        features = features / scale_dist

    return features.reshape(1, -1)

while True:
    ret, frame = cap.read()
    if not ret:
        continue

    frame = cv2.resize(frame, (320, 240))
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = hands.process(rgb)

    if results.multi_hand_landmarks:
        for hand_landmarks in results.multi_hand_landmarks:

            mp_draw.draw_landmarks(frame,hand_landmarks, mp_hands.HAND_CONNECTIONS)

            features = normalize_landmarks(hand_landmarks.landmark)

            prediction = model.predict(features, verbose=0)
            confidence = np.max(prediction)
            predicted_index = np.argmax(prediction)

            if confidence > CONF_THRESHOLD:
                gesture = encoder.inverse_transform([predicted_index])[0]
               #trigger_action(gesture)

                cv2.putText(frame,
                            f"{gesture} ({confidence:.2f})",    
                            (10, 40),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            1,
                            (0,255,0),
                            2)


    cv2.imshow("Gesture Runtime", frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
