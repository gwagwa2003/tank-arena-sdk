"""The game: exact v3_final rules and physics matching the Tank Arena server."""
import math
import random

from .geometry import wrap
from .rules import (
    ACCEL_FWD,
    ACCEL_REV,
    ARENA,
    ARMOR_ENABLED,
    ARMOR_FRONT_HALF,
    ARMOR_FRONT_MULT,
    ARMOR_REAR_HALF,
    ARMOR_REAR_MULT,
    ARMOR_SIDE_MULT,
    BACKSTEP,
    BACKSTEP_DASH_MODE,
    BLINK,
    BUSH_FIRE_REVEAL_STEPS,
    BUSHES_ENABLED,
    CHASSIS,
    CORE_CAPTURE_STEPS,
    CORE_CD_REFUND_FRAC,
    CORE_HEAL_FRAC,
    CORE_RADIUS,
    CORE_SPAWN_1,
    CORE_SPAWN_2,
    CORE_WARN_STEPS,
    DAMAGE,
    DECEL_DRAG,
    DESTRUCTIBLE_COVER_ENABLED,
    FOCUS_BSPD_MULT,
    FOCUS_DMG_MULT,
    FOCUS_MOVE,
    HEAT_COOL_PER_STEP,
    HEAT_ENABLED,
    HEAT_MAX_BLOOM,
    HEAT_OVERHEAT_LOCK,
    HEAT_PER_SHOT,
    HEAT_SPREAD_THRESH,
    INERTIA_ENABLED,
    INIT_COOLDOWN,
    INIT_SKILL_CD,
    MAPS,
    MODULES,
    OVERDRIVE,
    POWER_CORE_ENABLED,
    PROC_MAPS_ENABLED,
    RADAR_ARMOR_PIERCE,
    RULES_VERSION,
    SHIELD_ABSORB,
    SHIELD_ARC_HALF,
    SHIELD_MOVE_MULT,
    SHOT_FALLOFF,
    SHOT_N,
    SHOT_SPREAD,
    SIEGE_BSPD,
    SIEGE_RELOAD,
    SIEGE_WAIT,
    SMOKE_R,
    SOUND_ANGLE_NOISE,
    SOUND_CUES_ENABLED,
    STEPS,
    TR,
    TROT,
    TURN_SPEED_MULT,
    ZONE_DPS,
    ZONE_END,
    ZONE_R_END,
    ZONE_R_START,
    ZONE_START,
    generate_proc_map,
    hits_rect,
    map_seed_from_episode_seed,
    pick_core_spots,
    rect_alive,
)

IDLE = [2, 1, 1, 0, 0]
ACTION_SIZES = (3, 3, 3, 2, 2)
REPLAY_EVERY = 2


def valid_action(act):
    """5 ints within ACTION_SIZES, or ValueError."""
    act = [int(v) for v in act]
    if len(act) != 5 or not all(0 <= v < k for v, k in zip(act, ACTION_SIZES)):
        raise ValueError(f"bad action {act}")
    return act


def duel_outcome(rows):
    """1v1 result of each row: 'W', 'L' or 'D'."""
    def key(r):
        return (r["alive"], r["death"], round(r["hp"], 6) if r["alive"] else 0.0)

    ka, kb = key(rows[0]), key(rows[1])
    if ka == kb:
        return ["D", "D"]
    return ["W", "L"] if ka > kb else ["L", "W"]


