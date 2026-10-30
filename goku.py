"""Sorry, They Need Me: two fingers on your forehead -> you vanish from Teams via OBS Virtual Camera.

Usage: python goku.py --cams              (shows every camera with its number)
       python goku.py N                   (uses camera N, default 0; B captures the empty room)
       python goku.py N --bg image.png    (replaces the background with an image, like Teams does)
       python goku.py N --bg              (uses the backgrounds/ pool; N key = next)
Keys (debug window focused): B = capture background, Space = manual teleport, N = next background, Q = quit.
Sound: plays teleport.mp3/.m4a if present, else teleport.wav (generated on first run).
"""
import argparse
import contextlib
import math
import os
import shutil
import subprocess
import sys
import time
import wave
from pathlib import Path

import cv2
import numpy as np

# --- calibration knobs (all distances relative to face width) ---
HOLD_S = 0.5          # gesture must be held this long
RELEASE_S = 0.3       # hand must leave the gesture this long to re-arm
COOLDOWN_S = 0.5      # extra wait after re-arm
TIPS_TOGETHER = 0.35  # max distance index tip <-> middle tip
EXTENDED = 1.1        # tip farther from wrist than PIP by this factor
ZONE_SIDE = 0.3       # forehead zone extends this much beyond face box (temples)
ZONE_ABOVE = 0.7      # ...and this much above the face box top (BlazeFace's box starts near the eyebrows)
GRACE_S = 0.15        # a gesture lost for less than this still counts (detection flicker)
MIN_CONF = 0.3        # MediaPipe confidence: lower = keeps tracking a hand that covers the face
EFFECT_S = 0.25       # vanish/appear animation length
DETECT_W = 640        # MediaPipe runs on frames this wide
BG_FRAMES = 30        # frames for the background median
BG_COUNTDOWN_S = 5

MODELS = Path(__file__).parent / "models"
SOUND = Path(__file__).parent / "teleport.wav"
WRIST, INDEX_PIP, INDEX_TIP, MIDDLE_PIP, MIDDLE_TIP = 0, 6, 8, 10, 12
RING_PIP, RING_TIP, PINKY_PIP, PINKY_TIP = 14, 16, 18, 20


def gesture_fail(pts, face, world=None):
    """Why this hand is NOT the Goku gesture, or None if it is.
    pts: 21 (x, y) landmarks in pixels. face: (x, y, w, eye_y) in pixels.
    world: 21 (x, y, z) landmarks in meters; finger shape uses them so fingers
    pointing toward the camera aren't foreshortened into "folded"."""
    fx, fy, fw, eye_y = face
    shape = world or pts
    d = lambda a, b: math.dist(shape[a], shape[b])
    extended = lambda tip, pip: d(WRIST, tip) > d(WRIST, pip) * EXTENDED
    folded = lambda tip, pip: d(WRIST, tip) < d(WRIST, pip)
    if not extended(INDEX_TIP, INDEX_PIP):
        return "index not straight"
    if not extended(MIDDLE_TIP, MIDDLE_PIP):
        return "middle not straight"
    if not folded(RING_TIP, RING_PIP):
        return "ring not folded"
    if not folded(PINKY_TIP, PINKY_PIP):
        return "pinky not folded"
    if math.dist(pts[INDEX_TIP], pts[MIDDLE_TIP]) > TIPS_TOGETHER * fw:
        return "fingers apart"
    tx = (pts[INDEX_TIP][0] + pts[MIDDLE_TIP][0]) / 2
    ty = (pts[INDEX_TIP][1] + pts[MIDDLE_TIP][1]) / 2
    if not (fx - ZONE_SIDE * fw <= tx <= fx + fw + ZONE_SIDE * fw and fy - ZONE_ABOVE * fw <= ty <= eye_y):
        return "not on forehead"
    return None


def is_goku(pts, face, world=None):
    return gesture_fail(pts, face, world) is None


class GestureArm:
    """Fires once per gesture: hold -> fire -> lock until released for RELEASE_S -> cooldown."""

    def __init__(self):
        self.since = None
        self.last_seen = 0.0
        self.released_since = None
        self.locked = False
        self.ready_at = 0.0

    def update(self, active, now):
        if self.locked:
            if active:
                self.released_since = None
            elif self.released_since is None:
                self.released_since = now
            elif now - self.released_since >= RELEASE_S:
                self.locked, self.ready_at = False, now + COOLDOWN_S
            return False
        if now < self.ready_at:
            self.since = None
            return False
        if active:
            self.last_seen = now
            if self.since is None:
                self.since = now
        elif self.since is not None and now - self.last_seen > GRACE_S:
            self.since = None
        if self.since is not None and now - self.since >= HOLD_S:
            self.locked, self.since, self.released_since = True, None, None
            return True
        return False

    def progress(self, now):
        return 0.0 if self.since is None else min(1.0, (now - self.since) / HOLD_S)


