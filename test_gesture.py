import numpy as np

import tempfile, wave
from pathlib import Path

from goku import GestureArm, composite, effect, gesture_fail, is_goku, make_sound

# --- GestureArm: holding fires once, release + cooldown re-arms ---
arm = GestureArm()
fires = sum(arm.update(True, i / 30) for i in range(90))  # hold 3 s
assert fires == 1, fires
t = 3.0
assert not any(arm.update(False, t + i / 30) for i in range(5))  # brief release < 0.3 s
assert not any(arm.update(True, t + 0.2 + i / 30) for i in range(30))  # still locked
t = 4.5
for i in range(40):  # release 0.3 s + cooldown 0.5 s
    arm.update(False, t + i / 30)
assert sum(arm.update(True, 6.0 + i / 30) for i in range(30)) == 1

# --- grace: one dropped detection frame mid-hold doesn't reset it ---
arm = GestureArm()
seq = [True] * 8 + [False] + [True] * 10   # 0.63 s with a 1-frame gap
assert sum(arm.update(a, i / 30) for i, a in enumerate(seq)) == 1
arm = GestureArm()
seq = [True] * 8 + [False] * 9 + [True] * 10  # 0.3 s gap: hold restarts, too short to fire
assert sum(arm.update(a, i / 30) for i, a in enumerate(seq)) == 0

# --- is_goku: hand built around a face at x=200..300, y=100, eyes at y=150 ---
face = (200, 100, 100, 150)
pts = [(250, 300)] * 21                     # everything collapsed on the wrist = folded
pts[6], pts[8] = (245, 200), (245, 120)     # index extended, tip on forehead
pts[10], pts[12] = (260, 200), (262, 118)   # middle extended, close to index
pts[14], pts[16] = (270, 220), (268, 260)   # ring folded
pts[18], pts[20] = (280, 230), (278, 265)   # pinky folded
assert is_goku(pts, face)

far = list(pts); far[12] = (300, 118)                          # fingers apart
assert not is_goku(far, face)
ring_up = list(pts); ring_up[16] = (270, 110)                  # ring extended
assert not is_goku(ring_up, face)
low = [(x, y + 100) for x, y in pts]                           # touching the chin area
assert not is_goku(low, face)
high = [(x, y - 55) for x, y in pts]                           # tips at the hairline
assert is_goku(high, face)

# --- 3D: index pointing at the camera looks short in 2D but is straight in 3D ---
short = list(pts); short[8] = (245, 190)                       # 2D tip barely past PIP
short = [(x, y) for x, y in short]; short[12] = (247, 188)
assert gesture_fail(short, face) == "index not straight"
world = [(0, 0, 0)] * 21
world[6], world[8] = (0, -0.04, 0), (0, -0.05, -0.04)          # tip far away in depth
world[10], world[12] = (0.01, -0.04, 0), (0.01, -0.05, -0.04)
world[14], world[16] = (0.02, -0.04, 0), (0.02, -0.02, 0)      # ring folded
world[18], world[20] = (0.03, -0.035, 0), (0.03, -0.02, 0)     # pinky folded
short = [(x, y - 60) for x, y in short]                        # and on the forehead
assert gesture_fail(short, face, world) is None, gesture_fail(short, face, world)

# --- effect: endpoints are live and background ---
live = np.full((72, 128, 3), 50, np.uint8)
bg = np.full((72, 128, 3), 200, np.uint8)
assert np.array_equal(effect(live, bg, 0.0), live)
assert np.array_equal(effect(live, bg, 1.0), bg)

# --- composite: mask 1 = person, mask 0 = background image ---
person = np.zeros((36, 64, 1), np.float32); person[:, :32] = 1
c = composite(live, bg, person)
assert abs(int(c[36, 10, 0]) - 50) <= 1 and c[36, 120].tolist() == [200] * 3

# --- make_sound: valid wav ~0.35 s ---
with tempfile.TemporaryDirectory() as d:
    make_sound(Path(d) / "t.wav")
    with wave.open(str(Path(d) / "t.wav")) as w:
        assert abs(w.getnframes() / w.getframerate() - 0.35) < 0.01

print("ok")
