"""
Camera Engine — High-performance 3-thread architecture for real-time gesture recognition.

Thread 1: Camera Capture (continuous, non-blocking frame acquisition)
Thread 2: Processing (MediaPipe + TFLite inference + cursor/action)
Thread 3: SocketIO Emit Worker (async event emission via queue)

The MJPEG generator only reads the latest processed frame — zero processing inline.
"""

import cv2
import numpy as np
import mediapipe as mp
import threading
import time
import collections
import queue
import csv
import os
import json
import pickle

import runtime_state as rs
import action_engine

# ── Paths ─────────────────────────────────────────────────────────────────────
TFLITE_PATH = "model/gesture_ann.tflite"
ENCODER_PATH = "model/label_encoder.pkl"
CUSTOM_DATA_PATH = "model/custom_gesture_data.csv"
DISPLAY_NAMES_PATH = "config/display_names.json"

# ── TFLite Interpreter Import ─────────────────────────────────────────────────
try:
    from tflite_runtime.interpreter import Interpreter as TFLiteInterpreter
except ImportError:
    import tensorflow as tf
    TFLiteInterpreter = tf.lite.Interpreter


class CameraEngine:
    """
    Encapsulates the entire camera → processing → streaming pipeline.
    Uses 3 dedicated threads modeled after the reference project's architecture.
    """

    def __init__(self, socketio):
        self.socketio = socketio
        self.running = False
        self.thread = None

        # Frame output for MJPEG streaming
        self.frame_lock = threading.Lock()
        self.output_frame = None

        # Thread safety lock for model loading/inference
        self.model_lock = threading.Lock()

        # TFLite model
        self.interpreter = None
        self.input_details = None
        self.output_details = None
        self.encoder = None
        self.model_loaded = False

        # Display names cache
        self._display_names_cache = None
        self._display_names_mtime = 0

        # Load ML assets
        self.load_model()

    # ── Model Loading ─────────────────────────────────────────────────────────

    def load_model(self):
        """Load TFLite model and label encoder from disk."""
        with self.model_lock:
            try:
                if os.path.exists(TFLITE_PATH):
                    interpreter = TFLiteInterpreter(model_path=TFLITE_PATH)
                    interpreter.allocate_tensors()
                    input_details = interpreter.get_input_details()
                    output_details = interpreter.get_output_details()
                    self.interpreter = interpreter
                    self.input_details = input_details
                    self.output_details = output_details
                    print(f"[Engine] TFLite model loaded from {TFLITE_PATH}")
                else:
                    print(f"[Engine] TFLite model not found at {TFLITE_PATH} — run training first")

                if os.path.exists(ENCODER_PATH):
                    with open(ENCODER_PATH, 'rb') as f:
                        self.encoder = pickle.load(f)

                self.model_loaded = (self.interpreter is not None and self.encoder is not None)
            except Exception as e:
                print(f"[Engine] Error loading ML assets: {e}")
                self.model_loaded = False

    def reload_model(self):
        """Hot-reload model from disk (called after training completes)."""
        self.load_model()

    # ── Cache Management ──────────────────────────────────────────────────────

    def invalidate_caches(self):
        """Invalidate all in-memory caches (called after config writes)."""
        self._display_names_cache = None
        self._display_names_mtime = 0
        action_engine.invalidate_cache()

    def get_display_names(self):
        """Get display names with mtime-based caching."""
        try:
            if os.path.exists(DISPLAY_NAMES_PATH):
                mtime = os.path.getmtime(DISPLAY_NAMES_PATH)
                if self._display_names_cache is None or mtime != self._display_names_mtime:
                    with open(DISPLAY_NAMES_PATH, 'r') as f:
                        self._display_names_cache = json.load(f)
                    self._display_names_mtime = mtime
        except Exception:
            pass
        return self._display_names_cache or {}

    # ── Feature Extraction ────────────────────────────────────────────────────

    @staticmethod
    def _normalize_landmarks(landmarks):
        """Convert 21 MediaPipe landmarks to a normalized 63-feature vector."""
        base_x = landmarks.landmark[0].x
        base_y = landmarks.landmark[0].y
        base_z = landmarks.landmark[0].z
        features = []
        for lm in landmarks.landmark:
            features.extend([lm.x - base_x, lm.y - base_y, lm.z - base_z])
        features = np.array(features, dtype=np.float32)

        # Hand-scale normalization: distance from wrist to middle finger MCP (landmark 9)
        scale_dist = np.linalg.norm(features[27:30])
        if scale_dist > 0:
            features = features / scale_dist
        return features.reshape(1, -1)

    @staticmethod
    def _compute_finger_states(landmarks):
        """Heuristic finger up/down detection for dual shape-gating."""
        lm = landmarks.landmark
        i_ty, i_py, i_my = lm[8].y, lm[6].y, lm[5].y
        m_ty, m_py, m_my = lm[12].y, lm[10].y, lm[9].y
        r_ty, r_py, r_my = lm[16].y, lm[14].y, lm[13].y
        p_ty, p_py, p_my = lm[20].y, lm[18].y, lm[17].y

        th_tx = lm[4].x
        th_ix = lm[3].x
        w_x = lm[0].x
        thumb_dist_tip = abs(th_tx - w_x)
        thumb_dist_ip = abs(th_ix - w_x)

        return {
            "thumb":  thumb_dist_tip > thumb_dist_ip * 1.1,
            "index":  i_ty < i_py or i_ty < i_my,
            "middle": m_ty < m_py or m_ty < m_my,
            "ring":   r_ty < r_py or r_ty < r_my,
            "pinky":  p_ty < p_py or p_ty < p_my,
        }

    # ── TFLite Inference ──────────────────────────────────────────────────────

    def _predict_tflite(self, features):
        """Run TFLite inference on a (1, 63) feature array. Returns raw output array."""
        with self.model_lock:
            if not self.model_loaded or self.interpreter is None:
                return None
            try:
                input_data = features.astype(np.float32)
                self.interpreter.set_tensor(self.input_details[0]['index'], input_data)
                self.interpreter.invoke()
                return self.interpreter.get_tensor(self.output_details[0]['index'])
            except Exception as e:
                print(f"[Engine] Prediction error: {e}")
                return None

    # ── Engine Lifecycle ──────────────────────────────────────────────────────

    def start(self):
        """Start the engine's background threads."""
        if self.running and self.thread and self.thread.is_alive():
            return
        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()

    def stop(self):
        """Stop the engine (camera released, threads exit)."""
        self.running = False

    # ── Main Processing Loop ──────────────────────────────────────────────────

    def _run_loop(self):
        """Main loop: 3-thread camera → MediaPipe → TFLite → actions."""

        # ── Camera Init ───────────────────────────────────────────────────────
        active_cam_idx = rs.settings.get("camera_index", 0)
        cap = cv2.VideoCapture(active_cam_idx)
        if not cap.isOpened():
            for alt in [0, 1, 2]:
                if alt != active_cam_idx:
                    cap = cv2.VideoCapture(alt)
                    if cap.isOpened():
                        print(f"[Engine] Camera index {active_cam_idx} failed. Switched to index {alt}")
                        active_cam_idx = alt
                        break

        if cap.isOpened():
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            cap.set(cv2.CAP_PROP_FPS, 30)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        # ── Thread 1: Dedicated Capture Thread ────────────────────────────────
        _cap_lock = threading.Lock()
        _latest_raw = [None]
        _cap_alive = [True]
        _frame_seq = [0]

        def _capture_loop():
            nonlocal cap, active_cam_idx
            while _cap_alive[0] and self.running:
                # Dynamic camera index switching
                target_idx = rs.settings.get("camera_index", 0)
                if target_idx != active_cam_idx:
                    print(f"[Engine] Switching camera index from {active_cam_idx} to {target_idx}...")
                    if cap:
                        cap.release()
                    cap = cv2.VideoCapture(target_idx)
                    active_cam_idx = target_idx
                    if cap.isOpened():
                        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                        cap.set(cv2.CAP_PROP_FPS, 30)
                        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

                if cap is None or not cap.isOpened():
                    time.sleep(0.1)
                    continue
                ok, frm = cap.read()
                if ok:
                    with _cap_lock:
                        _latest_raw[0] = frm
                        _frame_seq[0] += 1
                else:
                    time.sleep(0.03)

        _cap_thread = threading.Thread(target=_capture_loop, daemon=True)
        _cap_thread.start()

        # ── Thread 3: Non-blocking SocketIO Emit Worker ───────────────────────
        _emit_q = queue.Queue(maxsize=16)

        def _emit_worker():
            while self.running or not _emit_q.empty():
                try:
                    event, data = _emit_q.get(timeout=1.0)
                    if self.socketio:
                        self.socketio.emit(event, data)
                    _emit_q.task_done()
                except queue.Empty:
                    pass

        _emit_thread = threading.Thread(target=_emit_worker, daemon=True)
        _emit_thread.start()

        def _safe_emit(event, data):
            try:
                _emit_q.put_nowait((event, data))
            except queue.Full:
                pass

        # ── Wait for first frame (with timeout) ───────────────────────────────
        wait_start = time.time()
        while _latest_raw[0] is None and self.running:
            if time.time() - wait_start > 5.0:
                print("[Engine] Warning: Timeout waiting for camera frames.")
                break
            time.sleep(0.01)

        # ── Pre-allocated buffers for MediaPipe ───────────────────────────────
        # MediaPipe runs on DOWNSCALED 320×240 (4× fewer pixels).
        # Landmark coords are normalized 0–1, so resolution-independent.
        MP_W, MP_H = 320, 240
        _small_buf = np.empty((MP_H, MP_W, 3), dtype=np.uint8)
        _rgb_small = np.empty((MP_H, MP_W, 3), dtype=np.uint8)

        # Pre-built DrawingSpec — avoids Python object allocation per frame
        mp_hands = mp.solutions.hands
        mp_drawing = mp.solutions.drawing_utils
        _lm_style = mp_drawing.DrawingSpec(thickness=2, circle_radius=1, color=(0, 127, 255))
        _con_style = mp_drawing.DrawingSpec(thickness=1, circle_radius=0, color=(0, 80, 160))

        # ── Local processing state ────────────────────────────────────────────

        class GestureSmoother:
            def __init__(self, window_size=5):
                self.window = collections.deque(maxlen=window_size)

            def add_and_get_majority(self, gesture):
                if not gesture:
                    self.window.append("None")
                else:
                    self.window.append(gesture)

                if len(self.window) < self.window.maxlen:
                    return None

                counts = collections.Counter(self.window)
                most_common, count = counts.most_common(1)[0]
                if count / len(self.window) >= 0.55 and most_common != "None":
                    return most_common
                return None

        gesture_smoother = GestureSmoother(5)
        is_gesture_active = False
        was_pinching = False
        last_collect_time = 0
        frame_count = 0
        fps_start = time.time()
        _last_seq = -1
        predict_counter = 0
        no_hand_emit_counter = 0

        # ── Thread 2: MediaPipe Processing (this thread) ──────────────────────
        with mp_hands.Hands(
            model_complexity=0,
            min_detection_confidence=0.7,
            min_tracking_confidence=0.5,
            max_num_hands=1,
        ) as hands:

            while self.running:
                # ── Grab latest frame (non-blocking) ──────────────────────────
                with _cap_lock:
                    image = _latest_raw[0]
                    this_seq = _frame_seq[0]

                if image is None:
                    time.sleep(0.004)
                    continue

                # Camera hasn't produced a new frame yet — yield CPU
                if this_seq == _last_seq:
                    time.sleep(0.002)
                    continue
                _last_seq = this_seq

                # ── FPS tracking ──────────────────────────────────────────────
                frame_count += 1
                now = time.time()
                if now - fps_start >= 1.0:
                    _safe_emit('fps_update', {'fps': frame_count})
                    frame_count = 0
                    fps_start = now

                # ── Process if engine is running OR collecting data ────────────
                if rs.camera_running or rs.collection_target is not None:
                    # MediaPipe on DOWNSCALED frame
                    cv2.resize(image, (MP_W, MP_H), dst=_small_buf,
                               interpolation=cv2.INTER_LINEAR)
                    cv2.cvtColor(_small_buf, cv2.COLOR_BGR2RGB, dst=_rgb_small)
                    _rgb_small.flags.writeable = False
                    results = hands.process(_rgb_small)
                    _rgb_small.flags.writeable = True

                    # Use full-res image for display
                    display_frame = image.copy()

                    if results.multi_hand_landmarks:
                        for hand_landmarks in results.multi_hand_landmarks:
                            # Draw landmarks on display frame
                            mp_drawing.draw_landmarks(
                                display_frame, hand_landmarks,
                                mp_hands.HAND_CONNECTIONS,
                                _lm_style, _con_style)

                            # ── Data Collection Mode ──────────────────────────
                            if rs.collection_target is not None:
                                current_time = time.time()
                                if current_time - last_collect_time > 0.03:
                                    last_collect_time = current_time
                                    features = self._normalize_landmarks(hand_landmarks)

                                    rs.collection_buffer.append(
                                        features[0].tolist() + [rs.collection_target])
                                    rs.collection_status["samples"] = len(rs.collection_buffer)

                                    MAX_SAMPLES = 400
                                    progress = int(
                                        (rs.collection_status["samples"] / MAX_SAMPLES) * 100)
                                    rs.collection_status["progress"] = progress

                                    if rs.collection_status["samples"] % 10 == 0:
                                        _safe_emit('collection_progress', {
                                            'status': 'collecting',
                                            'progress': progress,
                                            'samples': rs.collection_status["samples"],
                                            'total': MAX_SAMPLES
                                        })

                                    if rs.collection_status["samples"] >= MAX_SAMPLES:
                                        # Save to CSV
                                        with open(CUSTOM_DATA_PATH, "a", newline="") as f:
                                            writer = csv.writer(f)
                                            writer.writerows(rs.collection_buffer)

                                        rs.collection_target = None
                                        rs.collection_buffer = []
                                        rs.collection_status["status"] = "completed"
                                        _safe_emit('collection_progress', {
                                            'status': 'completed',
                                            'progress': 100,
                                            'samples': MAX_SAMPLES,
                                            'total': MAX_SAMPLES
                                        })

                            # ── Normal Prediction Engine Mode ─────────────────
                            elif rs.camera_running:
                                # Instant Pinch-to-Click (bypasses ML, runs every frame)
                                th_tip = hand_landmarks.landmark[4]
                                idx_tip = hand_landmarks.landmark[8]
                                pinch_dist = ((th_tip.x - idx_tip.x)**2 +
                                              (th_tip.y - idx_tip.y)**2)**0.5
                                is_pinching = pinch_dist < 0.05

                                if is_pinching and not was_pinching:
                                    action_result = action_engine.trigger_action("ok", 0)
                                    if action_result:
                                        log_entry = {
                                            "gesture": "ok (Instant)",
                                            "action": action_result["description"],
                                            "timestamp": time.time()
                                        }
                                        rs.action_log.insert(0, log_entry)
                                        if len(rs.action_log) > rs.MAX_LOG_SIZE:
                                            rs.action_log.pop()
                                        _safe_emit('action_triggered', log_entry)
                                was_pinching = is_pinching

                                # Full FPS Cursor Tracking (freeze if pinching)
                                effective_track = is_gesture_active and not is_pinching
                                action_engine.update_cursor(
                                    hand_landmarks, effective_track)

                                # ML prediction every 3rd frame (~10 FPS at 30 FPS)
                                predict_counter += 1
                                if predict_counter % 3 == 0:
                                    features = self._normalize_landmarks(hand_landmarks)

                                    if self.model_loaded:
                                        prediction = self._predict_tflite(features)
                                        if prediction is not None:
                                            class_idx = np.argmax(prediction)
                                            confidence = float(np.max(prediction))
                                            gesture = self.encoder.classes_[class_idx]

                                            # Dual Shape-Gating
                                            states = self._compute_finger_states(
                                                hand_landmarks)
                                            if (gesture == "palm" and not (
                                                    states["index"] and states["middle"]
                                                    and states["ring"] and states["pinky"])):
                                                confidence = 0.0
                                            elif (gesture == "fist" and (
                                                    states["index"] or states["middle"]
                                                    or states["ring"] or states["pinky"])):
                                                confidence = 0.0
                                            elif (gesture == "two_fingers" and not (
                                                    states["index"] and states["middle"])):
                                                confidence = 0.0

                                            display_names = self.get_display_names()
                                            display_gesture = display_names.get(
                                                gesture, gesture)

                                            rs.current_prediction = {
                                                "gesture": display_gesture,
                                                "confidence": confidence
                                            }
                                            _safe_emit('prediction', rs.current_prediction)

                                            if confidence >= rs.settings[
                                                    "confidence_threshold"]:
                                                smoothed = (
                                                    gesture_smoother
                                                    .add_and_get_majority(gesture))
                                                if smoothed:
                                                    action_map = (
                                                        action_engine.load_action_map())
                                                    action_info = action_map.get(
                                                        smoothed, {})

                                                    should_track = (
                                                        action_info.get("type")
                                                        == "tracking")
                                                    is_gesture_active = should_track

                                                    if not should_track:
                                                        action_result = (
                                                            action_engine
                                                            .trigger_action(
                                                                smoothed,
                                                                rs.settings[
                                                                    "action_cooldown"]))
                                                        if action_result:
                                                            log_entry = {
                                                                "gesture":
                                                                    display_gesture,
                                                                "action":
                                                                    action_result[
                                                                        "description"],
                                                                "timestamp":
                                                                    time.time()
                                                            }
                                                            rs.action_log.insert(
                                                                0, log_entry)
                                                            if len(rs.action_log) > (
                                                                    rs.MAX_LOG_SIZE):
                                                                rs.action_log.pop()
                                                            _safe_emit(
                                                                'action_triggered',
                                                                log_entry)
                                                else:
                                                    is_gesture_active = False
                                            else:
                                                gesture_smoother.add_and_get_majority(
                                                    None)
                                                is_gesture_active = False
                    else:
                        # No hand detected
                        if rs.collection_target is None and rs.camera_running:
                            rs.current_prediction = {
                                "gesture": None, "confidence": 0}
                            # Throttle no-hand emits (every 10th frame, not every frame)
                            no_hand_emit_counter += 1
                            if no_hand_emit_counter % 10 == 0:
                                _safe_emit('prediction', rs.current_prediction)
                            gesture_smoother.window.clear()
                            is_gesture_active = False
                else:
                    # Engine not running — just show raw camera feed
                    display_frame = image.copy()

                # ── Store frame for MJPEG streaming (reference swap) ──────────
                with self.frame_lock:
                    self.output_frame = display_frame

        # ── Cleanup ───────────────────────────────────────────────────────────
        _cap_alive[0] = False
        if cap and cap.isOpened():
            cap.release()

    # ── MJPEG Streaming Generator ─────────────────────────────────────────────

    def generate_frames(self):
        """
        Generator that yields MJPEG frames for the /api/camera/feed route.
        Does ZERO processing — only reads the latest processed frame.
        """
        encode_params = [cv2.IMWRITE_JPEG_QUALITY, 50]
        target_interval = 1.0 / 25.0  # 25 FPS display
        last_frame_id = -1

        while True:
            t0 = time.time()

            with self.frame_lock:
                frame_ref = self.output_frame

            if frame_ref is None:
                time.sleep(0.04)
                continue

            # Skip re-encoding if frame hasn't changed
            fid = id(frame_ref)
            if fid == last_frame_id:
                time.sleep(0.008)
                continue
            last_frame_id = fid

            ret, buf = cv2.imencode('.jpg', frame_ref, encode_params)
            if not ret:
                continue

            yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' +
                   buf.tobytes() + b'\r\n')

            # Rate-limit to target FPS
            wait = target_interval - (time.time() - t0)
            if wait > 0:
                time.sleep(wait)
