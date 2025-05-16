# USARBot – GPT-Powered PiCrawler Urban Search & Rescue Robot

**USARBot** is an advanced PiCrawler-based robot system enhanced with GPT-4 Vision, OpenCV, autonomous exploration, and a real-time web dashboard. Originally based on SunFounder's example code, this project expands it into a fully interactive search-and-rescue spider robot.

---

## 🚀 Features

- 🤖 Autonomous exploration with ultrasonic-based obstacle avoidance  
- 🧠 GPT-4o Vision integration with snapshot-based image understanding  
- 👀 human detection using yolov5
- 🎮 Manual control via keyboard   
- 🎥 Live camera feed 
- 🖼️ Web UI shows survivors and hazards with coordinates and thumbnails  
- 🔊 GPT-generated responses spoken aloud using OpenAI TTS and `sox`

---

---

## 🎬 Demo Video

[![USARBot Demo](https://img.youtube.com/vi/YOUR_VIDEO_ID_HERE/0.jpg)](https://www.youtube.com/watch?v=Cc84RhygEXo)

---

## 🛠️ Setup

### 1. Install Dependencies

Follow the official PiCrawler setup:  
[Setup](https://docs.sunfounder.com/projects/pi-crawler/en/latest/python/python_start/install_all_modules.html#install-all-modules)


### 2. Configure OpenAI Credentials

Create a file named `keys.py` in the root directory:

```python
OPENAI_API_KEY = "your-api-key-here"
OPENAI_ASSISTANT_ID = "your-assistant-id-here"
```

---

## 🧑‍🏫 Create Your GPT Assistant

Visit [OpenAI Assistants](https://platform.openai.com/assistants) and configure:

- **Name**: USARBot / PiCrawler
- **Instructions**:

```markdown
You are an AI spider robot named PiCrawler. With four legs, a camera, and an ultrasonic distance sensor. You are a search and rescue robot. Your goal is to search an area and find human survivors. You must avoid obstacles and detect hazards such as fire.  Greet all survivors and tell them that help is on the way.

## Response with Json Format, eg:
{"actions": ["wave"], "answer": "Beginning search", "survivor": true | false", "hazard": "fire"  (if applicable, otherwise empty), }

## Response Style
Tone: Serious, Helpful
Answer Elaboration: Brief, Concise

## Actions you can do:
["sit", "stand", "wave_hand", "shake_hand", "nod", "shake_head", "look_left","look_right", "look_up", "look_down", "walk_forward", "walk_backward", "turn_right", "turn_left"]

##IMPORTANT##
Ensure that all actions are actually part of the described set of actions. If you detect a hazard describe the hazard and fill the hazard field. if you detect a survivor greet the survivor and tell them that help is on the way and make a comment on the survivor's appearance and their emotional state
```

- **Model**: Use `gpt-4o or 4o-mini` for image understanding

---

##  Run the Program


```bash
sudo python3 usar.py
```

Open your browser and go to:

```
http://<raspberry-pi-ip>:9000
```

> ⚠️ **Run with `sudo`** or speaker output may fail.

---

## 🕹️ Controls

### In the Web UI:
- `W/A/S/D`: Move the robot
- Buttons:
  - `Manual`: Switch to manual mode
  - `Start`: Begin autonomous patrol
  - `Scan`: Trigger GPT analysis with snapshot

### Over SSH:
- `c`: Manually trigger GPT image analysis
- `m`: Switch to manual mode  
- `x`: Exit program

---

## 🌐 Web Dashboard

- **Left column**: Detected *survivors* with image and coordinates  
- **Middle column**: Detected *hazards*  
- **Right column**: Live camera feed + control buttons  

Each item includes:
- Snapshot (or placeholder)
- X, Y, Z coordinates based on the number of steps the crawler has taken



## ⚙️ Optional Configurations

Modify these in `usar.py`:

```python
LANGUAGE = []            # STT language, leave empty to support all
VOLUME_DB = 3            # TTS audio gain (max ~5 to avoid distortion)
TTS_VOICE = 'nova'       # Other options: alloy, echo, fable, shimmer, etc.
```

---

## 🧩 Project Structure

```
USARBot/
├── usar.py              # Main robot controller with GPT + Flask
├── index.html           # Web UI template
├── style.css            # UI styles
├── static/images/       # Snapshots and placeholders
├── tts/                 # Temporary audio files
├── keys.py              # Your OpenAI credentials
```

---

## 📦 Credits

- Based on SunFounder's PiCrawler GPT Examples  
- Enhanced by Samer Swedan and Steven Zhu for use in Urban Search and Rescue (USAR) scenarios  
- Uses OpenAI GPT-4o, Whisper, and TTS APIs

---


