<div align="center">

# Sorry, They Need Me

**Leave Teams meetings the way Goku leaves job interviews.**

<a href="https://giphy.com/gifs/goku-VIZi1DWTuZUcw"><img src="https://media.giphy.com/media/VIZi1DWTuZUcw/giphy.gif" width="520" alt="Goku in a suit teleporting out of a job interview"></a>

![Python](https://img.shields.io/badge/python-3.12-3776AB?logo=python&logoColor=white)
![MediaPipe](https://img.shields.io/badge/MediaPipe-hands%20%2B%20face%20%2B%20segmentation-0097A7?logo=google&logoColor=white)
![macOS | Windows](https://img.shields.io/badge/macOS%20%7C%20Windows-OBS%20Virtual%20Camera-555555?logo=obsstudio&logoColor=white)
[![tests](https://github.com/Yureehh/sorry-they-need-me/actions/workflows/test.yml/badge.svg)](https://github.com/Yureehh/sorry-they-need-me/actions/workflows/test.yml)
![Runs locally](https://img.shields.io/badge/runs-100%25%20locally-2ea44f)

</div>

Put two fingers on your forehead in a Teams call and vanish, Instant Transmission style. Your coworkers see a quick anime warp and then an empty room. Do it again and you're back, as if nothing happened.

It won't get you out of the meeting. It will make leaving it a lot more memorable.

## How it works

```
webcam ──► goku.py ──► OBS Virtual Camera ──► Teams
             │
             ├─ MediaPipe Hand Landmarker  → 21 points per hand (2D + 3D)
             ├─ MediaPipe BlazeFace        → where your forehead is
             ├─ MediaPipe Selfie Segmenter → you vs. the room (--bg mode only)
             └─ a few lines of geometry    → "is that the Goku pose?"
```

There's no custom ML here. Three pre-trained Google models run locally, and the gesture is plain geometry on top of them.

<img align="right" src="https://media.giphy.com/media/cW55zyF7dJAf6/giphy.gif" width="260" alt="Super Saiyan Goku doing Instant Transmission">

The reference pose is on the right. In geometry:

1. Index and middle finger straight (checked in 3D, so fingers pointing at the camera still count).
2. Ring finger and pinky folded.
3. Index and middle tips close together.
4. Tips somewhere on your forehead or temple.
5. All of the above held for 0.5 s.

Every distance is relative to your face width, so it works whether you're leaning in or slouching back.
<br clear="right">

Once it fires, it **locks** until you drop your hand. Holding the pose doesn't strobe you in and out of existence. A single dropped tracking frame doesn't reset the countdown either, because MediaPipe blinks sometimes.

The vanish itself takes 0.25 s: a horizontal wave warp, some white vertical streaks, and a fade to the background. While you're invisible the camera keeps watching, so the same gesture brings you back.

### Two ways to vanish

| Mode | What's behind you | What people see when you vanish |
|---|---|---|
| `goku.py 1` | your real room | your room, captured empty earlier (press **B**) |
| `goku.py 1 --bg` | a virtual background (image or looping video) | just the background |

In `--bg` mode the app cuts you out itself, which is why Teams' own background must be **off**. Two programs doing segmentation on top of each other just gives you a flickering ghost.

## Setup

You need Python 3.12 and OBS Studio. OBS is only there for its virtual camera: it doesn't have to be running.

**macOS**

```bash
brew install --cask obs
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Open OBS once and click **Start Virtual Camera**. macOS asks you to approve a camera extension (System Settings → General → Login Items & Extensions → Camera Extensions). Then give your terminal camera access in Privacy & Security → Camera.

**Windows**

```powershell
winget install OBSProject.OBSStudio
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

The OBS installer sets up the virtual camera, so there's nothing to approve.

**Both:** turn off any camera effects the OS adds on top (macOS Video Effects, Windows Studio Effects). macOS Reactions in particular read the Goku pose as a peace sign and throw balloons at you.

## Usage

```bash
python goku.py --cams                 # shows every camera with its number
python goku.py 1                      # real room mode, camera 1
python goku.py 1 --bg                 # virtual backgrounds from backgrounds/
python goku.py 1 --bg ~/Pictures/beach.jpg
```

Then in Teams: Settings → Devices → Camera → **OBS Virtual Camera**, background effects → **None**. Don't pick your real webcam in Teams too: on Windows only one app can use it at a time, and it has to be this one.

| Key | Does |
|---|---|
| gesture | vanish / come back |
| Space | same, for when your hands are busy |
| B | capture the empty room (5 s countdown, get out of the shot) |
| N | next background (`--bg` mode) |
| Q / red button / Ctrl+C | quit |

Add `--record demo` to also save `demo-clean.mp4` (what Teams sees) and `demo-debug.mp4` (with landmarks), for bragging purposes.

Keys only work when the "goku debug" window has focus. That window shows exactly what Teams gets, plus your hand landmarks, the forehead zone, a hold progress bar, and **why the gesture isn't firing** ("ring not folded", "not on forehead", ...). None of the overlay reaches Teams.

### Backgrounds

Drop images or `.mp4`/`.mov` files in `backgrounds/` (videos loop). They're sorted by name, so prefix them `1-`, `2-`... to pick the order. If you want to steal the ones Teams uses:

- macOS: `~/Library/Containers/com.microsoft.teams2/Data/Library/Application Support/Microsoft/MSTeams/Backgrounds/`
- Windows: `%LOCALAPPDATA%\Packages\MSTeams_8wekyb3d8bbwe\LocalCache\Microsoft\MSTeams\Backgrounds\`

The folder is git-ignored. Those images aren't mine to redistribute.

### Sound

On first run the app generates a `teleport.wav`: a rising zip with a puff of air. It's fine. If you have a better clip, save it as `teleport.mp3` or `teleport.m4a` next to `goku.py` and it wins. Those are git-ignored too, for the same copyright reason.

The sound plays on **your speakers**. Others hear it only if your mic picks it up. Routing it straight into the call needs a virtual audio device (BlackHole on macOS, VB-Cable on Windows), which I didn't set up.

## Credits

Hand, face and segmentation models: [Google MediaPipe](https://ai.google.dev/edge/mediapipe) (Apache 2.0). Virtual camera: [pyvirtualcam](https://github.com/letmaik/pyvirtualcam) + [OBS](https://obsproject.com). The GIFs are embedded from GIPHY and aren't stored in this repo; Dragon Ball belongs to Toei Animation and Bird Studio. The idea: Goku, who never once said goodbye before leaving.
