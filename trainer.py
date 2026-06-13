import pandas as pd
import numpy as np
import pickle
import os
import tensorflow as tf
from tensorflow.keras.models import Sequential, load_model
from tensorflow.keras.layers import Dense, Dropout
from tensorflow.keras.utils import to_categorical
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder

BUILTIN_DATA_PATH = "model/desktop_gesture_data.csv"
CUSTOM_DATA_PATH = "model/custom_gesture_data.csv"
MODEL_PATH = "model/gesture_ann.keras"
ENCODER_PATH = "model/label_encoder.pkl"

class ProgressCallback(tf.keras.callbacks.Callback):
    def __init__(self, socketio, total_epochs):
        self.socketio = socketio
        self.total_epochs = total_epochs
        
    def on_epoch_end(self, epoch, logs=None):
        if self.socketio:
            self.socketio.emit('training_progress', {
                'status': 'training',
                'epoch': epoch + 1,
                'total_epochs': self.total_epochs,
                'loss': round(float(logs.get('loss', 0)), 4),
                'accuracy': round(float(logs.get('accuracy', 0)), 4),
                'val_accuracy': round(float(logs.get('val_accuracy', 0)), 4),
                'progress': int((epoch + 1) / self.total_epochs * 100)
            })

def train_model(status_dict=None, socketio=None):
    try:
        if status_dict:
            status_dict["status"] = "loading_data"
            
        if socketio:
            socketio.emit('training_progress', {'status': 'loading_data'})

        # Load built-in data (locked)
        df_builtin = pd.read_csv(BUILTIN_DATA_PATH, header=None)
        
        # Load custom data if it exists
        df_custom = None
        if os.path.exists(CUSTOM_DATA_PATH):
            try:
                df_custom = pd.read_csv(CUSTOM_DATA_PATH, header=None)
            except pd.errors.EmptyDataError:
                pass
            
        # Extract unique classes from built-in data first to lock their indices
        builtin_classes = df_builtin.iloc[:, -1].unique().tolist()
        master_classes = builtin_classes.copy()
        
        # Combine datasets
        if df_custom is not None and not df_custom.empty:
            df = pd.concat([df_builtin, df_custom], ignore_index=True)
            # Append any new custom classes to the master list
            custom_classes = df_custom.iloc[:, -1].unique().tolist()
            for cls in custom_classes:
                if cls not in master_classes:
                    master_classes.append(cls)
        else:
            df = df_builtin
            
        # Split features and labels
        X = df.iloc[:, :-1].values
        y = df.iloc[:, -1].values
        
        # Encode labels using the locked master list
        encoder = LabelEncoder()
        encoder.fit(master_classes)
        y_encoded = encoder.transform(y)
        y_categorical = to_categorical(y_encoded)
        num_classes = len(encoder.classes_)
        
        # Save new encoder
        with open(ENCODER_PATH, 'wb') as f:
            pickle.dump(encoder, f)
            
        # Train/Test split
        X_train, X_test, y_train, y_test = train_test_split(
            X, y_categorical, test_size=0.2, random_state=42
        )
        
        if status_dict:
            status_dict["status"] = "training"

        # Warm Start Logic
        epochs = 100  # Increased epochs for warm start fine-tuning with early stopping
        
        if os.path.exists(MODEL_PATH):
            base_model = load_model(MODEL_PATH)
            old_num_classes = base_model.output_shape[-1]
            
            if old_num_classes == num_classes:
                # Same number of classes, just fine-tune
                model = base_model
                # Lower learning rate for fine-tuning
                model.compile(optimizer=tf.keras.optimizers.Adam(learning_rate=0.0005), 
                              loss='categorical_crossentropy', 
                              metrics=['accuracy'])
            else:
                # Number of classes changed, rebuild top layer
                model = Sequential()
                # Copy all layers except the last one
                for layer in base_model.layers[:-1]:
                    layer.trainable = False  # Freeze earlier layers
                    model.add(layer)
                    
                # Add new classification layer
                model.add(Dense(num_classes, activation='softmax', name=f'dense_new_{num_classes}'))
                model.compile(optimizer='adam', 
                              loss='categorical_crossentropy', 
                              metrics=['accuracy'])
        else:
            # Train from scratch if model missing
            epochs = 150
            model = Sequential([
                Dense(128, activation='relu', input_shape=(X.shape[1],)),
                Dropout(0.3),
                Dense(64, activation='relu'),
                Dropout(0.3),
                Dense(num_classes, activation='softmax')
            ])
            model.compile(optimizer='adam', loss='categorical_crossentropy', metrics=['accuracy'])

        # Train model
        callbacks = [tf.keras.callbacks.EarlyStopping(monitor='val_loss', patience=5, restore_best_weights=True)]
        if socketio:
            callbacks.append(ProgressCallback(socketio, epochs))
            
        model.fit(
            X_train, y_train,
            epochs=epochs,
            batch_size=16,
            validation_data=(X_test, y_test),
            callbacks=callbacks,
            verbose=1
        )
        
        loss, accuracy = model.evaluate(X_test, y_test, verbose=0)
        
        # Save model
        model.save(MODEL_PATH)
        
        if status_dict:
            status_dict["status"] = "completed"
            status_dict["accuracy"] = float(accuracy)
            
        if socketio:
            socketio.emit('training_progress', {
                'status': 'completed',
                'accuracy': round(float(accuracy), 4) * 100
            })
            
    except Exception as e:
        print(f"Training error: {e}")
        if status_dict:
            status_dict["status"] = "error"
        if socketio:
            socketio.emit('training_progress', {'status': 'error', 'message': str(e)})