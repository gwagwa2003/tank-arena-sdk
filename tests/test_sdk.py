import json
import math
from pathlib import Path
import sys

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
    assert ray_rect(105, 400, 1, 0, wall) == 0  # starting inside a wall
    assert clearance(400, 400, 0, []) == 400  # to the arena edge
    assert not line_of_sight(0, 400, 200, 400, [wall]) and line_of_sight(0, 400, 50, 400, [wall])


def test_game_is_deterministic_and_complete():
    a = play(7, [("gunner", "shield"), ("skirmisher", "backstep")], [ChaserBot(seed=1), ChaserBot(seed=2)], replay=True)
    b = play(7, [("gunner", "shield"), ("skirmisher", "backstep")], [ChaserBot(seed=1), ChaserBot(seed=2)], replay=True)
    assert a == b
    rows, rep = a
    assert {r["outcome"] for r in rows} <= {"W", "L", "D"} and rows[0]["steps"] <= 1200
    assert rep["frames"][0][0] == 0 and rep["map"] == "proc" and rep["rules"] == "v3_final" and len(rep["players"]) == 2
    assert len(rep["bushes"]) >= 4 and any(w[4] == 1 for w in rep["walls"])
    json.dumps(rep)


def test_idle_tanks_die_in_the_zone_or_draw():
    rows, _ = play(3, [("gunner", "shield"), ("marksman", "radar")], [IdleBot(), IdleBot()])
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
    assert o.shape == (118,) and o.dtype == np.float32 and np.all(np.isfinite(o))
    assert np.all((o[:32] > 0) & (o[:32] <= 1))
    assert o[76] == 1.0 and o[87] == 0.0 and o[88] == 0.25
    assert o[32] == 0 and visible_enemies(st) == []


def test_bad_actions_count_as_errors():
    class Broken:
        def act(self, state):
            return [9, 9, 9, 9, 9]

    rows, _ = play(2, [("gunner", "shield")] * 2, [Broken(), IdleBot()])
    assert rows[0]["errors"] > 0


def test_env_runs_a_game():
    env = TankEnv(ChaserBot(seed=3))
    obs, info = env.reset(seed=5)
    assert obs.shape == (118,)
    for _ in range(2000):
        obs, r, term, trunc, info = env.step(IDLE)
        if term or trunc:
            break
    assert (term or trunc) and info["outcome"] in ("W", "L", "D")


def test_duel_outcome_rules():
    alive = dict(alive=1, death=1200, hp=0.5)
    dead = dict(alive=0, death=300, hp=0.0)
    assert duel_outcome([alive, dead]) == ["W", "L"]
    assert duel_outcome([dict(alive=0, death=500, hp=0), dead]) == ["W", "L"]
    assert duel_outcome([dict(alive=1, death=1200, hp=0.3), alive]) == ["L", "W"]
    assert duel_outcome([alive, dict(alive)]) == ["D", "D"]


torch = pytest.importorskip("torch")


def test_export_check_and_play(tmp_path):
    from tank_arena.agent import FrameStack, ModelPolicy, load_model
    from tank_arena.check import check_model
    from tank_arena.export import export_model

    net = torch.nn.Sequential(torch.nn.Linear(118 * 2, 32), torch.nn.ReLU(), torch.nn.Linear(32, 13))
    path = export_model(net, tmp_path / "m.pt", stack=2, mean=np.zeros(118), std=np.ones(118))
    _, cfg, _, _ = load_model(path)
    assert cfg["format"] == "tank-arena-v3" and cfg["stack"] == 2
    res = check_model(str(path), speed_limit_ms=1000, timed_steps=20)
    assert res["ok"], res
    rows, _ = play(1, [("gunner", "shield")] * 2, [ModelPolicy(path), IdleBot()])
    assert rows[0]["errors"] == 0
    fs = FrameStack(3)
    a = fs.push(np.ones(118))
    b = fs.push(np.full(118, 2.0))
    assert a.shape == (354,) and np.all(b[:118] == 2) and np.all(b[118:] == 1)


