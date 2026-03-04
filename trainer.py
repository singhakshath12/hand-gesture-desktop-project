import pandas as pd
import numpy as np
import pickle
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense, Dropout
from tensorflow.keras.utils import to_categorical
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from tensorflow.keras.callbacks import EarlyStopping

DATA_PATH = "model/desktop_gesture_data.csv"
MODEL_PATH = "model/gesture_ann.keras"
ENCODER_PATH = "model/label_encoder.pkl"

def train_model(status_dict):

    status_dict["status"] = "loading_data"

    data = pd.read_csv(DATA_PATH, header=None)

    X = data.iloc[:, :-1].values
    y = data.iloc[:, -1].values

    encoder = LabelEncoder()
    y_encoded = encoder.fit_transform(y)

    with open(ENCODER_PATH, "wb") as f:
        pickle.dump(encoder, f)

    y_categorical = to_categorical(y_encoded)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y_categorical, test_size=0.2, random_state=42
    )

    num_classes = y_categorical.shape[1]

    status_dict["status"] = "training"

    model = Sequential([
        Dense(128, activation='relu', input_shape=(63,)),
        Dropout(0.3),
        Dense(64, activation='relu'),
        Dropout(0.3),
        Dense(num_classes, activation='softmax')
    ])

    model.compile(
        optimizer='adam',
        loss='categorical_crossentropy',
        metrics=['accuracy']
    )

    early_stop = EarlyStopping(patience=5, restore_best_weights=True)

    model.fit(
        X_train,
        y_train,
        epochs=40,
        batch_size=16,
        validation_data=(X_test, y_test),
        callbacks=[early_stop],
        verbose=0
    )

    loss, acc = model.evaluate(X_test, y_test, verbose=0)

    model.save(MODEL_PATH)

    status_dict["status"] = "completed"
    status_dict["accuracy"] = round(float(acc), 4)