"""Arena constants: v3_final ruleset, procedural symmetric maps, chassis, modules, timings. Same values as the Tank Arena server."""
from __future__ import annotations

import math

RULES_VERSION = "v3_final"

MAPS = {
    "fort": dict(
        name="十字堡壘",
        rects=[
            (370, 260, 60, 280),
            (260, 370, 280, 60),
            (130, 140, 100, 36),
            (570, 140, 100, 36),
            (130, 624, 100, 36),
            (570, 624, 100, 36),
            (90, 370, 40, 60),
            (670, 370, 40, 60),
        ],
    ),
    "city": dict(
        name="城區巷戰",
        rects=[
            (170, 180, 130, 56),
            (510, 150, 56, 150),
            (345, 345, 110, 110),
            (150, 510, 56, 150),
            (500, 565, 150, 56),
            (40, 385, 110, 30),
            (650, 385, 110, 30),
            (370, 70, 60, 44),
            (370, 686, 60, 44),
        ],
    ),
}

ARENA, TR, TROT, STEPS = 800, 16, 0.11, 1200
INIT_COOLDOWN, INIT_SKILL_CD = 20, 60
ZONE_START, ZONE_END, ZONE_R_START, ZONE_R_END, ZONE_DPS = 200, 1000, 620.0, 90.0, 0.5

# Physics: inertia, directional armor, barrel heat
INERTIA_ENABLED = True
ACCEL_FWD, ACCEL_REV, DECEL_DRAG, TURN_SPEED_MULT = 0.85, 0.58, 0.7, 0.9

ARMOR_ENABLED = True
ARMOR_FRONT_HALF, ARMOR_REAR_HALF = 0.96, 2.18
ARMOR_FRONT_MULT, ARMOR_SIDE_MULT, ARMOR_REAR_MULT = 0.8, 1.0, 1.35

HEAT_ENABLED = True
HEAT_COOL_PER_STEP, HEAT_SPREAD_THRESH, HEAT_MAX_BLOOM, HEAT_OVERHEAT_LOCK = 0.85, 75.0, 0.06, 30

# Vision, sound cues, dynamic battlefield
VISION_CONE_ENABLED = True
VISION_NEAR_RADIUS, VISION_CONE_HALF_ANGLE, RADAR_CONE_BONUS = 150.0, 1.31, 0.35
HIDE_ENEMY_VEL = True
BULLET_OBS_RANGE = 250.0

SOUND_CUES_ENABLED = True
SOUND_ANGLE_NOISE, SOUND_DECAY_STEPS = 0.26, 40

PROC_MAPS_ENABLED = True
BUSHES_ENABLED = True
BUSH_REVEAL_DIST, BUSH_FIRE_REVEAL_STEPS = 85.0, 25

DESTRUCTIBLE_COVER_ENABLED = True
COVER_HP = 45.0

POWER_CORE_ENABLED = True
CORE_SPAWN_1, CORE_SPAWN_2, CORE_WARN_STEPS = 300, 700, 100
CORE_RADIUS, CORE_CAPTURE_STEPS, CORE_HEAL_FRAC, CORE_CD_REFUND_FRAC = 42.0, 30, 0.22, 0.5

# chassis: speed (px/step), body turn (rad/step), reload (steps), bullet speed, bullet life (steps), HP
CHASSIS = dict(
    gunner=(3.0, 0.070, 12, 10.8, 42, 106),
    shotgun=(2.92, 0.072, 32, 11.5, 24, 110),
    skirmisher=(3.57, 0.080, 10, 12.25, 27, 92),
    marksman=(2.65, 0.060, 23, 15.51, 36, 96),
)
DAMAGE = dict(gunner=11.45, shotgun=7.75, skirmisher=9.85, marksman=20.4)
TURRET_ROT_MULT = dict(gunner=1.0, shotgun=0.95, skirmisher=1.05, marksman=0.82)
VIEW_BONUS = dict(gunner=10.0, shotgun=-10.0, skirmisher=0.0, marksman=70.0)
HEAT_PER_SHOT = dict(gunner=16.5, shotgun=44.0, skirmisher=10.5, marksman=36.0)

SIEGE_WAIT, SIEGE_RELOAD, SIEGE_BSPD = 30, 14, 13.0  # retired chassis siege
SHOT_N, SHOT_SPREAD = 5, 0.19
SHOT_FALLOFF = (7.75, 2.5, 6, 14)

