# Gesture Desktop Control 🖐️💻

An intelligent, real-time desktop control application that lets you control your computer using custom hand gestures through a webcam. Built with a Flask backend, MediaPipe Hand Tracking, TensorFlow/Keras Neural Network (TFLite inference), and a sleek Vanilla CSS/JS single-page frontend.

---

## Features
- **Real-Time Hand Landmark Tracking**: Powered by Google MediaPipe for high-accuracy single-hand tracking.
- **Neural Network-Based Classification**: Dynamic classification of gestures using a lightweight Keras ANN, exported to TFLite for ultra-fast (~0.05ms) real-time inference.
- **High-Performance 3-Thread Architecture**: Dedicated camera capture, processing, and SocketIO emit threads eliminate frame lag and ensure smooth 25-30 FPS operation.
- **Extensive Cascading Action Library**: Remap gestures to keyboard events, system shortcuts, media playback, system volume controls, application launchers, or custom automated text injection.
- **Locked & Custom Gestures**: Work with stable built-in locked ML gestures (customizable mapping and display name) or create and train your own custom gestures.
- **Interactive Gesture Training Hub**: Collect custom landmark dataset, train the model directly in your browser with real-time progress, and hot-reload the updated model.
- **Live Video Feed Overlay**: Toggle and inspect predictions, landmark meshes, and confidence levels in real time.

---

## Tech Stack
- **Backend**: Python, Flask, Flask-SocketIO, MediaPipe, OpenCV, NumPy, Pandas, TensorFlow/Keras (training), TFLite (inference), PyAutoGUI, pywin32, Scikit-Learn
- **Frontend**: Vanilla HTML5, CSS3, JavaScript (ES6+, HashRouter routing, Dynamic Event Delegation)

---

## Architecture

The application uses a **3-thread processing architecture** for lag-free performance:

| Thread | Role | Details |
|--------|------|---------|
| **Capture Thread** | Camera I/O | Continuously drains the camera buffer, storing the latest frame behind a lock. The processing thread never blocks on `cap.read()`. |
| **Processing Thread** | MediaPipe + ML | Runs hand landmark detection on a downscaled 320×240 frame (4× fewer pixels), performs TFLite inference every 3rd frame, handles cursor tracking and action execution. |
| **Emit Worker Thread** | WebSocket I/O | Drains a bounded queue of SocketIO events, preventing slow network writes from stalling the processing loop. |

The **MJPEG streaming generator** does zero processing — it only reads the latest processed frame and JPEG-encodes it at 25 FPS.

---

## Installation & Setup

### Prerequisites
1. **Python**: Ensure Python 3.9+ is installed on your computer.
2. **Webcam**: A functional USB or integrated webcam is required.

### 1. Clone the Project
Open a terminal in your project directory:
```bash
cd "desktop hand gesture"
```

### 2. Install Dependencies
Install all required libraries using the pre-compiled `requirements.txt`:
```bash
pip install -r requirements.txt
```

---

## Launching the Program

1. Run the Flask backend server:
   ```bash
   python app.py
   ```
2. Open your web browser and navigate to:
   ```text
   http://127.0.0.1:5000
   ```
3. Allow the browser access to the webcam (or the system will access it directly depending on configured settings).

---

## Project Structure
- `app.py`: Web server running the Flask application, API endpoints, and route handlers.
- `camera_engine.py`: High-performance 3-thread engine for camera capture, MediaPipe processing, TFLite inference, and MJPEG streaming.
- `action_engine.py`: Executor translating recognized gesture labels into system hotkeys, applications, and mouse commands. Uses win32api for low-latency cursor control.
- `runtime_state.py`: Shared global memory managing tracking configurations and active process logs.
- `trainer.py`: Model architect compiling and training the gesture classification ANN, with automatic TFLite export.
- `main.py`: Standalone CLI version for headless gesture recognition (uses TFLite).
- `static/app.js`: SPA frontend controller executing page routing, dynamic remap modals, and interactive training loops.
- `templates/index.html`: Main SPA structure containing layout containers and template definitions.
- `config/`: Configuration directories storing system preferences, display names, and built-in indices.
- `model/`: Folder containing neural network models (`gesture_ann.tflite` for inference, `gesture_ann.keras` for warm-start training), label encoders, and training CSV files.
