"""Rule bots: sparring partners for local games, and teachers for imitation learning (examples/02_behavior_cloning.py).

A bot gets the full state (the same dict the engine gives every policy) and returns 5 ints. Bots may use things a model
never sees (the exact positions of walls, bullets far away...). On the ladder only models play, so these are for training.

Actions: [move, body, turret, fire, skill]
    move: 0 forward, 1 back, 2 stop | body, turret: 0 left, 1 keep, 2 right | fire, skill: 0 no, 1 yes
"""
import math
import random

from .geometry import clearance, line_of_sight, visible_enemies, wrap
from .rules import CHASSIS, MODULES, TR, TROT

FWD, BACK, STOP = 0, 1, 2
LEFT, KEEP, RIGHT = 0, 1, 2


def turn_toward(current, target, step):
    """LEFT / KEEP / RIGHT to bring angle `current` toward `target`, turning at most `step` radians per step."""
    d = wrap(target - current)
    if abs(d) < step / 2: return KEEP
    return RIGHT if d > 0 else LEFT


class IdleBot:
    """Stands still and never shoots. The easiest opponent; good for checking that a model shoots at all."""
    label = "idle"

    def act(self, state):
        return [STOP, KEEP, KEEP, 0, 0]


class TurretBot:
    """Stays where it is and shoots at whatever it sees, leading its aim. Tests whether a model dodges and uses cover."""
    label = "turret"

    def act(self, state):
        me = state["self"]
        aim, fire = _aim(me, visible_enemies(state), state["walls"])
        return [STOP, KEEP, aim, fire, 0]


class ChaserBot:
    """A complete simple tactic: keep a preferred distance from the nearest visible enemy, circle it, lead the aim and
    fire, stay inside the safe zone, steer around walls, use the module sensibly; with nobody in sight, head for the
    centre of the zone. `distance` and `strafe` change its style; `seed` its small random choices."""
    label = "chaser"

    def __init__(self, distance=220, strafe=True, seed=None):
        self.distance, self.strafe = distance, strafe
        self.rng = random.Random(seed)
        self.reset()

    def reset(self):
        self.side = self.rng.choice((-1, 1))   # which way to circle
        self.flip_at = 0
        self.prev_hp = 1.0
        self.stuck = 0                         # steps in a row it tried to drive but did not move
        self.unstick = 0                       # steps left of backing out

    def act(self, state):
        me, zone, t = state["self"], state["zone"], state["t"]
        seen = visible_enemies(state)
        e = seen[0] if seen else None
        aim, fire = _aim(me, seen, state["walls"])
        hurt = me["hp_frac"] < self.prev_hp; self.prev_hp = me["hp_frac"]

        zone_d = math.hypot(zone["x"] - me["x"], zone["y"] - me["y"])
        to_zone = math.atan2(zone["y"] - me["y"], zone["x"] - me["x"])
        if zone_d > zone["r"] - 40:                       # (almost) outside: back to the zone first
            goal = to_zone
        elif e is not None:
            d = math.hypot(e["x"] - me["x"], e["y"] - me["y"])
            keep = min(self.distance, 150) if me["chassis"] == "shotgun" else self.distance   # shotgun: range ~330
            to_e = math.atan2(e["y"] - me["y"], e["x"] - me["x"])
            if t >= self.flip_at:                         # change the circling direction now and then
                self.side = self.rng.choice((-1, 1)); self.flip_at = t + self.rng.randint(40, 120)
            if d > keep + 40: goal = to_e + (0.35 * self.side if self.strafe else 0)
            elif d < keep - 40: goal = to_e + math.pi - 0.35 * self.side
            else: goal = to_e + (math.pi / 2) * self.side if self.strafe else to_e
        else:
            goal = to_zone if zone_d > 60 else me["heading"] + 0.6

        goal = _avoid_walls(me, goal, state["walls"])
        body = turn_toward(me["heading"], goal, CHASSIS[me["chassis"]][1])
        facing = abs(wrap(goal - me["heading"])) < 1.2
        move = FWD if facing else STOP
        if self.unstick:                                  # caught on a corner: back out while turning
            self.unstick -= 1
            move, body = BACK, (RIGHT if self.side > 0 else LEFT)
        elif move == FWD and math.hypot(me.get("vx", 0.0), me.get("vy", 0.0)) < 0.3:
            self.stuck += 1
            if self.stuck >= 8: self.stuck, self.unstick = 0, 18; self.side = self.rng.choice((-1, 1))
        else:
            self.stuck = 0

        los = e is not None and line_of_sight(me["x"], me["y"], e["x"], e["y"], state["walls"])
        if me["chassis"] == "siege" and los and zone_d < zone["r"] - 40 and math.hypot(e["x"] - me["x"], e["y"] - me["y"]) < 450:
            move = STOP                                   # siege: stand still to set up (faster reload, faster bullets)
        skill = 0
        m = me.get("module")
        if m in MODULES and me["skill_ready"]:
            if m == "shield": skill = int(_bullet_coming(state, 70))
            elif m == "stealth": skill = int(hurt and me["hp_frac"] < 0.6)
            elif m == "xray": skill = int(e is None and t > 60)
            elif m == "smoke": skill = int(hurt and me["hp_frac"] < 0.6 and e is not None)
            elif m == "overdrive": skill = int(los and math.hypot(e["x"] - me["x"], e["y"] - me["y"]) < 380)
        if m == "stealth" and me["skill_active"]: fire = 0   # firing ends stealth
        return [move, body, aim, fire, skill]


