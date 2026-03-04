import cv2
import mediapipe as mp
import csv
import numpy as np

GESTURES = {
    ord('1'): "fist",
    ord('2'): "two_fingers",
    ord('3'): "three_fingers",
    ord('4'): "four_fingers",
    ord('5'): "palm",
    ord('6'): "thumb_up",
    ord('7'): "thumb_down",
    ord('l'): "LEFT",
    ord('r'): "RIGHT",
    ord('u'): "UP",
    ord('d'): "DOWN",
    ord('y'): "YO",
    ord ('r'): "rock",
    ord('k'): "ok",
    ord('t'): "twist"

}

mp_hands = mp.solutions.hands
mp_draw = mp.solutions.drawing_utils
hands = mp_hands.Hands(max_num_hands=1)

cap = cv2.VideoCapture(0,cv2.CAP_DSHOW)

print("Checking camera...")

if not cap.isOpened():
    print("No camera detected.")
    exit()

with open("model/desktop_gesture_data.csv", "a", newline="") as f:
    writer = csv.writer(f)

    while True:
        ret, frame = cap.read()
        if not ret:
            continue

        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = hands.process(frame_rgb)

        data = None 

        if results.multi_hand_landmarks:
            for hand_landmarks in results.multi_hand_landmarks:
                lm = hand_landmarks.landmark
                mp_draw.draw_landmarks(frame,hand_landmarks, mp_hands.HAND_CONNECTIONS)

                base_x = lm[0].x
                base_y = lm[0].y
                base_z = lm[0].z

                features = []

                for point in lm:
                    features.append(point.x - base_x)
                    features.append(point.y - base_y)
                    features.append(point.z - base_z)
                features = np.array(features)

# normalization
                max_value = np.max(np.abs(features))
                if max_value != 0:
                    features = features / max_value

                data = features.tolist()

        cv2.putText(frame,
                    "1:Fist  2:two  3:three  4:four  5:palm 6:thumb up \n" \
                    "7:thumb down l:left r:right u:up d:down \n" \
                    " k:ok t:twist y:yo r:rock(thumbin) Q:Quit ",
            
                    (10, 40),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7, (0,255,0), 2)

        cv2.imshow("Collect Data", frame)

        key = cv2.waitKey(1)

        if key in GESTURES and data is not None:
            writer.writerow(data + [GESTURES[key]])
            print(f"Saved {GESTURES[key]}")

        elif key == ord('q'):
            break

cap.release()
cv2.destroyAllWindows()
