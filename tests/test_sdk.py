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
    a = play(7, [("gunner", "shield"), ("skirmisher", "backstep")], [ChaserBot(seed=1), ChaserBot(seed=2)], replay=True)
    b = play(7, [("gunner", "shield"), ("skirmisher", "backstep")], [ChaserBot(seed=1), ChaserBot(seed=2)], replay=True)
    assert a == b
    rows, rep = a
    assert {r["outcome"] for r in rows} <= {"W", "L", "D"} and rows[0]["steps"] <= 1200
    assert rep["frames"][0][0] == 0 and rep["map"] in ("fort", "city") and len(rep["players"]) == 2
    json.dumps(rep)                                               # a replay is plain JSON


def test_idle_tanks_die_in_the_zone_or_draw():
    rows, _ = play(3, [("gunner", "shield"), ("marksman", "radar")], [IdleBot(), IdleBot()])
    # nobody shoots: whoever is left outside the shrinking zone dies there (or both survive to a draw)
    assert sorted(r["outcome"] for r in rows) in (["D", "D"], ["L", "W"]) and all(r["taken"] == 0 for r in rows)
    assert all(r["zone_death"] for r in rows if r["outcome"] == "L")


def test_chaser_beats_idle_and_turret():
    for bot in (IdleBot, TurretBot):
        wins = sum(play(s, [("gunner", "shield")] * 2, [ChaserBot(seed=s), bot()])[0][0]["outcome"] == "W" for s in range(6))
        assert wins >= 5


def test_observation_layout():
    g = Game(1, [("gunner", "radar"), ("marksman", "shield")], mapname="fort")
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
    rows, _ = play(2, [("gunner", "shield")] * 2, [Broken(), IdleBot()])
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
    game = Game(1, [("gunner", "stealth"), ("gunner", "stealth")], mapname="fort")
    while not game.over and game.tick < 80:
        game.step([p.act(game.state(i)) for i, p in enumerate(pols)])
    walls = [dict(x=x, y=y, w=w, h=h) for x, y, w, h in MAPS["fort"]["rects"]]
    jumps = [math.dist(p.pos[65], p.pos[66]) for p in pols]
    assert max(jumps) > 40 and all(j <= BLINK + 1e-6 for j in jumps)
    assert all(not any(hits_rect(x, y, TR, w) for w in walls) for p in pols for x, y in p.pos.values())


def test_marksman_hits_for_18_and_a_shield_takes_a_whole_bullet(monkeypatch):
    from tank_arena import engine
    monkeypatch.setitem(engine.MAPS, "fort", dict(name="empty", rects=[]))   # the two spawns face each other, 700 px apart
    for module, struck in (("radar", 5), ("shield", 6)):
        game = Game(1, [("marksman", "radar"), ("gunner", module)], mapname="fort")
        while not game.over:                                # the marksman closes 40 steps to get in range, then stands
            game.step([[0 if game.tick < 40 else 2, 1, 1, 1, 0], [2, 1, 1, 0, int(game.tick >= 55)]])
        victim = game.tanks[1]
        assert not victim["alive"] and victim["struck"] == struck and victim["taken"] == 5 * 18   # 90 HP: 5 hits


def test_backstep_and_focus(monkeypatch):
    from tank_arena import engine
    monkeypatch.setitem(engine.MAPS, "fort", dict(name="empty", rects=[]))
    game = Game(1, [("skirmisher", "backstep"), ("marksman", "focus")], mapname="fort")
    pos, bspd = {}, {}
    while game.tick < 110:
        pos[game.tick] = [(t["x"], t["y"]) for t in game.tanks]; bspd[game.tick] = game.tanks[1]["bspd_now"]
        game.step([[2, 1, 1, 0, int(game.tick == 60)], [0, 1, 1, 0, int(game.tick == 60)]])
    hop = {t: math.dist(pos[t + 1][0], pos[t][0]) for t in range(55, 66)}
    assert abs(hop[61] - 24) < 1e-6 and all(hop[t] < 1e-9 for t in hop if t != 61)        # the step after pressing
    (x0, y0), (x1, y1) = pos[61][0], pos[62][0]
    t0 = game.tanks[0]["turret"]
    assert abs(wrap(math.atan2(y0 - y1, x0 - x1) - t0)) < 1e-6                           # straight away from the turret
    assert bspd[60] == 11 and all(bspd[t] == 14 for t in range(61, 101)) and bspd[101] == 11
    v = lambda t: math.dist(pos[t + 1][1], pos[t][1])
    assert abs(v(50) - 2.8) < 1e-6 and abs(v(70) - 2.8 * 0.78) < 1e-6


def test_shotgun_hits_hardest_up_close(monkeypatch):
    from tank_arena import engine
    monkeypatch.setitem(engine.MAPS, "fort", dict(name="empty", rects=[]))
    taken = {}
    for gap in (50, 250):                                   # point-blank: all three at 14; far: only the middle one, at 7
        game = Game(1, [("shotgun", "radar"), ("marksman", "radar")], mapname="fort")
        a, b = game.tanks
        a.update(x=300.0, y=400.0, heading=0.0, turret=0.0, cooldown=0); b.update(x=300.0 + gap, y=400.0)
        for _ in range(30):
            game.step([[2, 1, 1, int(game.tick == 0), 0], [2, 1, 1, 0, 0]])
        taken[gap] = b["taken"]
    assert taken == {50: 42, 250: 7}
