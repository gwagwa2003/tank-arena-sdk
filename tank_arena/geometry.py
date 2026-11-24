"""Geometry shared by the engine, the observation and the bots: angles, rays against walls, line of sight, visibility."""
import math

from .rules import ARENA

BASE_VIEW = 340      # how far a tank sees (px)
RADAR_VIEW = 450     # ... with the radar module
RADAR_SEEN = 1.1     # a tank carrying a radar is seen from 1.1x further away


def wrap(a):
    """An angle in radians, brought into -pi..pi."""
    return (a + math.pi) % (2 * math.pi) - math.pi


def ray_rect(ox, oy, dx, dy, r):
    """Distance along the unit ray (ox, oy) + t·(dx, dy), t >= 0, to the rectangle r (dict x, y, w, h); inf if it misses.
    A ray that starts inside the rectangle hits it at 0."""
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
    """How far from (x, y) in direction ang the first wall or the arena edge is (px)."""
    dx, dy = math.cos(ang), math.sin(ang)
    d = min((ray_rect(x, y, dx, dy, w) for w in walls), default=math.inf)
    if dx > 1e-9: d = min(d, (ARENA - x) / dx)
    elif dx < -1e-9: d = min(d, -x / dx)
    if dy > 1e-9: d = min(d, (ARENA - y) / dy)
    elif dy < -1e-9: d = min(d, -y / dy)
    return d


def line_of_sight(ax, ay, bx, by, walls):
    """True when no wall stands between the two points."""
    dist = math.hypot(bx - ax, by - ay)
    if dist < 1e-6:
        return True
    dx, dy = (bx - ax) / dist, (by - ay) / dist
    return all(ray_rect(ax, ay, dx, dy, w) >= dist for w in walls)


def view_of(module):
    return RADAR_VIEW if module == "radar" else BASE_VIEW


def visible_enemies(state):
    """The enemies this tank can see, nearest first: alive, not stealthed, within view (1.1x for a radar carrier)
    and not behind a wall (walls do not count while its own x-ray is on). These are the enemies the model observation shows."""
    me = state["self"]; view = view_of(me.get("module")); xray = me.get("module") == "xray" and me.get("skill_active")
    dist = lambda e: math.hypot(e["x"] - me["x"], e["y"] - me["y"])
    seen = [e for e in state["enemies"] if e["alive"] and not e["stealthed"]
            and dist(e) < view * (RADAR_SEEN if e.get("module") == "radar" else 1)
            and (xray or line_of_sight(me["x"], me["y"], e["x"], e["y"], state["walls"]))]
    return sorted(seen, key=dist)
