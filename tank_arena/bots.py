"""Basic built-in bots for local testing and replays (v3_final)."""
import math
import random

from .geometry import clearance, line_of_sight, visible_enemies, wrap
from .rules import CHASSIS, MODULES, TR, TROT, TURRET_ROT_MULT, rect_alive

FWD, BACK, STOP = 0, 1, 2
LEFT, KEEP, RIGHT = 0, 1, 2


def turn_toward(current, target, step):
    """LEFT / KEEP / RIGHT to bring angle `current` toward `target`, turning at most `step` radians per step."""
    d = wrap(target - current)
    if abs(d) < step / 2:
        return KEEP
    return RIGHT if d > 0 else LEFT


class IdleBot:
    """Stands still and never shoots."""
    label = "idle"

    def act(self, state):
        return [STOP, KEEP, KEEP, 0, 0]


class TurretBot:
    """Stays where it is and shoots at whatever it sees, leading its aim."""
    label = "turret"

    def act(self, state):
        me = state["self"]
        aim, fire = _aim(me, visible_enemies(state), state["walls"])
        if me.get("overheat_t", 0) > 0:
            fire = 0
        return [STOP, KEEP, aim, fire, 0]


class ChaserBot:
    """A complete simple tactic updated for v3_final (vision cone, heat, destructible cover, radar sonar, power cores)."""
    label = "chaser"

    def __init__(self, distance=220, strafe=True, seed=None):
        self.distance, self.strafe = distance, strafe
        self.rng = random.Random(seed)
        self.reset()

    def reset(self):
        self.side = self.rng.choice((-1, 1))
        self.flip_at = 0
        self.prev_hp = 1.0
        self.stuck = 0
        self.unstick = 0

    def act(self, state):
        me, zone, t = state["self"], state["zone"], state["t"]
        seen = visible_enemies(state)
        e = seen[0] if seen else None
        aim, fire = _aim(me, seen, state["walls"])
        hurt = me["hp_frac"] < self.prev_hp
        self.prev_hp = me["hp_frac"]
        if me.get("overheat_t", 0) > 0:
            fire = 0

        zone_d = math.hypot(zone["x"] - me["x"], zone["y"] - me["y"])
        to_zone = math.atan2(zone["y"] - me["y"], zone["x"] - me["x"])
        core_on = state.get("core_state", 0) == 2
        cx, cy = state.get("core_x", 400.0), state.get("core_y", 400.0)
        core_safe = math.hypot(cx - zone["x"], cy - zone["y"]) < zone["r"] - 30

        if zone_d > zone["r"] - 40:
            goal = to_zone
        elif e is not None:
            d = math.hypot(e["x"] - me["x"], e["y"] - me["y"])
            keep = min(self.distance, 150) if me["chassis"] == "shotgun" else self.distance
            to_e = math.atan2(e["y"] - me["y"], e["x"] - me["x"])
            if t >= self.flip_at:
                self.side = self.rng.choice((-1, 1))
                self.flip_at = t + self.rng.randint(40, 120)
            if d > keep + 40:
                goal = to_e + (0.35 * self.side if self.strafe else 0)
            elif d < keep - 40:
                goal = to_e + math.pi - 0.35 * self.side
            else:
                goal = to_e + (math.pi / 2) * self.side if self.strafe else to_e
        elif core_on and core_safe:
            goal = math.atan2(cy - me["y"], cx - me["x"])
        else:
            goal = to_zone if zone_d > 60 else me["heading"] + 0.6

        alive_walls = [w for w in state["walls"] if rect_alive(w)]
        goal = _avoid_walls(me, goal, alive_walls)
        body = turn_toward(me["heading"], goal, CHASSIS[me["chassis"]][1])
        facing = abs(wrap(goal - me["heading"])) < 1.2
        move = FWD if facing else STOP
        if self.unstick:
            self.unstick -= 1
            move, body = BACK, (RIGHT if self.side > 0 else LEFT)
        elif move == FWD and math.hypot(me.get("vx", 0.0), me.get("vy", 0.0)) < 0.3:
            self.stuck += 1
            if self.stuck >= 8:
                self.stuck, self.unstick = 0, 18
                self.side = self.rng.choice((-1, 1))
        else:
            self.stuck = 0

        los = e is not None and line_of_sight(me["x"], me["y"], e["x"], e["y"], alive_walls)
        if me["chassis"] == "siege" and los and zone_d < zone["r"] - 40 and math.hypot(e["x"] - me["x"], e["y"] - me["y"]) < 450:
            move = STOP
        skill = 0
        m = me.get("module")
        d_e = math.hypot(e["x"] - me["x"], e["y"] - me["y"]) if e is not None else 1e9
        if m in MODULES and me["skill_ready"]:
            if m == "shield":
                skill = int(_bullet_coming(state, 70))
            elif m == "stealth":
                skill = int(hurt and me["hp_frac"] < 0.6)
            elif m == "radar":
                skill = int((e is None and t > 60) or (e is not None and d_e < 420))
            elif m == "backstep":
                skill = int(_bullet_coming(state, 70) or (hurt and e is not None))
            elif m == "focus":
                skill = int(los and d_e < 480)
            elif m == "xray":
                skill = int(e is None and t > 60)
            elif m == "smoke":
                skill = int(hurt and me["hp_frac"] < 0.6 and e is not None)
            elif m == "overdrive":
                skill = int(los and d_e < 380)
        if m == "stealth" and me["skill_active"]:
            fire = 0
        return [move, body, aim, fire, skill]


