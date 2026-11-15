"""Example 2: your first model, by imitation. A few minutes on a laptop CPU, no GPU needed.

1. A teacher (ChaserBot, which reads the full state) plays games against assorted bots; every step we record what the
   model would see (the 91-number observation) and what the teacher did.
2. A small network learns to copy the teacher from the observation alone.
3. DAgger: the network now drives, the teacher keeps saying what it would have done, and those states join the data,
   so the network also learns to recover from its own mistakes. Repeat a few times.
4. Export to model.pt, run the server's checks, and play it against the bots.

    pip install -e ".[torch]"
    python examples/02_behavior_cloning.py --loadout gunner:shield
    python -m tank_arena upload model.pt
Use the same loadout on the site (the 我的 page, or ArenaClient.set_loadout) as the one you trained with.
"""
import argparse
import random
import time

import numpy as np
import torch
from torch import nn

from tank_arena import ChaserBot, Game, IdleBot, TurretBot, observation
from tank_arena.agent import FrameStack, ModelPolicy
from tank_arena.check import check_model
from tank_arena.engine import ACTION_SIZES, play
from tank_arena.export import export_model

CHASSIS = ["standard", "heavy", "scout", "gunner", "lancer"]
MODULES = ["stealth", "shield", "boost", "antizone", "radar"]


def opponents(rng):
    """A mix of sparring partners, so the student sees many situations."""
    k = rng.random()
    if k < 0.15: return IdleBot()
    if k < 0.35: return TurretBot()
    return ChaserBot(distance=rng.choice([160, 220, 280]), strafe=rng.random() < 0.8, seed=rng.randrange(2 ** 31))


def collect(n_games, loadout, rng, student=None, beta=1.0):
    """Games where the teacher's action is recorded at every step. With a student, the student drives with probability
    1 - beta at each step (DAgger); the recorded label is always the teacher's. Returns a list of (obs[T, 91], act[T, 5])."""
    episodes = []
    for _ in range(n_games):
        teacher = ChaserBot(distance=220, strafe=True, seed=rng.randrange(2 ** 31))
        op = opponents(rng)
        game = Game(rng.randrange(2 ** 31), [loadout, (rng.choice(CHASSIS), rng.choice(MODULES))])
        if student: student.reset()
        obs_l, act_l = [], []
        while not game.over:
            st = game.state(0)
            o = observation(st); a = teacher.act(st)
            obs_l.append(o); act_l.append(a)
            mine = a
            if student is not None:
                s_act = student.act_obs(o)                  # keep the student's frame stack up to date every step
                if rng.random() >= beta: mine = s_act
            other = op.act(game.state(1)) if game.tanks[1]["alive"] else None
            game.step([mine, other])
        episodes.append((np.array(obs_l, np.float32), np.array(act_l, np.int64)))
    return episodes


def stack_episodes(episodes, stack, mean, std):
    """The exact inputs the server will feed the network (normalised, newest frame first), episode by episode."""
    xs, ys = [], []
    for obs, act in episodes:
        fs = FrameStack(stack, mean, std)
        xs.append(np.stack([fs.push(o) for o in obs])); ys.append(act)
    return np.concatenate(xs), np.concatenate(ys)


class Policy(nn.Module):
    def __init__(self, n_in, hidden=256):
        super().__init__()
        self.body = nn.Sequential(nn.Linear(n_in, hidden), nn.ReLU(), nn.Linear(hidden, hidden), nn.ReLU(),
                                  nn.Linear(hidden, sum(ACTION_SIZES)))

    def forward(self, x):
        return self.body(x)


def train(net, x, y, epochs, lr=1e-3, batch=512):
    opt = torch.optim.Adam(net.parameters(), lr=lr)
    x, y = torch.from_numpy(x), torch.from_numpy(y)
    net.train()
    for ep in range(epochs):
        perm = torch.randperm(len(x)); total = 0.0
        for i in range(0, len(x), batch):
            idx = perm[i:i + batch]
            parts = torch.split(net(x[idx]), list(ACTION_SIZES), dim=1)
            loss = sum(nn.functional.cross_entropy(p, y[idx, k]) for k, p in enumerate(parts))
            opt.zero_grad(); loss.backward(); opt.step(); total += loss.item() * len(idx)
        print(f"    epoch {ep + 1}/{epochs}: loss {total / len(x):.3f}")
    net.eval()


def evaluate(path, loadout, games, rng):
    for name, make in (("idle", IdleBot), ("turret", TurretBot), ("chaser", lambda: ChaserBot(seed=rng.randrange(2 ** 31)))):
        w = 0
        for _ in range(games):
            rows, _ = play(rng.randrange(2 ** 31), [loadout, ("gunner", "shield")], [ModelPolicy(path), make()])
            w += rows[0]["outcome"] == "W"
        print(f"  vs {name:<7} {w}/{games} wins")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--loadout", default="gunner:shield", help="chassis:module you will use on the site")
    ap.add_argument("--games", type=int, default=80, help="teacher games to start with")
    ap.add_argument("--dagger", type=int, default=3, help="DAgger rounds")
    ap.add_argument("--stack", type=int, default=4, help="frames the network sees (1-16)")
    ap.add_argument("--epochs", type=int, default=8)
    ap.add_argument("--out", default="model.pt")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    torch.manual_seed(args.seed); torch.set_num_threads(max(1, torch.get_num_threads()))
    rng = random.Random(args.seed)
    chassis, _, module = args.loadout.partition(":"); loadout = (chassis, module or "shield")

    t0 = time.time()
    print(f"collecting {args.games} teacher games with {loadout[0]}+{loadout[1]} ...")
    episodes = collect(args.games, loadout, rng)
    allobs = np.concatenate([o for o, _ in episodes])
    mean, std = allobs.mean(0), allobs.std(0) + 1e-3        # fixed from now on: exported with the model
    net = Policy(91 * args.stack)
    for r in range(args.dagger + 1):
        x, y = stack_episodes(episodes, args.stack, mean, std)
        print(f"round {r}: training on {len(x):,} steps")
        train(net, x, y, args.epochs)
        export_model(net, args.out, stack=args.stack, mean=mean, std=std)
        if r < args.dagger:
            beta = 0.5 ** (r + 1)                            # the student drives more and more
            print(f"  DAgger: {args.games // 2} games with the student driving {1 - beta:.0%} of the time")
            episodes += collect(args.games // 2, loadout, rng, student=ModelPolicy(args.out), beta=beta)

    print(f"done in {time.time() - t0:.0f} s -> {args.out}")
    res = check_model(args.out, speed_limit_ms=50)
    print("server checks:", res["message"], res["summary"].get("ms_p95"), "ms/step")
    evaluate(args.out, loadout, 10, rng)


if __name__ == "__main__":
    main()
