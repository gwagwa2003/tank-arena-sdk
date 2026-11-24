import json
import math

import numpy as np
import pytest

from tank_arena import ChaserBot, Game, IdleBot, TankEnv, TurretBot, observation, play
from tank_arena.engine import IDLE, duel_outcome
from tank_arena.geometry import clearance, line_of_sight, ray_rect, visible_enemies, wrap


def test_wrap_and_rays():
    assert abs(wrap(3 * math.pi) - math.pi) < 1e-9 or abs(wrap(3 * math.pi) + math.pi) < 1e-9
    wall = dict(x=100, y=0, w=10, h=800)
    assert ray_rect(0, 400, 1, 0, wall) == 100
    assert ray_rect(0, 400, -1, 0, wall) == math.inf
    assert ray_rect(105, 400, 1, 0, wall) == 0                    # starting inside a wall
    assert clearance(400, 400, 0, []) == 400                      # to the arena edge
    assert not line_of_sight(0, 400, 200, 400, [wall]) and line_of_sight(0, 400, 50, 400, [wall])


def test_game_is_deterministic_and_complete():
    a = play(7, [("gunner", "shield"), ("scout", "stealth")], [ChaserBot(seed=1), ChaserBot(seed=2)], replay=True)
    b = play(7, [("gunner", "shield"), ("scout", "stealth")], [ChaserBot(seed=1), ChaserBot(seed=2)], replay=True)
    assert a == b
    rows, rep = a
    assert {r["outcome"] for r in rows} <= {"W", "L", "D"} and rows[0]["steps"] <= 1200
    assert rep["frames"][0][0] == 0 and rep["map"] in ("fort", "city") and len(rep["players"]) == 2
    json.dumps(rep)                                               # a replay is plain JSON


def test_idle_tanks_die_in_the_zone_or_draw():
    rows, _ = play(3, [("standard", "shield"), ("standard", "antizone")], [IdleBot(), IdleBot()])
    # antizone takes half damage outside the zone, so it outlives the other one (or both survive to a draw)
    assert rows[1]["outcome"] in ("W", "D")


def test_chaser_beats_idle_and_turret():
    for bot in (IdleBot, TurretBot):
        wins = sum(play(s, [("gunner", "shield")] * 2, [ChaserBot(seed=s), bot()])[0][0]["outcome"] == "W" for s in range(6))
        assert wins >= 5


def test_observation_layout():
    g = Game(1, [("gunner", "radar"), ("heavy", "shield")], mapname="fort")
    st = g.state(0)
    o = observation(st)
    assert o.shape == (91,) and o.dtype == np.float32 and np.all(np.isfinite(o))
    assert np.all((o[:32] > 0) & (o[:32] <= 1))                   # terrain rays
    assert o[76] == 1.0 and o[87] == 0.0 and o[88] == 0.25       # full HP, step 0, one enemy alive
    # the enemy starts 700 px away: out of sight
    assert o[32] == 0 and visible_enemies(st) == []


def test_bad_actions_count_as_errors():
    class Broken:
        def act(self, state): return [9, 9, 9, 9, 9]
    rows, _ = play(2, [("standard", "shield")] * 2, [Broken(), IdleBot()])
    assert rows[0]["errors"] > 0


def test_env_runs_a_game():
    env = TankEnv(ChaserBot(seed=3))
    obs, info = env.reset(seed=5)
    assert obs.shape == (91,)
    for _ in range(2000):
        obs, r, term, trunc, info = env.step(IDLE)
        if term or trunc: break
    assert (term or trunc) and info["outcome"] in ("W", "L", "D")


def test_duel_outcome_rules():
    alive = dict(alive=1, death=1200, hp=0.5); dead = dict(alive=0, death=300, hp=0.0)
    assert duel_outcome([alive, dead]) == ["W", "L"]
    assert duel_outcome([dict(alive=0, death=500, hp=0), dead]) == ["W", "L"]   # lasted longer
    assert duel_outcome([dict(alive=1, death=1200, hp=0.3), alive]) == ["L", "W"]
    assert duel_outcome([alive, dict(alive)]) == ["D", "D"]


torch = pytest.importorskip("torch")


def test_export_check_and_play(tmp_path):
    from tank_arena.agent import FrameStack, ModelPolicy, load_model
    from tank_arena.check import check_model
    from tank_arena.export import export_model
    net = torch.nn.Sequential(torch.nn.Linear(91 * 2, 32), torch.nn.ReLU(), torch.nn.Linear(32, 13))
    path = export_model(net, tmp_path / "m.pt", stack=2, mean=np.zeros(91), std=np.ones(91))
    _, cfg, _, _ = load_model(path)
    assert cfg["format"] == "tank-arena-v1" and cfg["stack"] == 2
    res = check_model(str(path), speed_limit_ms=1000, timed_steps=20)
    assert res["ok"], res
    rows, _ = play(1, [("gunner", "shield")] * 2, [ModelPolicy(path), IdleBot()])
    assert rows[0]["errors"] == 0
    fs = FrameStack(3); a = fs.push(np.ones(91)); b = fs.push(np.full(91, 2.0))
    assert a.shape == (273,) and np.all(b[:91] == 2) and np.all(b[91:] == 1)   # newest first, oldest repeated


def test_export_lstm(tmp_path):
    from tank_arena.agent import ModelPolicy
    from tank_arena.export import export_model

    class Net(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.lstm = torch.nn.LSTM(91, 16, 1); self.head = torch.nn.Linear(16, 13)

        def forward(self, x, h, c):
            y, (h, c) = self.lstm(x[None], (h, c))
            return self.head(y[0]), h, c

    path = export_model(Net(), tmp_path / "lstm.pt", recurrent=True, hidden=16, layers=1)
    rows, _ = play(1, [("gunner", "shield")] * 2, [ModelPolicy(path), IdleBot()])
    assert rows[0]["errors"] == 0


def test_stealth_blinks_and_stops_at_walls():
    import math
    from tank_arena.rules import BLINK, MAPS, TR, hits_rect

    class Script:
        def __init__(self, at): self.at, self.pos = at, {}
        def act(self, s):
            self.pos[s["t"]] = (s["self"]["x"], s["self"]["y"])
            return [2, 1, 1, 0, int(s["t"] == self.at)]
    pols = [Script(65), Script(65)]
    game = Game(1, [("standard", "stealth"), ("standard", "stealth")], mapname="fort")
    while not game.over and game.tick < 80:
        game.step([p.act(game.state(i)) for i, p in enumerate(pols)])
    walls = [dict(x=x, y=y, w=w, h=h) for x, y, w, h in MAPS["fort"]["rects"]]
    jumps = [math.dist(p.pos[65], p.pos[66]) for p in pols]
    assert max(jumps) > 40 and all(j <= BLINK + 1e-6 for j in jumps)
    assert all(not any(hits_rect(x, y, TR, w) for w in walls) for p in pols for x, y in p.pos.values())


def test_xray_sees_through_walls_one_way():
    from tank_arena.geometry import visible_enemies

    def tank(x, module, active=False):
        return dict(x=x, y=400, vx=0.0, vy=0.0, alive=True, stealthed=False, module=module, skill_active=active)
    wall = [dict(x=190, y=300, w=20, h=200)]
    sees = lambda me, foe: len(visible_enemies(dict(self=me, enemies=[foe], walls=wall)))
    assert sees(tank(100, "xray"), tank(300, "shield")) == 0
    assert sees(tank(100, "xray", True), tank(300, "shield")) == 1
    assert sees(tank(300, "shield"), tank(100, "xray", True)) == 0