def _aim(me, seen, walls):
    trot = TROT * TURRET_ROT_MULT.get(me.get("chassis", "gunner"), 1.0)
    if not seen:
        return turn_toward(me["turret"], me["heading"], trot), 0
    e = seen[0]
    speed = me.get("bspd_now") or CHASSIS[me["chassis"]][3]
    dx, dy = e["x"] - me["x"], e["y"] - me["y"]
    t = math.hypot(dx, dy) / speed
    tx, ty = e["x"] + e["vx"] * t, e["y"] + e["vy"] * t
    want = math.atan2(ty - me["y"], tx - me["x"])
    err = abs(wrap(want - me["turret"]))
    fire = int(me["cooldown"] == 0 and err < 0.08 and line_of_sight(me["x"], me["y"], e["x"], e["y"], walls))
    return turn_toward(me["turret"], want, trot), fire


def _room(x, y, a, walls):
    px, py = -math.sin(a) * (TR + 2), math.cos(a) * (TR + 2)
    return min(clearance(x + dx, y + dy, a, walls) for dx, dy in ((0, 0), (px, py), (-px, -py)))


def _avoid_walls(me, goal, walls, look=40):
    for off in (0, 0.4, -0.4, 0.8, -0.8, 1.2, -1.2, 1.6, -1.6, 2.2, -2.2, math.pi):
        a = goal + off
        if _room(me["x"], me["y"], a, walls) > look:
            return a
    return goal


def _bullet_coming(state, within):
    me = state["self"]
    for b in state["bullets"]:
        dx, dy = me["x"] - b["x"], me["y"] - b["y"]
        if dx * dx + dy * dy > within * within:
            continue
        v2 = b["vx"] ** 2 + b["vy"] ** 2
        if v2 < 1e-9:
            continue
        t = (dx * b["vx"] + dy * b["vy"]) / v2
        if t < 0:
            continue
        cx, cy = b["x"] + b["vx"] * t - me["x"], b["y"] + b["vy"] * t - me["y"]
        if cx * cx + cy * cy < 20 * 20 and line_of_sight(b["x"], b["y"], me["x"], me["y"], state["walls"]):
            return True
    return False


BOTS = {"idle": IdleBot, "turret": TurretBot, "chaser": ChaserBot}
