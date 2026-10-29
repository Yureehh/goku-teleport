# Goku Teleport

Two fingers on your forehead → you vanish from Teams, with sound.

## Setup (macOS, one time)
1. `brew install --cask obs`, open OBS → **Start Virtual Camera** (installs the system extension; approve it in System Settings, restart if needed). Then you can close OBS.
2. System Settings → Privacy & Security → Camera → enable your terminal.
3. `python3.12 -m venv .venv && .venv/bin/pip install opencv-python mediapipe pyvirtualcam numpy`
   (the models are already in `models/`)
4. Turn off macOS Video Effects for the camera (menu bar camera icon → Reactions, Center Stage, Portrait, Background off).

## Usage
```
.venv/bin/python goku.py --cams                 # find your camera number
.venv/bin/python goku.py 1                      # real room: press B to capture it
.venv/bin/python goku.py 1 --bg                 # virtual background from backgrounds/ (N = next)
.venv/bin/python goku.py 1 --bg image.png       # or a single image/video
```
- In Teams: Settings → Devices → Camera → **OBS Virtual Camera**, background effects **None** (the app does the background).
- `backgrounds/` (not in git) holds the pool: images or mp4/mov (videos loop). Teams' own ones are in
  `~/Library/Containers/com.microsoft.teams2/Data/Library/Application Support/Microsoft/MSTeams/Backgrounds/`
- **B** (real-room mode) → 5 s to leave the frame, then it captures the empty background.
- **Gesture** (index + middle together on your forehead/temple, ring and pinky folded, ~0.5 s) or **Space** → vanish / reappear.
- **Q** or Ctrl+C → quit. Keys only work with the "goku debug" window in focus; the debug window never reaches Teams.
- Sound: put your own clip as `teleport.mp3`, `.m4a` or `.wav` (not in git); otherwise a generated `teleport.wav` plays on your speakers.

Calibration: constants at the top of `goku.py`. Check: `.venv/bin/python test_gesture.py`.
