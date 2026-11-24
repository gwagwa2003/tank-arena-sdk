"""The game: same rules and the same physics as the Tank Arena server.

1,200 steps (20 steps = 1 second), 12 damage per bullet (lancer 15), a shield absorbs one bullet, the safe zone shrinks from radius
620 to 90 between steps 200 and 1,000, 0.5 HP per step outside it (0.25 with antizone).

Two ways to use it:
- play(seed, loadouts, policies): a whole game; a policy is any object with act(state) -> 5 ints (and optionally reset()).
- Game(seed, loadouts): one step at a time (game.state(i), game.step(actions)), which is what env.TankEnv uses for training.
"""
import math
import random

from .geometry import wrap
from .rules import ARENA, BLINK, CHASSIS, DAMAGE, MAPS, MODULES, STEPS, TR, TROT, hits_rect

IDLE = [2, 1, 1, 0, 0]          # stop, keep heading, keep turret, hold fire, no skill
ACTION_SIZES = (3, 3, 3, 2, 2)  # move, body, turret, fire, skill
REPLAY_EVERY = 2                # replays keep every 2nd step


def valid_action(act):
    """5 ints within ACTION_SIZES, or ValueError."""
    act = [int(v) for v in act]
    if len(act) != 5 or not all(0 <= v < k for v, k in zip(act, ACTION_SIZES)): raise ValueError(f"bad action {act}")
    return act


def duel_outcome(rows):
    """1v1 result of each row: "W", "L" or "D". The survivor wins; if both died, the one who lasted longer; if both are
    alive at the time limit, the one with more HP left (as a share of its maximum). Same death step or same HP: a draw."""
    def key(r):
        return (r["alive"], r["death"], round(r["hp"], 6) if r["alive"] else 0.0)
    ka, kb = key(rows[0]), key(rows[1])
    if ka == kb: return ["D", "D"]
    return ["W", "L"] if ka > kb else ["L", "W"]