# active modules: duration, cooldown (steps)
MODULES = dict(
    stealth=(45, 212),
    shield=(40, 358),
    radar=(60, 178),
    backstep=(4, 225),
    focus=(45, 198),
)
SMOKE_R, OVERDRIVE = 60, 0.75  # retired modules smoke / overdrive
BLINK, STEALTH_REVEAL_DIST = 68.0, 88.0
SHIELD_ABSORB, SHIELD_ARC_HALF, SHIELD_MOVE_MULT = 7.8, 1.134, 0.77
RADAR_SONAR_RANGE, RADAR_ARMOR_PIERCE = 650.0, True
BACKSTEP, BACKSTEP_DASH_MODE = 54.0, 1
FOCUS_BSPD_MULT, FOCUS_DMG_MULT, FOCUS_MOVE = 1.28, 1.27, 0.72
ALL_MODULES = ["stealth", "shield", "radar", "backstep", "focus"]

CHASSIS_INFO = {
    "gunner": "速射：速度 3.0、裝填 12、傷害 11.45、彈速 10.8、射程約 454、視野 +10、熱量 16.5、血量 106",
    "shotgun": "散彈：速度 2.92、裝填 32、5 顆扇形（近 7.75→遠 2.5，貼臉 38.75）、彈速 11.5、視野 −10、熱量 44、血量 110",
    "skirmisher": "遊擊：速度 3.57、轉向快、裝填 10、傷害 9.85、彈速 12.25、射程約 331、熱量 10.5、血量 92",
    "marksman": "狙擊：速度 2.65、砲塔較慢、裝填 23、傷害 20.4、彈速 15.51、射程約 558、視野 +70、熱量 36、血量 96",
}
MODULE_INFO = {
    "stealth": "隱身：啟動時往移動方向閃現 68，之後 2.25 秒內近身 88 才被發現、開火解除、冷卻 10.6 秒（發出聲波提示）",
    "shield": "護盾：2 秒內砲口前方 ±65° 吸收最多 7.8 傷害（移速 ×0.77）、冷卻 17.9 秒",
    "radar": "雷達：被動視野 +78、視野錐擴大；主動聲納 3 秒內偵測 650 內敵人且穿甲（無視前甲減傷）、冷卻 8.9 秒",
    "backstep": "側閃：啟動後 4 步高速衝刺共 54 像素（移動方向，停止時依砲塔側閃）、冷卻 11.25 秒",
    "focus": "專注：2.25 秒內彈速 ×1.28、傷害 ×1.27、移速 ×0.72、冷卻 9.9 秒",
}

_XOR_DEFAULT = 0x9E3779B97F4A7C15


def rect_alive(w: dict) -> bool:
    return not (w.get("destructible", 0) and w.get("hp", 0.0) <= 0.0)


def hits_rect(x: float, y: float, rad: float, r: dict) -> bool:
    nx = max(r["x"], min(x, r["x"] + r["w"]))
    ny = max(r["y"], min(y, r["y"] + r["h"]))
    return (x - nx) ** 2 + (y - ny) ** 2 < rad * rad


def _xorshift64(s: int) -> int:
    x = s & 0xFFFFFFFFFFFFFFFF
    if x == 0:
        x = _XOR_DEFAULT
    x ^= (x << 13) & 0xFFFFFFFFFFFFFFFF
    x ^= (x >> 7) & 0xFFFFFFFFFFFFFFFF
    x ^= (x << 17) & 0xFFFFFFFFFFFFFFFF
    return x & 0xFFFFFFFFFFFFFFFF


def _rng_u01(state: list[int]) -> float:
    state[0] = _xorshift64(state[0])
    return (state[0] >> 11) * (1.0 / 9007199254740992.0)


def _rng_range(state: list[int], lo: float, hi: float) -> float:
    return lo + (hi - lo) * _rng_u01(state)


def map_seed_from_episode_seed(seed: int) -> int:
    ms = ((int(seed) + 1) * 0xD1B54A32D192ED03) & 0xFFFFFFFFFFFFFFFF
    return ms if ms != 0 else _XOR_DEFAULT


def _rects_overlap_pad(a: dict, b: dict, pad: float) -> bool:
    return (
        a["x"] - pad < b["x"] + b["w"]
        and a["x"] + a["w"] + pad > b["x"]
        and a["y"] - pad < b["y"] + b["h"]
        and a["y"] + a["h"] + pad > b["y"]
    )


def pick_core_spots(walls: list[dict], flip: int) -> tuple[float, float, float, float]:
    cands = [400.0, 260.0, 540.0, 170.0, 630.0] if flip == 0 else [400.0, 540.0, 260.0, 630.0, 170.0]
    rad = CORE_RADIUS + 8.0
    valid = [cx for cx in cands if not any(hits_rect(cx, 400.0, rad, w) for w in walls)]
    if not valid:
        return 260.0, 400.0, 540.0, 400.0
    x1 = valid[0]
    x2 = valid[1] if len(valid) >= 2 else valid[0]
    return x1, 400.0, x2, 400.0


