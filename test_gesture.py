import numpy as np

from goku import GestureArm, effect, is_goku

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

# --- effect: endpoints are live and background ---
live = np.full((72, 128, 3), 50, np.uint8)
bg = np.full((72, 128, 3), 200, np.uint8)
assert np.array_equal(effect(live, bg, 0.0), live)
assert np.array_equal(effect(live, bg, 1.0), bg)

print("ok")
