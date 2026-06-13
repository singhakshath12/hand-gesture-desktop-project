import pandas as pd
import numpy as np
import pickle
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense, Dropout
from tensorflow.keras.utils import to_categorical
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from tensorflow.keras.callbacks import EarlyStopping

data = pd.read_csv("model/desktop_gesture_data.csv", header=None)

X = data.iloc[:, :-1].values
y = data.iloc[:, -1].values

unique_classes = data.iloc[:, -1].unique().tolist()
encoder = LabelEncoder()
encoder.fit(unique_classes)
y_encoded = encoder.transform(y)

with open("model/label_encoder.pkl", "wb") as f:
    pickle.dump(encoder, f)

y_categorical = to_categorical(y_encoded)

X_train, X_test, y_train, y_test = train_test_split( X, y_categorical, test_size=0.2, random_state=12)

num_classes = y_categorical.shape[1]

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
    epochs=50,
    batch_size=16,
    validation_data=(X_test, y_test),
    callbacks=[early_stop]
)

loss, acc = model.evaluate(X_test, y_test)
print("Final Accuracy:", acc)
print(encoder.classes_)

model.save("model/gesture_ann.keras")
