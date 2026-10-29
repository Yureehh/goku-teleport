"""Goku Teleport: two fingers on your forehead -> you vanish from Teams via OBS Virtual Camera.

Keys (debug window focused): B = capture background, Space = manual teleport, Q = quit.
"""
import math
import time
from pathlib import Path

import cv2
import numpy as np

# --- calibration knobs (all distances relative to face width) ---
HOLD_S = 0.5          # gesture must be held this long
RELEASE_S = 0.3       # hand must leave the gesture this long to re-arm
COOLDOWN_S = 0.5      # extra wait after re-arm
TIPS_TOGETHER = 0.35  # max distance index tip <-> middle tip
EXTENDED = 1.1        # tip farther from wrist than PIP by this factor
ZONE_SIDE = 0.2       # forehead zone extends this much beyond face box (temples)
ZONE_ABOVE = 0.3      # ...and this much above the face box top
EFFECT_S = 0.25       # vanish/appear animation length
DETECT_W = 640        # MediaPipe runs on frames this wide
BG_FRAMES = 30        # frames for the background median
BG_COUNTDOWN_S = 5

MODELS = Path(__file__).parent / "models"
WRIST, INDEX_PIP, INDEX_TIP, MIDDLE_PIP, MIDDLE_TIP = 0, 6, 8, 10, 12
RING_PIP, RING_TIP, PINKY_PIP, PINKY_TIP = 14, 16, 18, 20


def is_goku(pts, face):
    """pts: 21 (x, y) hand landmarks in pixels. face: (x, y, w, eye_y) in pixels."""
    fx, fy, fw, eye_y = face
    d = lambda a, b: math.dist(pts[a], pts[b])
    extended = lambda tip, pip: d(WRIST, tip) > d(WRIST, pip) * EXTENDED
    folded = lambda tip, pip: d(WRIST, tip) < d(WRIST, pip)
    if not (extended(INDEX_TIP, INDEX_PIP) and extended(MIDDLE_TIP, MIDDLE_PIP)):
        return False
    if not (folded(RING_TIP, RING_PIP) and folded(PINKY_TIP, PINKY_PIP)):
        return False
    if d(INDEX_TIP, MIDDLE_TIP) > TIPS_TOGETHER * fw:
        return False
    tx = (pts[INDEX_TIP][0] + pts[MIDDLE_TIP][0]) / 2
    ty = (pts[INDEX_TIP][1] + pts[MIDDLE_TIP][1]) / 2
    return (fx - ZONE_SIDE * fw <= tx <= fx + fw + ZONE_SIDE * fw
            and fy - ZONE_ABOVE * fw <= ty <= eye_y)


class GestureArm:
    """Fires once per gesture: hold -> fire -> lock until released for RELEASE_S -> cooldown."""

    def __init__(self):
        self.since = None
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
        # ponytail: one missed detection frame resets the hold; add a grace window if it flickers
        if not active or now < self.ready_at:
            self.since = None
            return False
        if self.since is None:
            self.since = now
        if now - self.since >= HOLD_S:
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
    wave = (math.sin(math.pi * t) * 60 * np.sin(gy / 9 + t * 25)).astype(np.float32)
    warped = cv2.remap(live, gx + wave, gy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    out = cv2.addWeighted(warped, 1 - t, bg, t, 0)
    # ponytail: distorts the whole frame; mask the person (|live - bg|) if the room wobble bothers you
    streaks = np.zeros(w, np.float32)
    rng = np.random.default_rng(int(t * 1000))
    for x in rng.integers(0, w, 25):
        streaks[x:x + rng.integers(2, 10)] = rng.uniform(0.4, 1.0)
    s = (streaks * math.sin(math.pi * t))[None, :, None]
    return (out * (1 - s) + 255 * s).astype(np.uint8)


def main():
    import mediapipe as mp
    import pyvirtualcam
    from mediapipe.tasks.python import BaseOptions, vision

    video = vision.RunningMode.VIDEO
    hands = vision.HandLandmarker.create_from_options(vision.HandLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=str(MODELS / "hand_landmarker.task")),
        running_mode=video, num_hands=2))
    faces = vision.FaceDetector.create_from_options(vision.FaceDetectorOptions(
        base_options=BaseOptions(model_asset_path=str(MODELS / "blaze_face_short_range.tflite")),
        running_mode=video))

    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    cap.set(cv2.CAP_PROP_FPS, 30)
    ok, frame = cap.read()
    if not ok:
        raise SystemExit("No webcam frame: check camera permission for your terminal.")
    H, W = frame.shape[:2]
    try:
        cam = pyvirtualcam.Camera(W, H, 30, fmt=pyvirtualcam.PixelFormat.BGR)
        print(f"Sending {W}x{H} to {cam.device}")
    except RuntimeError as e:
        cam = None
        print(f"No virtual camera ({e}). Running debug window only.")

    arm = GestureArm()
    bg = None
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
            face = (b.origin_x, b.origin_y, b.width, eye_y)  # ponytail: keeps last face when hand hides it
        hand_pts = [[(l.x * DETECT_W, l.y * dh) for l in hl] for hl in hands.detect_for_video(img, ts).hand_landmarks]
        active = face is not None and any(is_goku(p, face) for p in hand_pts)

        fire = arm.update(active, now)
        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break
        if key == ord("b"):
            bg_at, samples = now + BG_COUNTDOWN_S, []
        if (fire or key == ord(" ")) and bg is not None and state in ("VISIBLE", "INVISIBLE"):
            state, t0 = ("VANISHING" if state == "VISIBLE" else "APPEARING"), now

        # output frame
        t = min(1.0, (now - t0) / EFFECT_S)
        if state == "VANISHING":
            out = effect(frame, bg, t)
            if t >= 1:
                state = "INVISIBLE"
        elif state == "APPEARING":
            out = effect(frame, bg, 1 - t)
            if t >= 1:
                state = "VISIBLE"
        elif state == "INVISIBLE":
            out = bg
        else:
            out = frame
        if cam:
            cam.send(out)

        # debug window (never sent to Teams)
        dbg = small.copy()
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
        cv2.imshow("goku debug", dbg)

    cap.release()
    if cam:
        cam.close()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
