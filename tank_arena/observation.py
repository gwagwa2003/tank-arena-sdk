"""The 91 numbers a model sees each step (docs/observation.md has the full table).

The server builds exactly this observation from the game state, so a model trained on it behaves the same on the ladder.
"""
import math

import numpy as np

from .geometry import clearance, view_of, visible_enemies, wrap
from .rules import CHASSIS, MODULES, STEPS

OBS_SIZE = 91


def observation(state):
    """state: what the engine hands a policy each step (see engine.Game.state). Returns float32[91]."""
    s = state["self"]; zone = state["zone"]
    x, y, h = s["x"], s["y"], s["heading"]
    cs, sn = math.cos(h), math.sin(h)
    obs = np.zeros(OBS_SIZE, dtype=np.float32)

    # 0-31: terrain rays every 11.25 degrees, starting straight ahead and turning right, scaled by 320 (430 with radar)
    reach = 430 if s.get("module") == "radar" else 320
    for i in range(32):
        obs[i] = min(1.0, clearance(x, y, h + i * math.pi / 16, state["walls"]) / reach)

    # 32-55: up to 4 visible enemies, nearest first: seen, distance / view, angle (sin, cos), velocity in my frame / 6
    view = view_of(s.get("module"))
    for i, e in enumerate(visible_enemies(state)[:4]):
        dx, dy = e["x"] - x, e["y"] - y
        a = wrap(math.atan2(dy, dx) - h)
        obs[32 + 6 * i:38 + 6 * i] = [1, math.hypot(dx, dy) / view, math.sin(a), math.cos(a),
                                      (e["vx"] * cs + e["vy"] * sn) / 6, (-e["vx"] * sn + e["vy"] * cs) / 6]

    # 56-75: up to 4 enemy bullets within 250 px, nearest first: present, distance / 250, angle (sin, cos), closing speed / 14
    d2 = lambda b: (b["x"] - x) ** 2 + (b["y"] - y) ** 2
    near = sorted((b for b in state["bullets"] if not b.get("own") and d2(b) < 250 ** 2), key=d2)[:4]
    for i, b in enumerate(near):
        dx, dy = b["x"] - x, b["y"] - y
        d = math.hypot(dx, dy); a = wrap(math.atan2(dy, dx) - h)
        closing = -(dx * b["vx"] + dy * b["vy"]) / max(d, 1e-6)
        obs[56 + 5 * i:61 + 5 * i] = [1, d / 250, math.sin(a), math.cos(a), closing / 14]

    # 76-90: myself, the zone, the clock, the skill
    speed, _, reload, _, _, _ = CHASSIS[s["chassis"]]
    vx, vy = s.get("vx", 0.0), s.get("vy", 0.0)
    ta = wrap(s["turret"] - h)
    zx, zy = zone["x"] - x, zone["y"] - y
    zd = math.hypot(zx, zy); za = wrap(math.atan2(zy, zx) - h)
    alive_enemies = sum(1 for e in state["enemies"] if e["alive"])
    obs[76:89] = [s["hp_frac"], min(1.0, s["cooldown"] / reload),
                  (vx * cs + vy * sn) / (speed * 2), (-vx * sn + vy * cs) / (speed * 2),
                  math.sin(ta), math.cos(ta), math.sin(za), math.cos(za), zd / 800,
                  max(-1, min(1, (zone["r"] - zd) / 620)), max(0, min(1, (620 - zone["r"]) / 530)),
                  state["t"] / STEPS, alive_enemies / 4]
    m = s.get("module")
    obs[89] = s["skill_cd"] / MODULES[m][1] if m in MODULES else 0
    obs[90] = float(s["skill_active"])
    return obs
