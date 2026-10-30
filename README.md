<div align="center">

# Goku Teleport

**Leave Teams meetings the way Goku leaves job interviews.**

<a href="https://giphy.com/gifs/goku-VIZi1DWTuZUcw"><img src="https://media.giphy.com/media/VIZi1DWTuZUcw/giphy.gif" width="520" alt="Goku in a suit teleporting out of a job interview"></a>

![Python](https://img.shields.io/badge/python-3.12-3776AB?logo=python&logoColor=white)
![MediaPipe](https://img.shields.io/badge/MediaPipe-hands%20%2B%20face%20%2B%20segmentation-0097A7?logo=google&logoColor=white)
![macOS](https://img.shields.io/badge/macOS-OBS%20Virtual%20Camera-000000?logo=apple&logoColor=white)
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

## Setup (macOS)

```bash
brew install --cask obs
python3.12 -m venv .venv
.venv/bin/pip install opencv-python mediapipe pyvirtualcam numpy
```

1. Open OBS once and click **Start Virtual Camera**. macOS will ask you to approve a camera extension (System Settings → General → Login Items & Extensions → Camera Extensions). After that you can close OBS forever; the app talks to the virtual camera directly.
2. Give your terminal camera access: System Settings → Privacy & Security → Camera.
3. Models are already in `models/`. Nothing to download.

## Usage

```bash
.venv/bin/python goku.py --cams     # shows every camera with its number
.venv/bin/python goku.py 1          # real room mode, camera 1
.venv/bin/python goku.py 1 --bg     # virtual backgrounds from backgrounds/
.venv/bin/python goku.py 1 --bg ~/Pictures/beach.jpg
```

Then in Teams: Settings → Devices → Camera → **OBS Virtual Camera**, background effects → **None**.

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

Drop images or `.mp4`/`.mov` files in `backgrounds/` (videos loop). They're sorted by name, so prefix them `1-`, `2-`... to pick the order. Teams keeps its built-in ones here if you want to steal them:

```
~/Library/Containers/com.microsoft.teams2/Data/Library/Application Support/Microsoft/MSTeams/Backgrounds/
```

The folder is git-ignored. Those images aren't mine to redistribute.

### Sound

On first run the app generates a `teleport.wav`: a rising zip with a puff of air. It's fine. If you have a better clip, save it as `teleport.mp3` or `teleport.m4a` next to `goku.py` and it wins. Those are git-ignored too, for the same copyright reason.

The sound plays on **your speakers**. Others hear it only if your mic picks it up. Routing it straight into the call needs a virtual audio device like BlackHole, which I didn't set up.

## Troubleshooting

- **The app opened my iPhone camera.** That's Continuity Camera grabbing index 0. Run `--cams`, then pass the right number.
- **Balloons and fireworks appear when I do the gesture.** macOS Reactions think your two fingers are a peace sign. Menu bar camera icon → Video Effects → turn off Reactions (and Center Stage, Portrait, Background while you're there).
- **Flickering in Teams.** Teams background effects are on. Turn them off.
- **"No webcam frame: check camera permission".** Whatever app launched Python needs camera access. Running it from an IDE or another app's terminal means *that* app needs the permission.
- **The gesture won't fire.** Look at the debug window's bottom line and adjust the matching knob at the top of `goku.py` (`ZONE_ABOVE`, `TIPS_TOGETHER`, `HOLD_S`, ...).
- **When I vanish, the room comes out slightly brighter or darker than the live feed.** The camera's auto-exposure drifted since you pressed B. Press B again.

## Tests

```bash
.venv/bin/python test_gesture.py
```

These are plain asserts, with no framework. They check that holding fires exactly once, that release re-arms, that a dropped frame doesn't reset the hold, that the geometry accepts the pose and rejects near-misses, and that the effect starts and ends on the right frames.

## Credits

Hand, face and segmentation models: [Google MediaPipe](https://ai.google.dev/edge/mediapipe) (Apache 2.0). Virtual camera: [pyvirtualcam](https://github.com/letmaik/pyvirtualcam) + [OBS](https://obsproject.com). The GIFs are embedded from GIPHY and aren't stored in this repo; Dragon Ball belongs to Toei Animation and Bird Studio. The idea: Goku, who never once said goodbye before leaving.
