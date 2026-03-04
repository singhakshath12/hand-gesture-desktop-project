import cv2
import mediapipe as mp
import numpy as np
import csv
import time

def collect_gesture_data(gesture_name, status_dict):

    COLLECTION_TIME = 10
    MAX_SAMPLES = 200
    sample_count = 0
    start_time = time.time()

    status_dict["status"] = "collecting"
    status_dict["progress"] = 0

    print(f"Collecting samples for: {gesture_name}")

    mp_hands = mp.solutions.hands
    mp_draw = mp.solutions.drawing_utils
    hands = mp_hands.Hands(max_num_hands=1)

    cap = cv2.VideoCapture(0, cv2.CAP_MSMF)

    with open("model/desktop_gesture_data.csv", "a", newline="") as f:
        writer = csv.writer(f)

        while (time.time() - start_time < COLLECTION_TIME) and (sample_count < MAX_SAMPLES):

            ret, frame = cap.read()
            if not ret:
                continue

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = hands.process(rgb)

            if results.multi_hand_landmarks:
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

                    writer.writerow(features.tolist() + [gesture_name])

                    sample_count += 1
                    status_dict["progress"] = int((sample_count / MAX_SAMPLES) * 100)

            cv2.putText(
                frame,
                "Show gesture for 10 seconds",
                (10, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0,255,0),
                2
            )

            cv2.putText(
                frame,
                f"Samples: {sample_count}/{MAX_SAMPLES}",
                (10, 80),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (255,255,0),
                2
            )

            cv2.imshow("Training Gesture", frame)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    status_dict["status"] = "completed"
    status_dict["progress"] = 100

    cap.release()
    cv2.destroyAllWindows()

    print("Collection complete.")