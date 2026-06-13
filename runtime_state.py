# Shared state
current_prediction = {"gesture": None, "confidence": 0}

# System state
camera_running = False
system_active = False

# Action log (circular buffer, last 50)
action_log = []
MAX_LOG_SIZE = 50

# Training state
training_status = {"status": "idle", "epoch": 0, "accuracy": 0}

# Collection state
collection_target = None
collection_buffer = []
collection_status = {"status": "idle", "progress": 0, "samples": 0}

# Settings
settings = {
    "camera_index": 0,
    "confidence_threshold": 0.85,
    "frame_confirmation": 5,
    "action_cooldown": 1.0,
}