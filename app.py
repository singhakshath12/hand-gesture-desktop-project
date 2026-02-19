from flask import Flask, render_template, request, jsonify
import json
import subprocess

app = Flask(__name__)

ACTION_MAP_PATH = "action_map.json"

def load_action_map():
    with open(ACTION_MAP_PATH) as f:
        return json.load(f)


def save_action_map(data):
    with open(ACTION_MAP_PATH, "w") as f:
        json.dump(data, f, indent=4)


@app.route("/")
def dashboard():
    action_map = load_action_map()
    return render_template("index.html", action_map=action_map)


@app.route("/update", methods=["POST"])
def update_action():
    data = request.json
    action_map = load_action_map()

    gesture = data["gesture"]
    action_map[gesture] = data["action"]

    save_action_map(action_map)
    return jsonify({"status": "updated"})


@app.route("/retrain", methods=["POST"])
def retrain():
    subprocess.Popen(["python", "trainer.py"])
    return jsonify({"status": "retraining_started"})

@app.route("/delete", methods=["POST"])
def delete_gesture():
    data = request.json
    gesture = data["gesture"]

    action_map = load_action_map()

    if gesture in action_map:
        del action_map[gesture]

    save_action_map(action_map)

    return jsonify({"status": "deleted"})



if __name__ == "__main__":
    app.run(debug=True)
