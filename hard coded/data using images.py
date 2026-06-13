import cv2
import mediapipe as mp
import os
import csv
import numpy as np

mp_hands = mp.solutions.hands
hands = mp_hands.Hands(static_image_mode=True, max_num_hands=1)

dataset_path = "dataset"

with open("model/desktop_gesture_data.csv", "w", newline="") as f:

    writer = csv.writer(f)

    for label in os.listdir(dataset_path):
        folder = os.path.join(dataset_path, label)

        if not os.path.isdir(folder):
            continue

        for img_name in os.listdir(folder):
            img_path = os.path.join(folder, img_name)

            image = cv2.imread(img_path)
            if image is None:
                continue

            image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            results = hands.process(image_rgb)

            if results.multi_hand_landmarks:
                lm = results.multi_hand_landmarks[0].landmark

                base_x = lm[0].x
                base_y = lm[0].y
                base_z = lm[0].z

                data = []

                for point in lm:
                    data.append(point.x - base_x)
                    data.append(point.y - base_y)
                    data.append(point.z - base_z)

                data = np.array(data)

                # Hand-scale normalization
                scale_dist = np.linalg.norm(data[27:30])
                if scale_dist > 0:
                    data = data / scale_dist

                writer.writerow(list(data) + [label])

print("Dataset extraction complete.")
