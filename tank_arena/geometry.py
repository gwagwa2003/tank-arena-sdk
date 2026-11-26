"""Geometry shared by the engine, the observation and the bots: angles, rays against walls, line of sight, visibility (v3_final)."""
import math

from .rules import (
    ARENA,
    BUSH_FIRE_REVEAL_STEPS,
    BUSH_REVEAL_DIST,
    BUSHES_ENABLED,
    MODULES,
    RADAR_CONE_BONUS,
    RADAR_SONAR_RANGE,
    VIEW_BONUS,
    VISION_CONE_ENABLED,
    VISION_CONE_HALF_ANGLE,
    VISION_NEAR_RADIUS,
    rect_alive,
)

BASE_VIEW = 340.0            # how far a tank sees (px)
RADAR_PASSIVE_BONUS = 78.0
RADAR_VIEW = BASE_VIEW + RADAR_PASSIVE_BONUS   # 418.0
RADAR_SEEN = 1.0
RAY_REACH_BASE = 320.0
RAY_REACH_RADAR = RAY_REACH_BASE + RADAR_PASSIVE_BONUS  # 398.0


def wrap(a):
    """An angle in radians, brought into -pi..pi."""
    return (a + math.pi) % (2.0 * math.pi) - math.pi


def ray_rect(ox, oy, dx, dy, r):
    """Distance along the unit ray (ox, oy) + t*(dx, dy), t >= 0, to the rectangle r (dict x, y, w, h); inf if it misses."""
    t_in, t_out = -math.inf, math.inf
    for o, d, lo, hi in ((ox, dx, r["x"], r["x"] + r["w"]), (oy, dy, r["y"], r["y"] + r["h"])):
        if abs(d) < 1e-9:
            if not lo <= o <= hi:
                return math.inf
            continue
        a, b = (lo - o) / d, (hi - o) / d
        if a > b:
            a, b = b, a
        t_in, t_out = max(t_in, a), min(t_out, b)
    if t_out < t_in or t_out < 0:
        return math.inf
    return max(t_in, 0.0)


def clearance(x, y, ang, walls):
    """How far from (x, y) in direction ang the first alive wall or the arena edge is (px)."""
    dx, dy = math.cos(ang), math.sin(ang)
    d = min((ray_rect(x, y, dx, dy, w) for w in walls if rect_alive(w)), default=math.inf)
    if dx > 1e-9:
        d = min(d, (ARENA - x) / dx)
    elif dx < -1e-9:
        d = min(d, -x / dx)
    if dy > 1e-9:
        d = min(d, (ARENA - y) / dy)
    elif dy < -1e-9:
        d = min(d, -y / dy)
    return d


def line_of_sight(ax, ay, bx, by, walls):
    """True when no alive wall stands between the two points."""
    dist = math.hypot(bx - ax, by - ay)
    if dist < 1e-6:
        return True
    dx, dy = (bx - ax) / dist, (by - ay) / dist
    return all(ray_rect(ax, ay, dx, dy, w) >= dist for w in walls if rect_alive(w))


def view_of(chassis_or_module, module=None):
    """View range (px): accepts view_of(module) or view_of(chassis, module)."""
    if module is None:
        return RADAR_VIEW if chassis_or_module == "radar" else BASE_VIEW
    base = RADAR_VIEW if module == "radar" else BASE_VIEW
    return base + VIEW_BONUS.get(chassis_or_module, 0.0)


def in_smoke(ax, ay, bx, by, smokes):
    """True if the straight line from a to b passes through a smoke cloud."""
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy or 1e-9
    for c in smokes:
        t = max(0.0, min(1.0, ((c["x"] - ax) * dx + (c["y"] - ay) * dy) / L2))
        if (ax + dx * t - c["x"]) ** 2 + (ay + dy * t - c["y"]) ** 2 < c["r"] ** 2:
            return True
    return False


def visible_enemies(state):
    """Enemies visible to state['self'] under v3_final rules (sonar, stealth reveal dist, bushes, vision cone, LOS)."""
    me = state["self"]
    my_mod = me.get("module")
    my_ch = me.get("chassis", "gunner")
    view = view_of(my_ch, my_mod)
    sonar_dur = MODULES["radar"][0]
    me_sonar = my_mod == "radar" and me.get("skill_active", False)
    bushes = state.get("bushes", [])
    smokes = state.get("smokes", [])
    xray = my_mod == "xray" and me.get("skill_active", False)

    seen = []
    for e in state["enemies"]:
        if not e["alive"]:
            continue
        dist = math.hypot(e["x"] - me["x"], e["y"] - me["y"])
        en_mod = e.get("module")
        en_sonar = en_mod == "radar" and e.get("skill_active", False) and e.get("skill_t", 0) > (sonar_dur - 15)
        sonar_link = (me_sonar and dist < RADAR_SONAR_RANGE) or (en_sonar and dist < RADAR_SONAR_RANGE)

        eff_stealthed = bool(e.get("stealthed", False))
        if eff_stealthed and dist < 88.0:
            eff_stealthed = False
        if eff_stealthed and me_sonar and dist < RADAR_SONAR_RANGE:
            eff_stealthed = False
        if eff_stealthed:
            continue

        if BUSHES_ENABLED and bushes and not sonar_link:
            in_bush = any((e["x"] - b["x"]) ** 2 + (e["y"] - b["y"]) ** 2 <= b["r"] ** 2 for b in bushes)
            if in_bush and dist >= BUSH_REVEAL_DIST and e.get("fire_reveal_t", 0) <= 0:
                continue

        if sonar_link:
            seen.append((dist, e))
        else:
            v_lim = view * (RADAR_SEEN if en_mod == "radar" else 1.0)
            if dist >= v_lim:
                continue
            if VISION_CONE_ENABLED and dist >= VISION_NEAR_RADIUS:
                cone_half = VISION_CONE_HALF_ANGLE + (RADAR_CONE_BONUS if my_mod == "radar" else 0.0)
                ang_to_e = math.atan2(e["y"] - me["y"], e["x"] - me["x"])
                if abs(wrap(ang_to_e - me["turret"])) > cone_half:
                    continue
            if xray or (line_of_sight(me["x"], me["y"], e["x"], e["y"], state["walls"]) and not in_smoke(me["x"], me["y"], e["x"], e["y"], smokes)):
                seen.append((dist, e))

    seen.sort(key=lambda pair: pair[0])
    return [e for _, e in seen]
