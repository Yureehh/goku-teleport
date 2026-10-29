# Goku Teleport

Two fingers on your forehead → you vanish from Teams.

## Setup (macOS, one time)
1. `brew install --cask obs`, open OBS → **Start Virtual Camera** (installs the system extension; approve it in System Settings, restart if needed). Then you can close OBS.
2. System Settings → Privacy & Security → Camera → enable your terminal.
3. `python3.12 -m venv .venv && .venv/bin/pip install opencv-python mediapipe pyvirtualcam numpy`
   (the models are already in `models/`)

## Usage
```
.venv/bin/python goku.py
```
- In Teams: Settings → Devices → Camera → **OBS Virtual Camera**. Turn off Teams background effects.
- **B** → 5 s to leave the frame, then it captures the empty background (camera and chair stay put).
- **Gesture** (index + middle together on your forehead/temple, ring and pinky folded, ~0.5 s) or **Space** → vanish / reappear.
- **Q** → quit. Keys only work with the "goku debug" window in focus; the debug window never reaches Teams.

Calibration: constants at the top of `goku.py`. Check: `.venv/bin/python test_gesture.py`.