_grid = {}


def effect(live, bg, t):
    """t=0 fully live, t=1 fully background. Wavy distortion + anime streaks + blend."""
    h, w = live.shape[:2]
    if (h, w) not in _grid:
        _grid[(h, w)] = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))
    gx, gy = _grid[(h, w)]
    wave = (math.sin(math.pi * t) * 40 * np.sin(gy / 12 + t * 6)).astype(np.float32)
    warped = cv2.remap(live, gx + wave, gy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    a = t * t * (3 - 2 * t)  # smoothstep: no hard jump at start/end of the blend
    out = cv2.addWeighted(warped, 1 - a, bg, a, 0)
    # Warps the whole frame, room included. Masking it to just the person would look nicer.
    # streaks fixed per run (not per frame), so they glow in and out instead of strobing
    streaks = np.zeros(w, np.float32)
    rng = np.random.default_rng(7)
    for x in rng.integers(0, w, 25):
        streaks[x:x + rng.integers(2, 10)] = rng.uniform(0.3, 0.8)
    s = (streaks * math.sin(math.pi * t))[None, :, None]
    return (out * (1 - s) + 255 * s).astype(np.uint8)


def composite(frame, bg, person):
    """person: 0..1 float mask at any size. Returns the person over bg, soft edges."""
    m = cv2.resize(np.squeeze(person), frame.shape[1::-1])
    m = cv2.GaussianBlur(m, (15, 15), 0)[..., None]
    return (frame * m + bg * (1 - m)).astype(np.uint8)


def make_sound(path):
    """Original anime-style 'shunk': rising zip + air burst, ~0.35 s."""
    sr, dur = 44100, 0.35
    t = np.linspace(0, dur, int(sr * dur), endpoint=False)
    zip_ = np.sin(2 * np.pi * np.cumsum(400 + 3600 * (t / dur) ** 2) / sr)
    air = np.random.default_rng(0).uniform(-1, 1, t.size) * np.exp(-t * 30)
    x = 0.6 * zip_ * np.minimum(1, t * 200) * np.exp(-t * 9) + 0.4 * air
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((x * 0.8 * 32767).astype(np.int16).tobytes())


def play_sound():
    """Plays on your speakers; the call hears it only if your mic picks it up."""
    own = [f for f in (SOUND.with_suffix(e) for e in (".mp3", ".m4a")) if f.exists()]
    path = own[0] if own else SOUND  # your own clip wins over the generated one
    if sys.platform == "darwin":
        subprocess.Popen(["afplay", str(path)])
    elif sys.platform == "win32":
        import ctypes  # MCI ships with Windows and plays both wav and mp3, no installs
        mci = ctypes.windll.winmm.mciSendStringW
        mci("close teleport", None, 0, None)
        mci(f'open "{path}" type mpegvideo alias teleport', None, 0, None)
        mci("play teleport", None, 0, None)
    elif shutil.which("paplay"):
        subprocess.Popen(["paplay", str(path)])


CAM_HELP = ("Check that the app running Python has camera access (macOS: Privacy & Security -> Camera; "
                   "Windows: Settings -> Privacy -> Camera) and that nothing else is using the camera.")
BG_EXT = {".png", ".jpg", ".jpeg", ".mp4", ".mov"}


def load_bg(path, size):
    """Returns a function giving the next background frame; videos loop."""
    if path.suffix.lower() in (".mp4", ".mov"):
        cap = cv2.VideoCapture(str(path))

        def next_frame():
            ok, f = cap.read()
            if not ok:
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ok, f = cap.read()
            return cv2.resize(f, size)  # one video frame per camera frame, so speed follows our fps
        if not cap.isOpened():
            raise SystemExit(f"Can't open background video: {path}")
        return next_frame
    pic = cv2.imread(str(path))
    if pic is None:
        raise SystemExit(f"Can't read background image: {path}")
    pic = cv2.resize(pic, size)  # non-16:9 images get stretched
    return lambda: pic


@contextlib.contextmanager
def quiet_stderr():
    """MediaPipe's C++ logs ignore env vars; mute fd 2 while models load."""
    saved, null = os.dup(2), os.open(os.devnull, os.O_WRONLY)
    os.dup2(null, 2)
    os.close(null)
    try:
        yield
    finally:
        os.dup2(saved, 2)
        os.close(saved)


def window_closed(name):
    try:
        return cv2.getWindowProperty(name, cv2.WND_PROP_VISIBLE) < 1
    except cv2.error:  # Cocoa destroys the window on the red button
        return True


def open_camera(index):
    if sys.platform != "win32":
        return cv2.VideoCapture(index)
    # The default Windows backend (MSMF) can take 10+ s to open; DirectShow is instant.
    # MJPG because most USB webcams only do 720p at 30 fps compressed.
    cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    return cap


def show_cams():
    shots = []
    for i in range(5):
        cap = open_camera(i)
        ok, f = cap.read()
        cap.release()
        if ok:
            f = cv2.resize(f, (426, 240))
            cv2.putText(f, f"camera {i}", (10, 35), 0, 1.2, (0, 255, 0), 3)
            shots.append(f)
    if not shots:
        raise SystemExit("No cameras readable. " + CAM_HELP)
    name = "pick a camera, then: python goku.py N   (any key closes)"
    cv2.imshow(name, np.hstack(shots))
    while cv2.waitKey(100) == -1 and not window_closed(name):
        pass


def main(camera, bg_image, record=None):
    import mediapipe as mp
    import pyvirtualcam
    from mediapipe.tasks.python import BaseOptions, vision

    if not SOUND.exists():
        make_sound(SOUND)
    video = vision.RunningMode.VIDEO
    print("Loading models...")
    with quiet_stderr():
        segmenter = bg_image and vision.ImageSegmenter.create_from_options(vision.ImageSegmenterOptions(
            base_options=BaseOptions(model_asset_path=str(MODELS / "selfie_segmenter.tflite")),
            running_mode=video, output_confidence_masks=True))
        hands = vision.HandLandmarker.create_from_options(vision.HandLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=str(MODELS / "hand_landmarker.task")),
            running_mode=video, num_hands=2, min_hand_detection_confidence=MIN_CONF,
            min_hand_presence_confidence=MIN_CONF, min_tracking_confidence=MIN_CONF))
        faces = vision.FaceDetector.create_from_options(vision.FaceDetectorOptions(
            base_options=BaseOptions(model_asset_path=str(MODELS / "blaze_face_short_range.tflite")),
            running_mode=video, min_detection_confidence=MIN_CONF))

    cap = open_camera(camera)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    cap.set(cv2.CAP_PROP_FPS, 30)
    ok, frame = cap.read()
    if not ok:
        raise SystemExit(f"Camera {camera} gave no picture. " + CAM_HELP)
    H, W = frame.shape[:2]
    try:
        cam = pyvirtualcam.Camera(W, H, 30, fmt=pyvirtualcam.PixelFormat.BGR)
        print(f"Sending {W}x{H} to {cam.device}")
    except RuntimeError as e:
        cam = None
        print(f"No virtual camera ({e}). Running debug window only.")

    rec = None
    if record:  # written at a nominal 20 fps; the real rate is printed on exit
        mp4 = cv2.VideoWriter_fourcc(*"mp4v")
        rec = [cv2.VideoWriter(f"{record}-clean.mp4", mp4, 20, (W, H)),
               cv2.VideoWriter(f"{record}-debug.mp4", mp4, 20, (DETECT_W, DETECT_W * H // W))]
        rec_n, rec_t = 0, time.monotonic()
        print(f"Recording to {record}-clean.mp4 / {record}-debug.mp4: quit with Q or the red button to save")

    arm = GestureArm()
    bg = None
    pool, pick, next_bg = [], 0, None
    if bg_image:
        p = Path(bg_image)
        pool = sorted(f for f in p.iterdir() if f.suffix.lower() in BG_EXT) if p.is_dir() else [p]
        if not pool:
            raise SystemExit(f"No images or videos in {p}")
        next_bg = load_bg(pool[0], (W, H))
        print(f"Background: {pool[0].name}" + (f"  (N = next, {len(pool)} in pool)" if len(pool) > 1 else ""))
    bg_at, samples = None, []
    state, t0 = "VISIBLE", 0.0
    face = None
    start = time.monotonic()
    last_ts = -1
    fps, last = 0.0, start

    while True:
        ok, frame = cap.read()
        if not ok:
            break
        now = time.monotonic()
        fps, last = 0.9 * fps + 0.1 / max(now - last, 1e-6), now

        # background capture (you should be out of frame by now)
        if bg_at is not None and now >= bg_at:
            samples.append(frame)
            if len(samples) >= BG_FRAMES:
                bg = np.median(np.stack(samples), axis=0).astype(np.uint8)
                bg_at, samples = None, []

        # detection on a downscaled frame
        dh = DETECT_W * H // W
        small = cv2.resize(frame, (DETECT_W, dh))
        ts = max(int((now - start) * 1000), last_ts + 1)
        last_ts = ts
        img = mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(small, cv2.COLOR_BGR2RGB))
        det = faces.detect_for_video(img, ts).detections
        if det:
            b = max(det, key=lambda d: d.bounding_box.width).bounding_box
            kp = max(det, key=lambda d: d.bounding_box.width).keypoints
            eye_y = (kp[0].y + kp[1].y) / 2 * dh
            face = (b.origin_x, b.origin_y, b.width, eye_y)  # kept when the hand hides the face
        hr = hands.detect_for_video(img, ts)
        hand_pts = [[(l.x * DETECT_W, l.y * dh) for l in hl] for hl in hr.hand_landmarks]
        hand_3d = [[(l.x, l.y, l.z) for l in hl] for hl in hr.hand_world_landmarks]
        fails = [gesture_fail(p, face, w) for p, w in zip(hand_pts, hand_3d)] if face else []
        active = None in fails
        why = "GOKU!" if active else (fails[0] if fails else ("no face" if face is None else "no hand"))
        live = frame
        if segmenter:
            bg = next_bg()
            live = composite(frame, bg, segmenter.segment_for_video(img, ts).confidence_masks[0].numpy_view())

        fire = arm.update(active, now)
        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break
        if key == ord("n") and len(pool) > 1:
            pick = (pick + 1) % len(pool)
            next_bg = load_bg(pool[pick], (W, H))
            print(f"Background: {pool[pick].name}")
        if key == ord("b") and not segmenter:
            bg_at, samples = now + BG_COUNTDOWN_S, []
        if (fire or key == ord(" ")) and bg is not None and state in ("VISIBLE", "INVISIBLE"):
            state, t0 = ("VANISHING" if state == "VISIBLE" else "APPEARING"), now
            play_sound()
            print(f"{now - start:7.1f}s {state} ({'gesture' if fire else 'key'})")
        elif (fire or key == ord(" ")) and bg is None:
            print("Gesture recognised, but there's no background yet: press B and leave the frame.")

        # output frame
        t = min(1.0, (now - t0) / EFFECT_S)
        if state == "VANISHING":
            out = effect(live, bg, t)
            if t >= 1:
                state = "INVISIBLE"
        elif state == "APPEARING":
            out = effect(live, bg, 1 - t)
            if t >= 1:
                state = "VISIBLE"
        elif state == "INVISIBLE":
            out = bg
        else:
            out = live
        if cam:
            cam.send(out)

        # debug window (never sent to Teams)
        dbg = cv2.resize(out, (DETECT_W, dh))  # what Teams sees, plus overlays
        for p in hand_pts:
            for x, y in p:
                cv2.circle(dbg, (int(x), int(y)), 3, (0, 255, 0) if active else (0, 200, 255), -1)
        if face:
            fx, fy, fw, ey = face
            cv2.rectangle(dbg, (int(fx - ZONE_SIDE * fw), int(fy - ZONE_ABOVE * fw)),
                          (int(fx + fw + ZONE_SIDE * fw), int(ey)), (255, 0, 255), 1)
        dbg = cv2.flip(dbg, 1)
        if bg_at is not None:
            left = bg_at - now
            msg = f"Leave the frame! {left:.1f}s" if left > 0 else f"Capturing {len(samples)}/{BG_FRAMES}"
        else:
            msg = "B: capture background" if bg is None else "Space / gesture: teleport"
        cv2.putText(dbg, f"{state}  {fps:.0f} fps  {'cam' if cam else 'NO CAM'}", (10, 25), 0, 0.6, (255, 255, 255), 2)
        cv2.putText(dbg, msg, (10, 50), 0, 0.6, (255, 255, 255), 2)
        cv2.rectangle(dbg, (10, dh - 20), (10 + int(200 * arm.progress(now)), dh - 10), (0, 255, 0), -1)
        cv2.putText(dbg, why, (220, dh - 10), 0, 0.6, (0, 255, 0) if active else (0, 200, 255), 2)
        cv2.imshow("goku debug", dbg)
        if rec:
            rec[0].write(out)
            rec[1].write(dbg)
            rec_n += 1
        if window_closed("goku debug"):  # red button
            break

    if rec:
        for r in rec:
            r.release()
        secs = time.monotonic() - rec_t
        print(f"Saved {rec_n} frames over {secs:.1f} s ({rec_n / secs:.1f} fps real)")
    cap.release()
    if cam:
        cam.close()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("camera", nargs="?", type=int, default=0)
    ap.add_argument("--cams", action="store_true", help="show every camera with its number")
    ap.add_argument("--bg", nargs="?", const=str(Path(__file__).parent / "backgrounds"),
                    help="background image/video, or a folder (default: backgrounds/); N cycles")
    ap.add_argument("--record", metavar="NAME", help="also save NAME-clean.mp4 (what Teams sees) and NAME-debug.mp4")
    args = ap.parse_args()
    if args.cams:
        show_cams()
    else:
        try:
            main(args.camera, args.bg, args.record)
        except KeyboardInterrupt:
            os._exit(0)  # Ctrl+C: skip MediaPipe's slow cleanup; the OS releases the cameras
