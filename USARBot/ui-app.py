from flask import Flask, render_template, jsonify, request
import bridge

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('templates/index.html')          # your uploaded template

# --- REST endpoints -------------------------------------------------
@app.route('/api/state')
def api_state():
    # return the latest robot status & detections
    return jsonify({
        "state"      : dict(bridge.robot_state),
        "detections" : list(bridge.detections_queue)
    })

@app.route('/api/command', methods=['POST'])
def api_command():
    data = request.get_json(force=True)
    bridge.send_command(data)                     # e.g. {"cmd":"forward"}
    return jsonify({"ok": True})

# run only when launched directly
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=9000, threaded=True)