def test_export_lstm_gru_and_v1_compat(tmp_path):
    from tank_arena.agent import FORMAT_V1, ModelPolicy
    from tank_arena.check import check_model
    from tank_arena.export import export_model

    class LstmNet(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.lstm = torch.nn.LSTM(118, 16, 1)
            self.head = torch.nn.Linear(16, 13)

        def forward(self, x, h, c):
            y, (h, c) = self.lstm(x[None], (h, c))
            return self.head(y[0]), h, c

    p_lstm = export_model(LstmNet(), tmp_path / "lstm.pt", recurrent=True, rnn="lstm", hidden=16, layers=1)
    rows, _ = play(1, [("gunner", "shield")] * 2, [ModelPolicy(p_lstm), IdleBot()])
    assert rows[0]["errors"] == 0

    class Gru2ArgNet(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.gru = torch.nn.GRU(118 * 2, 16, 1)
            self.head = torch.nn.Linear(16, 13)

        def forward(self, x, h):
            y, h2 = self.gru(x[None], h)
            return self.head(y[0]), h2

    p_gru = export_model(Gru2ArgNet(), tmp_path / "gru_s2.pt", recurrent=True, rnn="gru", hidden=16, layers=1, stack=2)
    res_g = check_model(str(p_gru), speed_limit_ms=1000, timed_steps=20)
    assert res_g["ok"] and res_g["summary"]["rnn"] == "GRU" and res_g["summary"]["stack"] == 2

    v1_net = torch.nn.Sequential(torch.nn.Linear(91, 32), torch.nn.ReLU(), torch.nn.Linear(32, 13))
    p_v1 = export_model(v1_net, tmp_path / "legacy_v1.pt", format=FORMAT_V1, stack=1)
    res_v1 = check_model(str(p_v1), speed_limit_ms=1000, timed_steps=20)
    assert res_v1["ok"] and res_v1["summary"]["obs_size"] == 91
    rows_mix, _ = play(2, [("gunner", "radar"), ("gunner", "shield")], [ModelPolicy(p_gru), ModelPolicy(p_v1)])
    assert rows_mix[0]["errors"] == 0 and rows_mix[1]["errors"] == 0

    # Stateless Transformer (stack=8) + stateful ring-buffer Transformer (layers=8, hidden=64, stack=2)
    class TransformerNet(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.proj = torch.nn.Linear(118, 32)
            self.enc = torch.nn.TransformerEncoderLayer(d_model=32, nhead=4, dim_feedforward=64, batch_first=True)
            self.head = torch.nn.Linear(32, 13)

        def forward(self, x):
            seq = x.view(x.shape[0], 8, 118)
            return self.head(self.enc(self.proj(seq))[:, 0, :])

    p_xf = export_model(TransformerNet(), tmp_path / "transformer_s8.pt", stack=8, arch="transformer")
    res_xf = check_model(str(p_xf), speed_limit_ms=1000, timed_steps=20)
    assert res_xf["ok"] and res_xf["summary"]["rnn"] == "TRANSFORMER" and res_xf["summary"]["stack"] == 8

    class StatefulTransformerNet(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.proj = torch.nn.Linear(118 * 2, 64)
            self.enc = torch.nn.TransformerEncoderLayer(d_model=64, nhead=4, dim_feedforward=128, batch_first=True)
            self.head = torch.nn.Linear(64, 13)

        def forward(self, x, h):
            hist = torch.cat([h[1:], self.proj(x).unsqueeze(0)], dim=0)
            return self.head(self.enc(hist.transpose(0, 1))[:, -1, :]), hist

    p_stf = export_model(StatefulTransformerNet(), tmp_path / "stateful_xf.pt", recurrent=True, rnn="transformer", hidden=64, layers=8, stack=2)
    res_stf = check_model(str(p_stf), speed_limit_ms=1000, timed_steps=20)
    assert res_stf["ok"] and res_stf["summary"]["rnn"] == "TRANSFORMER"
    rows_xf, _ = play(3, [("gunner", "radar"), ("gunner", "shield")], [ModelPolicy(p_xf), ModelPolicy(p_stf)])
    assert rows_xf[0]["errors"] == 0 and rows_xf[1]["errors"] == 0

    with pytest.raises(ValueError):
        export_model(v1_net, tmp_path / "bad_s65.pt", stack=65)
    with pytest.raises(ValueError):
        export_model(Gru2ArgNet(), tmp_path / "bad_oom.pt", recurrent=True, rnn="transformer", hidden=2048, layers=100)


def test_stealth_blinks_and_stops_at_walls():
    from tank_arena.rules import BLINK, MAPS, TR, hits_rect

    class Script:
        def __init__(self, at):
            self.at, self.pos = at, {}

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


def test_marksman_armor_pierce_and_directional_shield(monkeypatch):
    from tank_arena import engine

    monkeypatch.setitem(engine.MAPS, "fort", dict(name="empty", rects=[]))
    for skill_s, mod_t, skill_t, exp_hits, exp_taken in (
        (False, "radar", False, 7, 7 * 20.4 * 0.8),
        (True, "radar", False, 6, 3 * 20.4 + 3 * 20.4 * 0.8),
        (False, "shield", True, 7, 7 * 20.4 * 0.8 - 7.8),
    ):
        game = Game(1, [("marksman", "radar"), ("gunner", mod_t)], mapname="fort")
        while not game.over:
            game.step([[0 if game.tick < 70 else 2, 1, 1, 1, int(skill_s and game.tick >= 55)], [2, 1, 1, 0, int(skill_t and game.tick >= 55)]])
        victim = game.tanks[1]
        assert not victim["alive"] and victim["struck"] == exp_hits and victim["taken"] == pytest.approx(exp_taken, abs=1e-4)


def test_backstep_and_focus(monkeypatch):
    from tank_arena import engine

    monkeypatch.setitem(engine.MAPS, "fort", dict(name="empty", rects=[]))
    game = Game(1, [("skirmisher", "backstep"), ("marksman", "focus")], mapname="fort")
    pos, bspd = {}, {}
    while game.tick < 110:
        pos[game.tick] = [(t["x"], t["y"]) for t in game.tanks]
        bspd[game.tick] = game.tanks[1]["bspd_now"]
        game.step([[2, 1, 1, 0, int(game.tick == 60)], [0, 1, 1, 0, int(game.tick == 60)]])
    hop = {t: math.dist(pos[t + 1][0], pos[t][0]) for t in range(55, 66)}
    assert hop[59] < 1e-9 and all(abs(hop[t] - 13.5) < 1e-6 for t in range(60, 64)) and hop[64] < 1e-9
    base_b, foc_b = 15.51, 15.51 * 1.28
    assert bspd[60] == pytest.approx(base_b) and all(bspd[t] == pytest.approx(foc_b) for t in range(61, 106)) and bspd[106] == pytest.approx(base_b)
    v = lambda t: math.dist(pos[t + 1][1], pos[t][1])
    assert abs(v(50) - 2.65) < 1e-5 and abs(v(75) - 2.65 * 0.72) < 1e-5


def test_shotgun_hits_hardest_up_close(monkeypatch):
    from tank_arena import engine

    monkeypatch.setitem(engine.MAPS, "fort", dict(name="empty", rects=[]))
    taken = {}
    for gap in (50, 250):
        game = Game(1, [("shotgun", "radar"), ("marksman", "radar")], mapname="fort")
        a, b = game.tanks
        a.update(x=300.0, y=400.0, heading=0.0, turret=0.0, cooldown=0)
        b.update(x=300.0 + gap, y=400.0)
        for _ in range(30):
            game.step([[2, 1, 1, int(game.tick == 0), 0], [2, 1, 1, 0, 0]])
        taken[gap] = b["taken"]
    assert taken[50] == pytest.approx(23.25, abs=1e-4)
    assert taken[250] == pytest.approx(2.5, abs=1e-4)


def test_three_way_v3_final_parity():
    tks_root = Path("/Volumes/Wang_SSD/Workspace/Project/tks-research")
    arena_root = Path("/Volumes/Wang_SSD/Workspace/Project/arena-a1")
    cfg_path = tks_root / "configs" / "v3_final.json"
    if not cfg_path.exists() or not arena_root.exists():
        pytest.skip("tks-research or arena-a1 not present")
    for p in (str(tks_root / "src"), str(arena_root)):
        if p not in sys.path:
            sys.path.insert(0, p)
    from arena.game.engine import play as arena_play
    from arena.game.observation import observation as arena_obs
    from tks_balance.ref_engine import RefGame, ref_observation
    from tks_balance.ruleset import RuleSet

    rs = RuleSet.from_json(cfg_path)
    combos = [
        (1, [("gunner", "shield"), ("shotgun", "stealth")]),
        (2, [("skirmisher", "backstep"), ("marksman", "radar")]),
        (3, [("marksman", "focus"), ("gunner", "radar")]),
        (17, [("shotgun", "backstep"), ("skirmisher", "stealth")]),
    ]

    for seed, loadouts in combos:
        sdk_g = Game(seed, loadouts)
        ref_g = RefGame(seed, loadouts, rs)
        while not sdk_g.over or not ref_g.over:
            assert sdk_g.over == ref_g.over and sdk_g.tick == ref_g.tick
            t = sdk_g.tick
            acts = []
            for idx in (0, 1):
                osdk = observation(sdk_g.state(idx))
                oref = ref_observation(ref_g.state(idx), rs)
                assert np.max(np.abs(osdk - oref)) < 1e-5
                if sdk_g.tanks[idx]["alive"]:
                    h = t * 37 + idx * 13 + seed * 7
                    acts.append([h % 3, (h // 3) % 3, (h // 7) % 3, int((h % 5) != 0), int(t >= 60 and (t % 19 == 0))])
                else:
                    acts.append(None)
            sdk_g.step(acts)
            ref_g.step(acts)

        # Also compare arena server play() + arena observation
        class ArenaSeq:
            def __init__(self, idx):
                self.idx = idx
                self.obs = []

            def reset(self):
                pass

            def act(self, s):
                t = s["t"]
                self.obs.append((t, arena_obs(s)))
                h = t * 37 + self.idx * 13 + seed * 7
                return [h % 3, (h // 3) % 3, (h // 7) % 3, int((h % 5) != 0), int(t >= 60 and (t % 19 == 0))]

        pa, pb = ArenaSeq(0), ArenaSeq(1)
        rows_ar, _ = arena_play(seed, loadouts, [pa, pb])
        rows_sdk = sdk_g.results()
        rows_ref = ref_g.results()
        for ra, rs_row, rr in zip(rows_ar, rows_sdk, rows_ref):
            assert ra["outcome"] == rs_row["outcome"] == rr["outcome"]
            assert abs(ra["hp"] - rr["hp"]) < 1e-5 and abs(rs_row["hp"] - rr["hp"]) < 1e-5
            assert ra["kills"] == rs_row["kills"] == rr["kills"]
            assert ra["hits"] == rs_row["hits"] == rr["hits"]
            assert ra["overheats"] == rs_row["overheats"] == rr["overheats"]
            assert ra["cores_captured"] == rs_row["cores_captured"] == rr["cores_captured"]
