"""The 118 numbers a model sees each step under v3_final (docs/observation.md has the full table)."""
import math

import numpy as np

from .geometry import BASE_VIEW, RAY_REACH_BASE, RAY_REACH_RADAR, clearance, line_of_sight, ray_rect, view_of, visible_enemies, wrap
from .rules import (
    ARENA,
    BULLET_OBS_RANGE,
    BUSH_FIRE_REVEAL_STEPS,
    BUSHES_ENABLED,
    CHASSIS,
    CORE_CAPTURE_STEPS,
    CORE_RADIUS,
    CORE_SPAWN_1,
    CORE_SPAWN_2,
    CORE_WARN_STEPS,
    HIDE_ENEMY_VEL,
    MODULES,
    POWER_CORE_ENABLED,
    SHIELD_ABSORB,
    SOUND_CUES_ENABLED,
    SOUND_DECAY_STEPS,
    STEPS,
    ZONE_R_END,
    ZONE_R_START,
    rect_alive,
)

OBS_SIZE = 118


def observation(state):
    """Build the 118-dim float32 observation vector matching the Tank Arena v3_final server."""
    s = state["self"]
    zone = state["zone"]
    x, y, h = s["x"], s["y"], s["heading"]
    cs, sn = math.cos(h), math.sin(h)
    obs = np.zeros(OBS_SIZE, dtype=np.float32)

    # 0..31: terrain rays every 11.25 deg
    reach = RAY_REACH_RADAR if s.get("module") == "radar" else RAY_REACH_BASE
    for i in range(32):
        obs[i] = min(1.0, clearance(x, y, h + i * math.pi / 16.0, state["walls"]) / reach)

    # 32..55: up to 4 visible enemies (enemy velocity hidden under HIDE_ENEMY_VEL)
    view = view_of(s["chassis"], s.get("module"))
    vis = visible_enemies(state)
    for i, e in enumerate(vis[:4]):
        dx, dy = e["x"] - x, e["y"] - y
        a = wrap(math.atan2(dy, dx) - h)
        evx = 0.0 if HIDE_ENEMY_VEL else (e["vx"] * cs + e["vy"] * sn) / 6.0
        evy = 0.0 if HIDE_ENEMY_VEL else (-e["vx"] * sn + e["vy"] * cs) / 6.0
        obs[32 + 6 * i : 38 + 6 * i] = [1.0, math.hypot(dx, dy) / view, math.sin(a), math.cos(a), evx, evy]

    # 56..75: up to 4 enemy bullets within BULLET_OBS_RANGE
    d2 = lambda b: (b["x"] - x) ** 2 + (b["y"] - y) ** 2
    near = sorted((b for b in state["bullets"] if not b.get("own") and d2(b) < BULLET_OBS_RANGE ** 2), key=d2)[:4]
    for i, b in enumerate(near):
        dx, dy = b["x"] - x, b["y"] - y
        d = math.hypot(dx, dy)
        a = wrap(math.atan2(dy, dx) - h)
        closing = -(dx * b["vx"] + dy * b["vy"]) / max(d, 1e-6)
        obs[56 + 5 * i : 61 + 5 * i] = [1.0, d / BULLET_OBS_RANGE, math.sin(a), math.cos(a), closing / 14.0]

    # 76..90: self, zone, clock, skill
    speed, _, reload, _, _, _ = CHASSIS[s["chassis"]]
    vx, vy = s.get("vx", 0.0), s.get("vy", 0.0)
    ta = wrap(s["turret"] - h)
    zx, zy = zone["x"] - x, zone["y"] - y
    zd = math.hypot(zx, zy)
    za = wrap(math.atan2(zy, zx) - h)
    alive_enemies = sum(1 for e in state["enemies"] if e["alive"])
    obs[76:89] = [
        s["hp_frac"],
        min(1.0, s["cooldown"] / reload),
        (vx * cs + vy * sn) / (speed * 2.0),
        (-vx * sn + vy * cs) / (speed * 2.0),
        math.sin(ta),
        math.cos(ta),
        math.sin(za),
        math.cos(za),
        zd / ARENA,
        max(-1.0, min(1.0, (zone["r"] - zd) / ZONE_R_START)),
        max(0.0, min(1.0, (ZONE_R_START - zone["r"]) / (ZONE_R_START - ZONE_R_END))),
        state["t"] / STEPS,
        alive_enemies / 4.0,
    ]
    m = s.get("module")
    m_spec = MODULES.get(m)
    obs[89] = s["skill_cd"] / m_spec[1] if m_spec and m_spec[1] > 0 else 0.0
    obs[90] = float(s["skill_active"])

    # 91..95: heat, overheat lock, shield fraction, visible enemy heading
    obs[91] = s.get("heat", 0.0) / 100.0
    obs[92] = 1.0 if s.get("overheat_t", 0) > 0 else 0.0
    sh_val = float(s.get("shield", 0.0))
    obs[93] = sh_val / SHIELD_ABSORB if SHIELD_ABSORB > 0.0 else (1.0 if sh_val > 0.0 else 0.0)
    if vis:
        eh_rel = wrap(vis[0]["heading"] - h)
        obs[94] = math.sin(eh_rel)
        obs[95] = math.cos(eh_rel)

    # 96..99: sound cues
    decay = max(1, SOUND_DECAY_STEPS)
    s_age = s.get("sound_age", 999)
    if SOUND_CUES_ENABLED and s_age < decay:
        sa = wrap(s.get("sound_ang", 0.0) - h)
        s_type = s.get("sound_type", 0)
        obs[96] = max(0.0, 1.0 - s_age / decay)
        obs[97] = math.sin(sa)
        obs[98] = math.cos(sa)
        obs[99] = 0.5 if s_type == 1 else (1.0 if s_type == 2 else 0.0)

    # 100..105: power core state & direction
    cstate = state.get("core_state", 0)
    if POWER_CORE_ENABLED and cstate > 0:
        obs[100] = 0.5 if cstate == 1 else 1.0
        if cstate == 1:
            spawn_t = CORE_SPAWN_1 if state.get("core_idx", 0) == 0 else CORE_SPAWN_2
            obs[101] = max(0.0, min(1.0, (spawn_t - state["t"]) / max(1, CORE_WARN_STEPS)))
        else:
            sign = 1.0 if s.get("id", 0) == 0 else -1.0
            obs[101] = max(-1.0, min(1.0, sign * state.get("core_prog", 0) / max(1, CORE_CAPTURE_STEPS)))
        cdx = state["core_x"] - x
        cdy = state["core_y"] - y
        cdist = math.hypot(cdx, cdy)
        cang = wrap(math.atan2(cdy, cdx) - h)
        obs[102] = cdist / ARENA
        obs[103] = math.sin(cang)
        obs[104] = math.cos(cang)
        obs[105] = 1.0 if (cstate == 2 and cdist <= CORE_RADIUS) else 0.0

    # 106..110: bushes & nearest bush
    bushes = state.get("bushes", [])
    if BUSHES_ENABLED:
        obs[106] = 1.0 if any((x - b["x"]) ** 2 + (y - b["y"]) ** 2 <= b["r"] ** 2 for b in bushes) else 0.0
        obs[107] = s.get("fire_reveal_t", 0) / max(1, BUSH_FIRE_REVEAL_STEPS)
    if bushes:
        nb = min(bushes, key=lambda b: (b["x"] - x) ** 2 + (b["y"] - y) ** 2)
        bdx, bdy = nb["x"] - x, nb["y"] - y
        bang = wrap(math.atan2(bdy, bdx) - h)
        obs[108] = min(1.0, math.hypot(bdx, bdy) / BASE_VIEW)
        obs[109] = math.sin(bang)
        obs[110] = math.cos(bang)
    else:
        obs[108] = 1.0

    # 111..117: turret aim destructible-cover flag, self pose, LOS, skill progress
    tx_d, ty_d = math.cos(s["turret"]), math.sin(s["turret"])
    t_solid = math.inf
    if tx_d > 1e-9:
        t_solid = min(t_solid, (ARENA - x) / tx_d)
    elif tx_d < -1e-9:
        t_solid = min(t_solid, -x / tx_d)
    if ty_d > 1e-9:
        t_solid = min(t_solid, (ARENA - y) / ty_d)
    elif ty_d < -1e-9:
        t_solid = min(t_solid, -y / ty_d)
    t_dest = math.inf
    for w in state["walls"]:
        if not rect_alive(w):
            continue
        rt = ray_rect(x, y, tx_d, ty_d, w)
        if w.get("destructible", 0):
            if rt < t_dest:
                t_dest = rt
        else:
            if rt < t_solid:
                t_solid = rt
    obs[111] = 1.0 if (t_dest < reach and t_dest < t_solid) else 0.0
    obs[112] = x / ARENA
    obs[113] = y / ARENA
    obs[114] = math.sin(h)
    obs[115] = math.cos(h)
    if vis:
        obs[116] = 1.0 if line_of_sight(x, y, vis[0]["x"], vis[0]["y"], state["walls"]) else 0.0
    m_dur = m_spec[0] if m_spec else 0
    sk_t = s.get("skill_t", 0)
    obs[117] = (sk_t / m_dur) if (m_dur > 0 and sk_t > 0) else 0.0
    return obs