class Game:
    """One game, played step by step.

    game = Game(seed, [("gunner", "shield"), ("scout", "stealth")])
    while not game.over:
        game.step([policy_i.act(game.state(i)) for i in ...])   # None for a tank that is already dead
    rows = game.results()
    """
    def __init__(self, seed, loadouts, mapname=None):
        rng = random.Random(seed)
        n = len(loadouts)
        self.mapname = mapname or rng.choice(["fort", "city"])
        self.walls = [dict(x=x, y=y, w=w, h=h) for x, y, w, h in MAPS[self.mapname]["rects"]]
        self.zone = dict(x=rng.uniform(320, 480), y=rng.uniform(320, 480), r=620.0)
        spots = list(range(n)); rng.shuffle(spots)
        self.tanks = []
        for i, (c, m) in enumerate(loadouts):
            if c not in CHASSIS: raise ValueError(f"unknown chassis {c!r}")
            ang = -math.pi / 2 + spots[i] * 2 * math.pi / n
            x, y = 400 + 350 * math.cos(ang), 400 + 350 * math.sin(ang)
            hd = math.atan2(400 - y, 400 - x)
            self.tanks.append(dict(id=i, x=x, y=y, vx=0.0, vy=0.0, heading=hd, turret=hd, hp=CHASSIS[c][5], hp_frac=1.0,
                                   chassis=c, module=m, cooldown=20, skill_ready=False, skill_active=False, stealthed=False,
                                   alive=True, skill_cd=60, skill_t=0, shield=0, kills=0, hits=0, shots=0, damage=0,
                                   taken=0, zone_death=False, death=STEPS, skills=0, errors=0, killer=None,
                                   threats=0, dodged=0, struck=0))
        self.bullets = []
        self.tick = 0          # the step about to be played
        self.steps = 0         # steps played
        self.over = False
        self.events = []       # [step, "kill", shooter, victim] / [step, "zone", None, victim]
        self._uid = 0
        self._near_seen = set()
        self._begin()

    @property
    def head(self):
        """Map, walls and zone centre (the parts of a replay that never change)."""
        return dict(map=self.mapname, walls=[[w["x"], w["y"], w["w"], w["h"]] for w in self.walls],
                    zone=[self.zone["x"], self.zone["y"]], every=REPLAY_EVERY)

    def _begin(self):
        if sum(a["alive"] for a in self.tanks) <= 1 or self.tick >= STEPS:
            self.over = True
            return
        t = self.tick
        self.zone["r"] = 620.0 if t < 200 else max(90.0, 620 - (t - 200) * 530 / 800)

    def state(self, i):
        """What tank i's policy gets this step. The full state: the observation (observation.py) is what a model sees."""
        a = self.tanks[i]
        return dict(t=self.tick, self=a, enemies=[b for b in self.tanks if b is not a],
                    bullets=[dict(x=b["x"], y=b["y"], vx=b["vx"], vy=b["vy"], own=False) for b in self.bullets if b["owner"] != i],
                    zone=self.zone, walls=self.walls)

    def frame(self):
        """This moment for a replay: [step, zone radius, tanks [x, y, heading, turret, hp, alive, skill, shield], bullets]."""
        return [self.tick if not self.over else self.steps, round(self.zone["r"], 1),
                [[round(a["x"], 1), round(a["y"], 1), round(a["heading"], 3), round(a["turret"], 3),
                  round(a["hp_frac"], 3), int(a["alive"]), int(a["skill_active"]), int(a["shield"] > 0)] for a in self.tanks],
                [[round(b["x"], 1), round(b["y"], 1), b["owner"]] for b in self.bullets]]

    def _free(self, x, y, i):
        return (TR < x < ARENA - TR and TR < y < ARENA - TR and not any(hits_rect(x, y, TR, w) for w in self.walls)
                and all(not o["alive"] or o["id"] == i or (o["x"] - x) ** 2 + (o["y"] - y) ** 2 >= 4 * TR * TR for o in self.tanks))

    def step(self, actions):
        """Play one step. actions: one per tank (5 ints, or None for a dead tank). An invalid action counts as an error and
        the tank idles."""
        if self.over: raise RuntimeError("the game is over")
        tick, ts = self.tick, self.tanks
        acts = []
        for a, act in zip(ts, actions):
            if not a["alive"]: acts.append(None); continue
            try:
                acts.append(valid_action(act))
            except Exception:
                acts.append(list(IDLE)); a["errors"] += 1
        for a, act in zip(ts, acts):
            if not a["alive"]: continue
            spd, rot, reload, bspd, blife, maxhp = CHASSIS[a["chassis"]]; m = a["module"]; just = False
            if m in MODULES and act[4] == 1 and a["skill_cd"] <= 0:
                a["skill_t"], a["skill_cd"] = MODULES[m]; just = True; a["skills"] += 1
                if m == "shield": a["shield"] = 12
                if m == "stealth":                            # blink: 4 px at a time, stop in front of walls and tanks
                    d = a["heading"] + (math.pi if act[0] == 1 else 0)
                    for _ in range(BLINK // 4):
                        tx, ty = a["x"] + math.cos(d) * 4, a["y"] + math.sin(d) * 4
                        if not self._free(tx, ty, a["id"]): break
                        a["x"], a["y"] = tx, ty
            a["heading"] = wrap(a["heading"] + (act[1] - 1) * rot)
            v = spd * (1 if act[0] == 0 else -0.6 if act[0] == 1 else 0)
            ox, oy = a["x"], a["y"]; nx = ox + math.cos(a["heading"]) * v; ny = oy + math.sin(a["heading"]) * v
            if v != 0:
                if self._free(nx, ny, a["id"]): a["x"], a["y"] = nx, ny
                elif self._free(nx, oy, a["id"]): a["x"] = nx
                elif self._free(ox, ny, a["id"]): a["y"] = ny
            a["vx"], a["vy"] = a["x"] - ox, a["y"] - oy
            a["turret"] = wrap(a["turret"] + (act[2] - 1) * TROT); a["cooldown"] = max(0, a["cooldown"] - 1)
            if act[3] == 1 and not a["cooldown"] and not (just and m == "stealth"):
                self._uid += 1
                self.bullets.append(dict(uid=self._uid, x=a["x"] + math.cos(a["turret"]) * 24, y=a["y"] + math.sin(a["turret"]) * 24,
                                         vx=math.cos(a["turret"]) * bspd, vy=math.sin(a["turret"]) * bspd, owner=a["id"], life=blife,
                                         dmg=DAMAGE.get(a["chassis"], 12)))
                a["cooldown"] = reload; a["shots"] += 1
                if m == "stealth": a["skill_t"] = 0
        keep = []
        for b in self.bullets:
            b["x"] += b["vx"]; b["y"] += b["vy"]; b["life"] -= 1; x = b["x"]; y = b["y"]
            if not (0 < x < ARENA and 0 < y < ARENA and b["life"] > 0) or any(
                    w["x"] <= x <= w["x"] + w["w"] and w["y"] <= y <= w["y"] + w["h"] for w in self.walls):
                continue
            target = None
            for a in ts:
                if not a["alive"] or a["id"] == b["owner"]: continue
                d2 = (a["x"] - x) ** 2 + (a["y"] - y) ** 2
                if d2 < 1600 and (b["uid"], a["id"]) not in self._near_seen:   # a threat: first time within 40 px
                    self._near_seen.add((b["uid"], a["id"])); a["threats"] += 1; a["dodged"] += 1
                if d2 < 256 and target is None: target = a
            if target:
                sh = ts[b["owner"]]; sh["hits"] += 1; target["struck"] += 1; target["dodged"] -= 1
                dmg = 0 if target["shield"] > 0 else b["dmg"]; target["shield"] = 0  # the shield takes one whole bullet
                target["hp"] -= dmg; target["taken"] += dmg; sh["damage"] += dmg
                if target["hp"] <= 0 and target["alive"]:
                    target["alive"] = False; target["hp_frac"] = 0.0; target["death"] = tick; target["killer"] = sh["id"]
                    sh["kills"] += 1; self.events.append([tick, "kill", sh["id"], target["id"]])
            else:
                keep.append(b)
        self.bullets = keep
        zone = self.zone
        for a in ts:
            if not a["alive"]: continue
            if (a["x"] - zone["x"]) ** 2 + (a["y"] - zone["y"]) ** 2 > zone["r"] ** 2:
                a["hp"] -= 0.25 if a["module"] == "antizone" else 0.5
                if a["hp"] <= 0:
                    a["alive"] = False; a["hp_frac"] = 0.0; a["death"] = tick; a["zone_death"] = True
                    self.events.append([tick, "zone", None, a["id"]])
            if a["skill_t"] > 0:
                a["skill_t"] -= 1
                if a["skill_t"] == 0: a["shield"] = 0
            a["skill_cd"] = max(0, a["skill_cd"] - 1)
            a["skill_ready"] = a["module"] in MODULES and a["skill_cd"] <= 0
            a["skill_active"] = a["skill_t"] > 0
            a["stealthed"] = a["module"] == "stealth" and a["skill_active"]
            a["hp_frac"] = max(0, a["hp"]) / CHASSIS[a["chassis"]][5]
        self.steps = tick + 1
        self.tick += 1
        self._begin()

    def results(self):
        """One row per tank: alive, hp (share left), death step, kills, hits, shots, damage, taken, ... and, in a duel, the
        outcome "W" / "L" / "D"."""
        steps, rows = self.steps, []
        for a in self.tanks:
            rows.append(dict(slot=a["id"], chassis=a["chassis"], module=a["module"], alive=int(a["alive"]), hp=a["hp_frac"],
                             death=a["death"], steps=steps, kills=a["kills"], hits=a["hits"], shots=a["shots"],
                             damage=a["damage"], taken=a["taken"], skills=a["skills"], zone_death=int(a["zone_death"]),
                             threats=a["threats"], dodged=a["dodged"], struck=a["struck"], errors=a["errors"]))
        if len(rows) == 2:
            for r, o in zip(rows, duel_outcome(rows)): r["outcome"] = o
        return rows


def play(seed, loadouts, policies, mapname=None, replay=False):
    """Play a whole game. loadouts: [(chassis, module)]; policies: one per tank, objects with act(state) -> 5 ints (and
    optionally reset()). A policy that raises or returns a bad action idles that step (counted in "errors").
    Returns (rows, replay or None); a replay is the JSON the website's replay viewer plays."""
    game = Game(seed, loadouts, mapname)
    for pol in policies:
        if hasattr(pol, "reset"): pol.reset()
    frames = [] if replay else None
    while not game.over:
        if replay and game.tick % REPLAY_EVERY == 0: frames.append(game.frame())
        acts = []
        for i, a in enumerate(game.tanks):
            if not a["alive"]: acts.append(None); continue
            try:
                acts.append(valid_action(policies[i].act(game.state(i))))
            except Exception:
                acts.append(list(IDLE)); a["errors"] += 1
        game.step(acts)
    rows = game.results()
    rep = None
    if replay:
        frames.append(game.frame())
        rep = dict(game.head, steps=game.steps, frames=frames, events=game.events,
                   players=[dict(label=getattr(p, "label", type(p).__name__), chassis=c, module=m)
                            for p, (c, m) in zip(policies, loadouts)])
    return rows, rep
