"""Example 2: minimal MLP model interface, TorchScript export, check, and local match.

    pip install -e ".[torch]"
    python examples/02_minimal_mlp.py --loadout gunner:shield
"""
import argparse

import numpy as np
import torch
from torch import nn

from tank_arena import IdleBot
from tank_arena.agent import ModelPolicy
from tank_arena.check import check_model
from tank_arena.engine import ACTION_SIZES, play
from tank_arena.export import export_model
from tank_arena.observation import OBS_SIZE


class MinimalMLP(nn.Module):
    def __init__(self, n_in):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(n_in, 64),
            nn.ReLU(),
            nn.Linear(64, sum(ACTION_SIZES)),
        )

    def forward(self, x):
        return self.net(x)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--loadout", default="gunner:shield", help="chassis:module pair")
    ap.add_argument("--stack", type=int, default=1, help="observation frames stacked (1-16)")
    ap.add_argument("--out", default="model.pt")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    torch.manual_seed(args.seed)
    chassis, _, module = args.loadout.partition(":")
    loadout = (chassis, module or "shield")

    net = MinimalMLP(OBS_SIZE * args.stack)
    mean = np.zeros(OBS_SIZE, dtype=np.float32)
    std = np.ones(OBS_SIZE, dtype=np.float32)
    export_model(net, args.out, stack=args.stack, mean=mean, std=std)

    res = check_model(args.out, speed_limit_ms=20)
    assert res["ok"], res
    print("server checks:", res["message"], res["summary"].get("ms_p95"), "ms/step")

    rows, _ = play(args.seed, [loadout, ("gunner", "shield")], [ModelPolicy(args.out), IdleBot()])
    print(f"local match vs idle: outcome={rows[0]['outcome']} steps={rows[0]['steps']}")


if __name__ == "__main__":
    main()
