#!/usr/bin/env python3


import os, sys, time, json, cv2, threading, random, readchar, termios, tempfile, itertools
import numpy as np
from collections import deque
from datetime import datetime
from flask import Flask, render_template, Response, jsonify, request, send_from_directory

from picrawler import Picrawler
from robot_hat import Music, Pin, Ultrasonic
from openai_helper import OpenAiHelper
from keys           import OPENAI_API_KEY, OPENAI_ASSISTANT_ID
from preset_actions import actions_dict
from utils          import sox_volume, speak_block

# ─────────────────────────── writable dirs ─────────────────────────────
BASE = os.path.abspath(os.path.dirname(__file__)); os.chdir(BASE)
def wdir(path, prefix):
    try:
        os.makedirs(path, exist_ok=True)
        p = os.path.join(path,'.probe'); open(p,'w').close(); os.remove(p)
        return path
    except OSError:
        return tempfile.mkdtemp(prefix=prefix)

STATIC_IMG_DIR = wdir(os.path.join(BASE,'static','images'),'snap_')
TTS_DIR        = wdir(os.path.join(BASE,'tts'),            'tts_')

# ────────────────────────── globals & flags ───────────────────────────
with_img = '--no-img' not in sys.argv
ALERT_DISTANCE, AUTO_SPEED = 30, 80
DETECTION_COOLDOWN = 30   # seconds between same-person detections
stop_event   = threading.Event()
orig_termios = termios.tcgetattr(sys.stdin.fileno())

movement_lock = threading.Lock()
gpt_active = manual_mode = explore_enabled = False
robot_state = {"mode":"idle"}

detections = deque(maxlen=100)
next_id    = itertools.count(1)
command_q  = deque()
key_q      = deque()
last_walk  = 0

# ────────────────────────── detection cooldown ─────────────────────────
last_person_detect = 0

# ─────────────────────────── odometry ────────────────────────────────
x_pos = y_pos = 0
heading = 0
STEP_UNIT = 1

def update_pose(act:str):
    global x_pos, y_pos, heading
    if act=='turn_left':
        heading = (heading - 90) % 360
    elif act=='turn_right':
        heading = (heading + 90) % 360
    elif act=='walk_forward':
        if   heading==0:   y_pos += STEP_UNIT
        elif heading==90:  x_pos += STEP_UNIT
        elif heading==180: y_pos -= STEP_UNIT
        elif heading==270: x_pos -= STEP_UNIT
    elif act=='walk_backward':
        if   heading==0:   y_pos -= STEP_UNIT
        elif heading==90:  x_pos -= STEP_UNIT
        elif heading==180: y_pos += STEP_UNIT
        elif heading==270: x_pos += STEP_UNIT

def perform_action(act:str):
    """Update odometry then invoke the preset action."""
    if act in actions_dict:
        update_pose(act)
        actions_dict[act](my_spider)

# ────────────────────────── hardware init ────────────────────────────
my_spider = Picrawler(); time.sleep(1)
music, led = Music(), Pin('LED')
sonar      = Ultrasonic(Pin("D2"), Pin("D3"))

if with_img:
    from vilib import Vilib
    Vilib.camera_start(vflip=False, hflip=False)
    Vilib.display(local=False, web=False)
    Vilib.show_fps(); time.sleep(0.4)

def frame():
    for a in ('img','frame','camera_frame'):
        if hasattr(Vilib,a):
            return getattr(Vilib, a)
    return None

def mjpeg():
    while not stop_event.is_set():
        if with_img and (f := frame()) is not None:
            ok, buf = cv2.imencode('.jpg', f)
            if ok:
                yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n'
                       + buf.tobytes() + b'\r\n')
        time.sleep(0.05)

# ────────────────────────── OpenAI + TTS ─────────────────────────────
openai_helper = OpenAiHelper(OPENAI_API_KEY, OPENAI_ASSISTANT_ID,'picrawler')
VOLUME_DB, TTS_VOICE = 3, 'nova'
speech_ready = False
tts_file = None
speech_lock = threading.Lock()

# ────────────────────────── Flask UI ──────────────────────────────────
app = Flask(__name__, static_folder='static', template_folder='templates')

@app.route('/')
def index():
    sv = [d for d in detections if d['type']=='survivor']
    hz = [d for d in detections if d['type']=='hazard']
    return render_template('index.html', targets=sv, obstacles=hz, video_feed=True)