def generate_proc_map(map_seed: int) -> tuple[list[dict], list[dict], float, float, float, float]:
    """Deterministic point-symmetric procedural map generator (exact server parity)."""
    state = [map_seed & 0xFFFFFFFFFFFFFFFF]
    walls: list[dict] = []
    bushes: list[dict] = []

    def add_wall(x: float, y: float, w: float, h: float, dest: int) -> None:
        d = 1 if (dest and DESTRUCTIBLE_COVER_ENABLED) else 0
        hp = COVER_HP if d else 0.0
        walls.append(dict(x=x, y=y, w=w, h=h, destructible=d, hp=hp, max_hp=hp))

    state[0] = _xorshift64(state[0])
    arch = state[0] % 3
    if arch == 0:
        add_wall(365.0, 365.0, 70.0, 70.0, 0)
        add_wall(245.0, 384.0, 52.0, 32.0, 1)
        add_wall(503.0, 384.0, 52.0, 32.0, 1)
    elif arch == 1:
        add_wall(310.0, 320.0, 42.0, 160.0, 0)
        add_wall(448.0, 320.0, 42.0, 160.0, 0)
        add_wall(376.0, 250.0, 48.0, 28.0, 1)
        add_wall(376.0, 522.0, 48.0, 28.0, 1)
    else:
        add_wall(280.0, 270.0, 56.0, 56.0, 0)
        add_wall(464.0, 474.0, 56.0, 56.0, 0)
        add_wall(464.0, 270.0, 56.0, 56.0, 1)
        add_wall(280.0, 474.0, 56.0, 56.0, 1)

    state[0] = _xorshift64(state[0])
    target_pairs = 3 + (state[0] % 2)
    added = 0
    for _ in range(40):
        if added >= target_pairs or len(walls) + 2 > 24:
            break
        w = float(math.floor(_rng_range(state, 44.0, 116.0)))
        h = float(math.floor(_rng_range(state, 34.0, 96.0)))
        x = float(math.floor(_rng_range(state, 64.0, ARENA - 64.0 - w)))
        y = float(math.floor(_rng_range(state, 115.0, 340.0 - 0.5 * h)))
        r1 = dict(x=x, y=y, w=w, h=h, destructible=0, hp=0.0, max_hp=0.0)
        r2 = dict(x=ARENA - x - w, y=ARENA - y - h, w=w, h=h, destructible=0, hp=0.0, max_hp=0.0)
        if _rects_overlap_pad(r1, r2, 48.0):
            continue
        bad = False
        for rr in (r1, r2):
            for cx, cy, cr in (
                (400.0, 50.0, 92.0),
                (400.0, 750.0, 92.0),
                (400.0, 400.0, 52.0),
                (260.0, 400.0, 52.0),
                (540.0, 400.0, 52.0),
            ):
                if hits_rect(cx, cy, cr, rr):
                    bad = True
                    break
            if bad:
                break
            for ew in walls:
                if _rects_overlap_pad(rr, ew, 46.0):
                    bad = True
                    break
            if bad:
                break
        if bad:
            continue
        dest = 1 if (added % 2 == 1) else 0
        add_wall(r1["x"], r1["y"], r1["w"], r1["h"], dest)
        add_wall(r2["x"], r2["y"], r2["w"], r2["h"], dest)
        added += 1

    if BUSHES_ENABLED:
        state[0] = _xorshift64(state[0])
        target_b = 2 + (state[0] % 2)
        added_b = 0
        for _ in range(40):
            if added_b >= target_b or len(bushes) + 2 > 8:
                break
            br = float(math.floor(_rng_range(state, 44.0, 56.0)))
            bx = float(math.floor(_rng_range(state, 100.0, 700.0)))
            by = float(math.floor(_rng_range(state, 140.0, 355.0)))
            mbx, mby = ARENA - bx, ARENA - by
            if math.hypot(bx - 400.0, by - 50.0) < 95.0 or math.hypot(bx - 400.0, by - 750.0) < 95.0:
                continue
            if math.hypot(bx - mbx, by - mby) < 2.0 * br + 30.0:
                continue
            if any(hits_rect(bx, by, br + 12.0, w) or hits_rect(mbx, mby, br + 12.0, w) for w in walls):
                continue
            if any(
                math.hypot(bx - eb["x"], by - eb["y"]) < br + eb["r"] + 28.0
                or math.hypot(mbx - eb["x"], mby - eb["y"]) < br + eb["r"] + 28.0
                for eb in bushes
            ):
                continue
            bushes.append(dict(x=bx, y=by, r=br))
            bushes.append(dict(x=mbx, y=mby, r=br))
            added_b += 1

    state[0] = _xorshift64(state[0])
    flip = int(state[0] & 1)
    cx1, cy1, cx2, cy2 = pick_core_spots(walls, flip)
    return walls, bushes, cx1, cy1, cx2, cy2