class Game:
    """One v3_final game, played step by step."""

    def __init__(self, seed, loadouts, mapname=None):
        rng = random.Random(seed)
        n = len(loadouts)
        picked = rng.choice(["fort", "city"])
        map_seed = map_seed_from_episode_seed(seed)
        if mapname is None and PROC_MAPS_ENABLED or mapname == "proc":
            self.mapname = "proc"
            self.walls, self.bushes, self.core_x1, self.core_y1, self.core_x2, self.core_y2 = generate_proc_map(map_seed)
        else:
            self.mapname = mapname or picked
            self.walls = [
                dict(x=x, y=y, w=w, h=h, destructible=0, hp=0.0, max_hp=0.0)
                for x, y, w, h in MAPS[self.mapname]["rects"]
            ]
            self.bushes = []
            self.core_x1, self.core_y1, self.core_x2, self.core_y2 = pick_core_spots(self.walls, int(map_seed & 1))

        self.zone = dict(x=rng.uniform(320, 480), y=rng.uniform(320, 480), r=ZONE_R_START)
        spots = list(range(n))
        rng.shuffle(spots)
        self.tanks = []
        for i, (c, m) in enumerate(loadouts):
            if c not in CHASSIS:
                raise ValueError(f"unknown chassis {c!r}")
            spd, rot, reload, bspd, blife, maxhp = CHASSIS[c]
            ang = -math.pi / 2 + spots[i] * 2 * math.pi / n
            x, y = 400.0 + 350.0 * math.cos(ang), 400.0 + 350.0 * math.sin(ang)
            hd = math.atan2(400.0 - y, 400.0 - x)
            self.tanks.append(
                dict(
                    id=i,
                    x=x,
                    y=y,
                    vx=0.0,
                    vy=0.0,
                    v_cur=0.0,
                    heading=hd,
                    turret=hd,
                    hp=maxhp,
                    hp_frac=1.0,
                    chassis=c,
                    module=m,
                    cooldown=INIT_COOLDOWN,
                    skill_ready=False,
                    skill_active=False,
                    stealthed=False,
                    alive=True,
                    skill_cd=INIT_SKILL_CD,
                    skill_t=0,
                    shield=0.0,
                    heat=0.0,
                    overheat_t=0,
                    dash_dir=0.0,
                    sound_ang=0.0,
                    sound_age=999,
                    sound_type=0,
                    fire_reveal_t=0,
                    cores_captured=0,
                    covers_broken=0,
                    kills=0,
                    hits=0,
                    shots=0,
                    damage=0.0,
                    taken=0.0,
                    zone_death=False,
                    death=STEPS,
                    skills=0,
                    errors=0,
                    killer=None,
                    threats=0,
                    dodged=0,
                    struck=0,
                    front_hits=0,
                    side_hits=0,
                    rear_hits=0,
                    overheats=0,
                    still=0,
                    sieged=False,
                    bspd_now=bspd,
                )
            )
        self.bullets = []
        self.smokes = []
        self.tick = 0
        self.steps = 0
        self.over = False
        self.events = []
        self._uid = 0
        self._near_seen = set()
        self.core_idx = 0
        self.core_state = 0
        self.core_x = 400.0
        self.core_y = 400.0
        self.core_prog = 0
        self._dest_indices = [idx for idx, w in enumerate(self.walls) if w["destructible"]]
        self._begin()

    @property
    def head(self):
        return dict(
            map=self.mapname,
            rules=RULES_VERSION,
            walls=[[w["x"], w["y"], w["w"], w["h"], w["destructible"]] for w in self.walls],
            bushes=[[b["x"], b["y"], b["r"]] for b in self.bushes],
            zone=[self.zone["x"], self.zone["y"]],
            every=REPLAY_EVERY,
        )

    def _begin(self):
        if sum(a["alive"] for a in self.tanks) <= 1 or self.tick >= STEPS:
            self.over = True
            return
        t = self.tick
        if t < ZONE_START:
            self.zone["r"] = ZONE_R_START
        else:
            span = max(1, ZONE_END - ZONE_START)
            self.zone["r"] = max(ZONE_R_END, ZONE_R_START - (t - ZONE_START) * (ZONE_R_START - ZONE_R_END) / span)
        if POWER_CORE_ENABLED and self.core_idx < 2:
            spawn_t = CORE_SPAWN_1 if self.core_idx == 0 else CORE_SPAWN_2
            warn_t = spawn_t - CORE_WARN_STEPS
            if self.core_state == 0 and t >= warn_t:
                self.core_state = 1
                self.core_x, self.core_y = (self.core_x1, self.core_y1) if self.core_idx == 0 else (self.core_x2, self.core_y2)
                self.core_prog = 0
            if self.core_state == 1 and t >= spawn_t:
                self.core_state = 2

    def state(self, i):
        a = self.tanks[i]
        return dict(
            t=self.tick,
            self=a,
            enemies=[b for b in self.tanks if b is not a],
            bullets=[dict(x=b["x"], y=b["y"], vx=b["vx"], vy=b["vy"], own=False) for b in self.bullets if b["owner"] != i],
            zone=self.zone,
            walls=self.walls,
            bushes=self.bushes,
            core_idx=self.core_idx,
            core_state=self.core_state,
            core_x=self.core_x,
            core_y=self.core_y,
            core_prog=self.core_prog,
            smokes=self.smokes,
        )

    def frame(self):
        return [
            self.tick if not self.over else self.steps,
            round(self.zone["r"], 1),
            [
                [
                    round(a["x"], 1),
                    round(a["y"], 1),
                    round(a["heading"], 3),
                    round(a["turret"], 3),
                    round(a["hp_frac"], 3),
                    int(a["alive"]),
                    int(a["skill_active"]),
                    round(a["shield"], 1),
                    int(a["sieged"]),
                    round(a["heat"] / 100.0, 2),
                    int(a["overheat_t"] > 0),
                ]
                for a in self.tanks
            ],
            [[round(b["x"], 1), round(b["y"], 1), b["owner"]] for b in self.bullets],
            [[round(s["x"], 1), round(s["y"], 1), s["r"], s["t"]] for s in self.smokes],
            [
                [
                    round(self.walls[wi]["hp"] / self.walls[wi]["max_hp"], 2) if self.walls[wi]["max_hp"] > 0 else 0.0
                    for wi in self._dest_indices
                ],
                [self.core_state, round(self.core_x, 1), round(self.core_y, 1), self.core_prog],
            ],
        ]

    def _free(self, x, y, i):
        return (
            TR < x < ARENA - TR
            and TR < y < ARENA - TR
            and not any(rect_alive(w) and hits_rect(x, y, TR, w) for w in self.walls)
            and all(not o["alive"] or o["id"] == i or (o["x"] - x) ** 2 + (o["y"] - y) ** 2 >= 4.0 * TR * TR for o in self.tanks)
        )

    def _emit_sound(self, shooter, receiver, event_type):
        if not receiver["alive"]:
            return
        hval = ((self.tick * 131 + shooter["id"] * 17 + event_type * 997 + self._uid) * 2654435761) & 0xFFFFFFFF
        u = (hval / 2147483648.0) - 1.0
        receiver["sound_ang"] = wrap(math.atan2(shooter["y"] - receiver["y"], shooter["x"] - receiver["x"]) + u * SOUND_ANGLE_NOISE)
        receiver["sound_age"] = 0
        receiver["sound_type"] = event_type

    def step(self, actions):
        if self.over:
            raise RuntimeError("the game is over")
        tick, ts = self.tick, self.tanks
        acts = []
        for a, act in zip(ts, actions):
            if not a["alive"]:
                acts.append(None)
                continue
            try:
                acts.append(valid_action(act))
            except Exception:
                acts.append(list(IDLE))
                a["errors"] += 1

        for a, act in zip(ts, acts):
            if not a["alive"]:
                continue
            a["sound_age"] = min(999, a["sound_age"] + 1)
            a["fire_reveal_t"] = max(0, a["fire_reveal_t"] - 1)
            c = a["chassis"]
            spd, rot, reload, bspd, blife, _ = CHASSIS[c]
            m = a["module"]
            just = False

            if m in MODULES and act[4] == 1 and a["skill_cd"] <= 0:
                a["skill_t"], a["skill_cd"] = MODULES[m]
                just = True
                a["skills"] += 1
                if m == "shield":
                    a["shield"] = SHIELD_ABSORB
                if m == "smoke":
                    self.smokes.append(dict(x=a["x"], y=a["y"], r=SMOKE_R, t=MODULES["smoke"][0]))
                if m == "stealth":
                    d = a["heading"] + (math.pi if act[0] == 1 else 0.0)
                    for _ in range(int(BLINK) // 4):
                        tx, ty = a["x"] + math.cos(d) * 4.0, a["y"] + math.sin(d) * 4.0
                        if not self._free(tx, ty, a["id"]):
                            break
                        a["x"], a["y"] = tx, ty
                if m == "backstep" and BACKSTEP_DASH_MODE == 1:
                    if act[0] == 0:
                        a["dash_dir"] = a["heading"]
                    elif act[0] == 1:
                        a["dash_dir"] = a["heading"] + math.pi
                    else:
                        a["dash_dir"] = a["turret"] + (math.pi / 2.0 if act[1] == 2 else -math.pi / 2.0)
                if SOUND_CUES_ENABLED and m in ("stealth", "radar"):
                    for o in ts:
                        if o is not a:
                            self._emit_sound(a, o, 2)

            dashing = m == "backstep" and BACKSTEP_DASH_MODE == 1 and a["skill_t"] > 0
            if m == "backstep" and BACKSTEP_DASH_MODE == 0 and a["skill_t"] == 1:
                for _ in range(int(BACKSTEP) // 4):
                    tx, ty = a["x"] - math.cos(a["turret"]) * 4.0, a["y"] - math.sin(a["turret"]) * 4.0
                    if not self._free(tx, ty, a["id"]):
                        break
                    a["x"], a["y"] = tx, ty

            a["heading"] = wrap(a["heading"] + (act[1] - 1) * rot)
            ox, oy = a["x"], a["y"]

            if dashing:
                step_dist = BACKSTEP / max(1, MODULES["backstep"][0])
                n_chunks = int(step_dist // 4.0)
                rem = step_dist - n_chunks * 4.0
                d_ang = a["dash_dir"]
                blocked = False
                for _ in range(n_chunks):
                    tx, ty = a["x"] + math.cos(d_ang) * 4.0, a["y"] + math.sin(d_ang) * 4.0
                    if not self._free(tx, ty, a["id"]):
                        blocked = True
                        break
                    a["x"], a["y"] = tx, ty
                if not blocked and rem > 1e-6:
                    tx, ty = a["x"] + math.cos(d_ang) * rem, a["y"] + math.sin(d_ang) * rem
                    if self._free(tx, ty, a["id"]):
                        a["x"], a["y"] = tx, ty
                a["vx"], a["vy"] = a["x"] - ox, a["y"] - oy
                a["v_cur"] = 0.0
            else:
                v_target = spd * (1.0 if act[0] == 0 else -0.6 if act[0] == 1 else 0.0)
                if INERTIA_ENABLED and act[1] != 1:
                    v_target *= TURN_SPEED_MULT
                if m == "focus" and a["skill_t"] > 0:
                    v_target *= FOCUS_MOVE
                if m == "shield" and a["skill_t"] > 0 and a["shield"] > 0.0:
                    v_target *= SHIELD_MOVE_MULT

                if INERTIA_ENABLED:
                    vc = a["v_cur"]
                    if abs(vc) < 1e-9:
                        vc = 0.0
                    if v_target == 0.0 or (v_target * vc < -1e-9) or abs(v_target) < abs(vc):
                        lim = DECEL_DRAG
                    elif v_target > 0.0:
                        lim = ACCEL_FWD
                    else:
                        lim = ACCEL_REV
                    lim *= spd / 3.0
                    diff = v_target - vc
                    if abs(diff) <= lim:
                        v = v_target
                    else:
                        v = vc + (lim if diff > 0.0 else -lim)
                    a["v_cur"] = v
                else:
                    v = v_target

                nx, ny = ox + math.cos(a["heading"]) * v, oy + math.sin(a["heading"]) * v
                if v != 0.0:
                    if self._free(nx, ny, a["id"]):
                        a["x"], a["y"] = nx, ny
                    elif self._free(nx, oy, a["id"]):
                        a["x"] = nx
                    elif self._free(ox, ny, a["id"]):
                        a["y"] = ny
                a["vx"], a["vy"] = a["x"] - ox, a["y"] - oy
                if INERTIA_ENABLED:
                    vc_new = a["vx"] * math.cos(a["heading"]) + a["vy"] * math.sin(a["heading"])
                    a["v_cur"] = 0.0 if abs(vc_new) < 1e-9 else vc_new

            a["still"] = a["still"] + 1 if abs(a["vx"]) + abs(a["vy"]) < 0.05 else 0
            a["sieged"] = c == "siege" and a["still"] >= SIEGE_WAIT
            if a["sieged"]:
                reload, bspd = SIEGE_RELOAD, SIEGE_BSPD
            if m == "overdrive" and a["skill_t"] > 0:
                reload = round(reload * OVERDRIVE)

            dmg_mult = 1.0
            if m == "focus" and a["skill_t"] > 0:
                bspd = bspd * FOCUS_BSPD_MULT
                dmg_mult = FOCUS_DMG_MULT
            a["bspd_now"] = bspd

            trot_m = {"gunner": 1.0, "shotgun": 0.95, "skirmisher": 1.05, "marksman": 0.82}.get(c, 1.0)
            a["turret"] = wrap(a["turret"] + (act[2] - 1) * TROT * trot_m)
            a["cooldown"] = max(0, a["cooldown"] - 1)

            if HEAT_ENABLED:
                if a["overheat_t"] > 0:
                    a["overheat_t"] -= 1
                    a["heat"] = max(0.0, a["heat"] - 100.0 / max(1, HEAT_OVERHEAT_LOCK))
                else:
                    a["heat"] = max(0.0, a["heat"] - HEAT_COOL_PER_STEP)

            if (
                act[3] == 1
                and not a["cooldown"]
                and not (just and m == "stealth")
                and not dashing
                and a["overheat_t"] == 0
            ):
                k = SHOT_N if c == "shotgun" else 1
                spread = SHOT_SPREAD if c == "shotgun" else 0.0
                for q in range(k):
                    self._uid += 1
                    bloom = 0.0
                    if HEAT_ENABLED and a["heat"] > HEAT_SPREAD_THRESH:
                        u = (((self._uid * 2654435761) & 0xFFFFFFFF) / 2147483648.0) - 1.0
                        frac_h = (a["heat"] - HEAT_SPREAD_THRESH) / max(1e-6, 100.0 - HEAT_SPREAD_THRESH)
                        bloom = u * HEAT_MAX_BLOOM * frac_h
                    ang = a["turret"] + (q - (k - 1) / 2.0) * spread + bloom
                    pierce_armor = m == "radar" and a["skill_t"] > 0 and RADAR_ARMOR_PIERCE
                    self.bullets.append(
                        dict(
                            uid=self._uid,
                            x=a["x"] + math.cos(ang) * 24.0,
                            y=a["y"] + math.sin(ang) * 24.0,
                            vx=math.cos(ang) * bspd,
                            vy=math.sin(ang) * bspd,
                            owner=a["id"],
                            life=blife,
                            dmg=DAMAGE[c],
                            dmg_mult=dmg_mult,
                            life0=blife,
                            fall=SHOT_FALLOFF if c == "shotgun" else None,
                            pierce_armor=pierce_armor,
                        )
                    )
                a["cooldown"] = reload
                a["shots"] += k
                if m == "stealth":
                    a["skill_t"] = 0
                if HEAT_ENABLED:
                    a["heat"] += HEAT_PER_SHOT.get(c, 16.5)
                    if a["heat"] >= 100.0:
                        a["heat"] = 100.0
                        a["overheat_t"] = HEAT_OVERHEAT_LOCK
                        a["overheats"] += 1
                if BUSHES_ENABLED:
                    a["fire_reveal_t"] = BUSH_FIRE_REVEAL_STEPS
                if SOUND_CUES_ENABLED:
                    for o in ts:
                        if o is not a:
                            self._emit_sound(a, o, 1)

        keep = []
        for b in self.bullets:
            b["x"] += b["vx"]
            b["y"] += b["vy"]
            b["life"] -= 1
            x, y = b["x"], b["y"]
            if not (0.0 < x < ARENA and 0.0 < y < ARENA and b["life"] > 0):
                continue
            hit_w = None
            for w in self.walls:
                if rect_alive(w) and w["x"] <= x <= w["x"] + w["w"] and w["y"] <= y <= w["y"] + w["h"]:
                    hit_w = w
                    break
            if hit_w is not None:
                if DESTRUCTIBLE_COVER_ENABLED and hit_w["destructible"] and hit_w["hp"] > 0.0:
                    cdmg = (b["fall"][0] if b["fall"] else b["dmg"]) * b["dmg_mult"]
                    hit_w["hp"] -= cdmg
                    if hit_w["hp"] <= 0.0:
                        hit_w["hp"] = 0.0
                        ts[b["owner"]]["covers_broken"] += 1
                continue

            target = None
            for a in ts:
                if not a["alive"] or a["id"] == b["owner"]:
                    continue
                d2 = (a["x"] - x) ** 2 + (a["y"] - y) ** 2
                if d2 < 1600.0 and (b["uid"], a["id"]) not in self._near_seen:
                    self._near_seen.add((b["uid"], a["id"]))
                    a["threats"] += 1
                    a["dodged"] += 1
                if d2 < 256.0 and target is None:
                    target = a

            if target:
                sh = ts[b["owner"]]
                sh["hits"] += 1
                target["struck"] += 1
                target["dodged"] -= 1
                raw = b["dmg"]
                if b["fall"]:
                    near, far, s1, s2 = b["fall"]
                    age = b["life0"] - b["life"]
                    raw = near if age <= s1 else far if age >= s2 else round(near + (far - near) * (age - s1) / (s2 - s1))
                raw *= b["dmg_mult"]

                impact_ang = math.atan2(-b["vy"], -b["vx"])
                if ARMOR_ENABLED:
                    rel = abs(wrap(impact_ang - target["heading"]))
                    if rel <= ARMOR_FRONT_HALF:
                        if not b.get("pierce_armor", False):
                            raw *= ARMOR_FRONT_MULT
                        target["front_hits"] += 1
                    elif rel >= ARMOR_REAR_HALF:
                        raw *= ARMOR_REAR_MULT
                        target["rear_hits"] += 1
                    else:
                        raw *= ARMOR_SIDE_MULT
                        target["side_hits"] += 1

                in_arc = abs(wrap(impact_ang - target["turret"])) <= SHIELD_ARC_HALF
                if target["shield"] > 0.0 and in_arc:
                    absorbed = min(target["shield"], raw)
                    dmg = raw - absorbed
                    target["shield"] -= absorbed
                else:
                    dmg = raw

                target["hp"] -= dmg
                target["taken"] += dmg
                sh["damage"] += dmg
                if target["hp"] <= 0.0 and target["alive"]:
                    target["alive"] = False
                    target["hp_frac"] = 0.0
                    target["death"] = tick
                    target["killer"] = sh["id"]
                    sh["kills"] += 1
                    self.events.append([tick, "kill", sh["id"], target["id"]])
            else:
                keep.append(b)
        self.bullets = keep

        zone = self.zone
        for a in ts:
            if not a["alive"]:
                continue
            if (a["x"] - zone["x"]) ** 2 + (a["y"] - zone["y"]) ** 2 > zone["r"] ** 2:
                a["hp"] -= 0.25 if a["module"] == "antizone" else ZONE_DPS
                if a["hp"] <= 0.0:
                    a["alive"] = False
                    a["hp_frac"] = 0.0
                    a["death"] = tick
                    a["zone_death"] = True
                    self.events.append([tick, "zone", None, a["id"]])
            if a["skill_t"] > 0:
                a["skill_t"] -= 1
                if a["skill_t"] == 0:
                    a["shield"] = 0.0
            a["skill_cd"] = max(0, a["skill_cd"] - 1)
            a["skill_ready"] = a["module"] in MODULES and a["skill_cd"] <= 0
            a["skill_active"] = a["skill_t"] > 0
            a["stealthed"] = a["module"] == "stealth" and a["skill_active"]
            a["hp_frac"] = max(0.0, a["hp"]) / CHASSIS[a["chassis"]][5]

        if POWER_CORE_ENABLED and self.core_state == 2 and len(ts) == 2:
            r2 = CORE_RADIUS * CORE_RADIUS
            in0 = ts[0]["alive"] and ((ts[0]["x"] - self.core_x) ** 2 + (ts[0]["y"] - self.core_y) ** 2 <= r2)
            in1 = ts[1]["alive"] and ((ts[1]["x"] - self.core_x) ** 2 + (ts[1]["y"] - self.core_y) ** 2 <= r2)
            if in0 and not in1:
                self.core_prog += 2 if self.core_prog < 0 else 1
            elif in1 and not in0:
                self.core_prog -= 2 if self.core_prog > 0 else 1
            elif not in0 and not in1:
                if self.core_prog > 0:
                    self.core_prog -= 1
                elif self.core_prog < 0:
                    self.core_prog += 1
            if abs(self.core_prog) >= CORE_CAPTURE_STEPS:
                cap = ts[0] if self.core_prog > 0 else ts[1]
                maxhp_c = CHASSIS[cap["chassis"]][5]
                cap["hp"] = min(maxhp_c, cap["hp"] + maxhp_c * CORE_HEAL_FRAC)
                cap["hp_frac"] = max(0.0, cap["hp"]) / maxhp_c
                m_cd = MODULES[cap["module"]][1] if cap["module"] in MODULES else 0
                cap["skill_cd"] = max(0, cap["skill_cd"] - int(m_cd * CORE_CD_REFUND_FRAC))
                cap["skill_ready"] = cap["module"] in MODULES and cap["skill_cd"] <= 0
                cap["heat"] = 0.0
                cap["overheat_t"] = 0
                cap["cores_captured"] += 1
                self.events.append([tick, "core", cap["id"], self.core_idx])
                self.core_state = 0
                self.core_prog = 0
                self.core_idx += 1

        for s in self.smokes:
            s["t"] -= 1
        self.smokes[:] = [s for s in self.smokes if s["t"] > 0]
        self.steps = tick + 1
        self.tick += 1
        self._begin()

    def results(self):
        steps, rows = self.steps, []
        for a in self.tanks:
            rows.append(
                dict(
                    slot=a["id"],
                    chassis=a["chassis"],
                    module=a["module"],
                    alive=int(a["alive"]),
                    hp=a["hp_frac"],
                    death=a["death"],
                    steps=steps,
                    kills=a["kills"],
                    hits=a["hits"],
                    shots=a["shots"],
                    damage=a["damage"],
                    taken=a["taken"],
                    skills=a["skills"],
                    zone_death=int(a["zone_death"]),
                    threats=a["threats"],
                    dodged=a["dodged"],
                    struck=a["struck"],
                    front_hits=a["front_hits"],
                    side_hits=a["side_hits"],
                    rear_hits=a["rear_hits"],
                    overheats=a["overheats"],
                    cores_captured=a["cores_captured"],
                    covers_broken=a["covers_broken"],
                    errors=a["errors"],
                )
            )
        if len(rows) == 2:
            for r, o in zip(rows, duel_outcome(rows)):
                r["outcome"] = o
        return rows


def play(seed, loadouts, policies, mapname=None, replay=False):
    """Play a whole game and return (rows, replay or None)."""
    game = Game(seed, loadouts, mapname)
    for pol in policies:
        if hasattr(pol, "reset"):
            pol.reset()
    frames = [] if replay else None
    while not game.over:
        if replay and game.tick % REPLAY_EVERY == 0:
            frames.append(game.frame())
        acts = []
        for i, a in enumerate(game.tanks):
            if not a["alive"]:
                acts.append(None)
                continue
            try:
                acts.append(valid_action(policies[i].act(game.state(i))))
            except Exception:
                acts.append(list(IDLE))
                a["errors"] += 1
        game.step(acts)
    rows = game.results()
    rep = None
    if replay:
        frames.append(game.frame())
        rep = dict(
            game.head,
            steps=game.steps,
            frames=frames,
            events=game.events,
            players=[dict(label=getattr(p, "label", type(p).__name__), chassis=c, module=m) for p, (c, m) in zip(policies, loadouts)],
        )
    return rows, rep