@app.route('/api/state')
def api_state():
    return jsonify({"state": robot_state, "detections": list(detections)})

@app.route('/video_feed')
def video_feed():
    return Response(mjpeg(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/api/command', methods=['POST'])
def api_command():
    c = (request.get_json(force=True) or {}).get('cmd','').lower()
    if c in {'manual','start','scan'}:
        command_q.append(c)
        return jsonify(ok=True)
    return jsonify(ok=False), 400

@app.route('/api/key', methods=['POST'])
def api_key():
    k = (request.get_json(force=True) or {}).get('key','').lower()
    if k in {'w','a','s','d','q'}:
        key_q.append(k)
        return jsonify(ok=True)
    return jsonify(ok=False), 400

@app.route('/images/<path:filename>')
def serve_image(filename):
    return send_from_directory(STATIC_IMG_DIR, filename)

def start_flask():
    app.run(host='0.0.0.0', port=9000,
            threaded=True, debug=False, use_reloader=False)

# ───────────────────── detection & GPT helpers ────────────────────────
def add_detection(kind, img='', name=''):
    detections.append({
        "id":   next(next_id),
        "type": kind,
        "image": img,
        "name": name,
        "x":    x_pos,
        "y":    y_pos,
        "z":    0,
        "time": time.time()
    })

def gpt_actions(actions):
    for a in actions:
        perform_action(a.strip().lower().replace(' ','_'))

last_snap, SNAP_COOL = 0, 10
def snapshot_and_gpt(src:str):
    global last_snap, gpt_active, speech_ready, tts_file
    if time.time() - last_snap < SNAP_COOL:
        return
    last_snap = time.time()
    gpt_active = True

    with movement_lock:
        # look up instead of sit for better view
        perform_action('look_up')

    rel = ''; img_path = None
    if with_img and (f := frame()) is not None:
        rel = f'snap_{int(time.time())}.jpg'
        img_path = os.path.join(STATIC_IMG_DIR, rel)
        if not cv2.imwrite(img_path, f):
            img_path = None

    raw = (openai_helper.dialogue_with_img(src, img_path)
           if img_path else openai_helper.dialogue(src))
    try:
        parsed = raw if isinstance(raw, dict) else json.loads(str(raw))
    except:
        parsed = None

    answer = parsed.get('answer','')  if parsed else str(raw)
    acts   = parsed.get('actions',[]) if parsed else []
    surv   = bool(parsed.get('survivor',False)) if parsed else False
    haz    = (parsed.get('hazard') or '').strip() if parsed else ''

    # TTS first (overlap speech+motion)
    if answer:
        ts = datetime.now().strftime('%y%m%d_%H%M%S')
        raw_wav = os.path.join(TTS_DIR, f'{ts}_raw.wav')
        if openai_helper.text_to_speech(answer, raw_wav, TTS_VOICE, 'wav'):
            tts_file = os.path.join(TTS_DIR, f'{ts}_{VOLUME_DB}dB.wav')
            sox_volume(raw_wav, tts_file, VOLUME_DB)
            with speech_lock:
                speech_ready = True

    # run GPT‐directed actions
    gpt_actions(acts)

    # record detection or cleanup
    if surv:
        add_detection('survivor', rel)
    elif haz:
        add_detection('hazard', rel, haz)
    else:
        if img_path and os.path.isfile(img_path):
            os.remove(img_path)

    with movement_lock:
        my_spider.do_action('stand', speed=60)
    gpt_active = False

# ────────────────────────── background threads ─────────────────────────
def tts_thread():
    global speech_ready
    while not stop_event.is_set():
        if speech_ready:
            with speech_lock:
                speak_block(music, tts_file)
                speech_ready = False
        time.sleep(0.05)

def yolov5_thread(model="models/yolov5s_f16.tflite", thresh=0.8):
    import tflite_runtime.interpreter as tflite

    global last_person_detect

    # load model into memory buffer
    model_path = os.path.join(BASE, model)
    buf = open(model_path,'rb').read()
    interp = tflite.Interpreter(model_content=buf)
    interp.allocate_tensors()

    inp  = interp.get_input_details()[0]
    out1 = interp.get_output_details()[0]

    # determine input shape & dtype
    _, *shape = inp['shape']
    if len(shape)==3:
        in_h, in_w, _ = shape
    else:
        in_h, in_w = shape[1], shape[2]
    expected_dtype = np.dtype(inp['dtype'])

    while not stop_event.is_set():
        if not (with_img and explore_enabled):
            time.sleep(0.1); continue

        f = frame()
        if f is None:
            time.sleep(0.05); continue

        # preprocess to correct dtype
        img = cv2.resize(f, (in_w, in_h))
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        tensor = np.expand_dims(img, 0).astype(expected_dtype)
        if expected_dtype == np.float32:
            tensor = tensor / 255.0

        interp.set_tensor(inp['index'], tensor)
        interp.invoke()
        pred = interp.get_tensor(out1['index'])[0]

        # parse YOLOv5 output: [x,y,w,h,obj,cls0,cls1...]
        obj_scores  = pred[:,4]
        class_probs = pred[:,5:]
        class_ids   = class_probs.argmax(axis=1)
        scores      = obj_scores * class_probs[np.arange(len(class_ids)), class_ids]

        # if PERSON detected and past cooldown
        now = time.time()
        if (now - last_person_detect > DETECTION_COOLDOWN) and np.any((class_ids==0) & (scores>thresh)):
            last_person_detect = now
            snapshot_and_gpt("YOLOv5‑TFLite person")
            time.sleep(1.0)
        else:
            time.sleep(0.1)

def obstacle_thread():
    while not stop_event.is_set():
        if gpt_active or manual_mode or not explore_enabled:
            time.sleep(0.2); continue
        if time.time() - last_walk < 0.35:
            time.sleep(0.1); continue
        d = sonar.read()
        if 0 <= d <= ALERT_DISTANCE:
            turn = random.choice(['turn_left','turn_right'])
            with movement_lock:
                perform_action(turn)
        time.sleep(0.2)

def cmd_thread():
    global manual_mode, explore_enabled
    while not stop_event.is_set():
        if command_q:
            c = command_q.popleft()
            if c=='manual':
                explore_enabled=False; manual_mode=True; robot_state["mode"]="manual"
                with movement_lock: my_spider.do_action('sit',speed=80)
            elif c=='start':
                manual_mode=False; explore_enabled=True; robot_state["mode"]="autonomous"
            elif c=='scan':
                snapshot_and_gpt("UI Scan")
        time.sleep(0.1)

KEY_MAP={'w':'walk_forward','a':'turn_left','s':'walk_backward','d':'turn_right'}
def key_consumer():
    global last_walk
    while not stop_event.is_set():
        if manual_mode and key_q:
            k = key_q.popleft()
            if k=='q':
                command_q.append('start'); continue
            act = KEY_MAP.get(k)
            if act:
                with movement_lock:
                    my_spider.do_action('stand',speed=60)
                    perform_action(act)
                    if act=='walk_forward':
                        last_walk = time.time()
        time.sleep(0.05)

def ssh_keys():
    print("SSH keys: c=snapshot  m=manual  x=quit")
    while not stop_event.is_set():
        if manual_mode:
            time.sleep(0.05); continue
        try:
            ch = readchar.readkey().lower()
        except KeyboardInterrupt:
            continue
        if ch=='c':
            snapshot_and_gpt("SSH snap")
        elif ch=='m':
            command_q.append('manual')
        elif ch=='x':
            stop_event.set(); break
        time.sleep(0.05)

def explore_loop():
    global last_walk
    while not stop_event.is_set():
        if explore_enabled and not (manual_mode or gpt_active):
            for _ in range(random.randint(10,20)):
                if stop_event.is_set() or manual_mode or gpt_active:
                    break
                with movement_lock:
                    perform_action('walk_forward')
                    last_walk = time.time()
                time.sleep(0.3)
        else:
            time.sleep(0.5)

# ─────────────────────────── main entrypoint ──────────────────────────
def main():
    with movement_lock:
        my_spider.do_action('sit',speed=60)

    for tgt in (
        start_flask,
        tts_thread,
        yolov5_thread,    
        obstacle_thread,
        cmd_thread,
        key_consumer,
        ssh_keys):
        threading.Thread(target=tgt, daemon=True).start()

    try:
        explore_loop()
    finally:
        stop_event.set()
        if with_img:
            Vilib.camera_close()
        with movement_lock:
            my_spider.do_action('sit',speed=60)
        termios.tcsetattr(sys.stdin.fileno(),
                          termios.TCSADRAIN, orig_termios)
        print("\nExited cleanly.")

if __name__=='__main__':
    try:
        main()
    except Exception:
        termios.tcsetattr(sys.stdin.fileno(),
                          termios.TCSADRAIN, orig_termios)
        raise