def _aim(me, seen, walls):
    """(turret action, fire) toward the nearest visible enemy, leading the target; with nobody seen, keep the turret
    pointing where the body goes. Holds fire while a wall is in the way (an x-ray can see through walls, bullets can't)."""
    if not seen:
        return turn_toward(me["turret"], me["heading"], TROT), 0
    e = seen[0]
    speed = me.get("bspd_now") or CHASSIS[me["chassis"]][3]
    dx, dy = e["x"] - me["x"], e["y"] - me["y"]
    t = math.hypot(dx, dy) / speed                       # bullet flight time, then aim where the enemy will be
    tx, ty = e["x"] + e["vx"] * t, e["y"] + e["vy"] * t
    want = math.atan2(ty - me["y"], tx - me["x"])
    err = abs(wrap(want - me["turret"]))
    fire = int(me["cooldown"] == 0 and err < 0.08 and line_of_sight(me["x"], me["y"], e["x"], e["y"], walls))
    return turn_toward(me["turret"], want, TROT), fire


def _room(x, y, a, walls):
    """Free space ahead for the whole width of a tank: rays from its centre and from both sides."""
    px, py = -math.sin(a) * (TR + 2), math.cos(a) * (TR + 2)
    return min(clearance(x + dx, y + dy, a, walls) for dx, dy in ((0, 0), (px, py), (-px, -py)))


def _avoid_walls(me, goal, walls, look=40):
    """The direction nearest to `goal` with at least `look` px of free space ahead for the tank's full width."""
    for off in (0, 0.4, -0.4, 0.8, -0.8, 1.2, -1.2, 1.6, -1.6, 2.2, -2.2, math.pi):
        a = goal + off
        if _room(me["x"], me["y"], a, walls) > look: return a
    return goal


def _bullet_coming(state, within):
    """An enemy bullet will pass within 20 px of me in the next few steps and is closer than `within` px."""
    me = state["self"]
    for b in state["bullets"]:
        dx, dy = me["x"] - b["x"], me["y"] - b["y"]
        if dx * dx + dy * dy > within * within: continue
        v2 = b["vx"] ** 2 + b["vy"] ** 2
        if v2 < 1e-9: continue
        t = (dx * b["vx"] + dy * b["vy"]) / v2              # when the bullet is closest
        if t < 0: continue
        cx, cy = b["x"] + b["vx"] * t - me["x"], b["y"] + b["vy"] * t - me["y"]
        if cx * cx + cy * cy < 20 * 20 and line_of_sight(b["x"], b["y"], me["x"], me["y"], state["walls"]): return True
    return False


BOTS = {"idle": IdleBot, "turret": TurretBot, "chaser": ChaserBot}
