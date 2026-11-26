"""Example 3: minimal recurrent (GRU / LSTM) model interface, TorchScript export, and check.

    pip install -e ".[torch]"
    python examples/03_minimal_recurrent.py --rnn gru
    python examples/03_minimal_recurrent.py --rnn lstm
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


class MinimalGRU(nn.Module):
    def __init__(self, n_in, hidden=64):
        super().__init__()
        self.rnn = nn.GRU(n_in, hidden, num_layers=1)
        self.head = nn.Linear(hidden, sum(ACTION_SIZES))

    def forward(self, x, h):
        out, h_next = self.rnn(x.unsqueeze(0), h)
        return self.head(out.squeeze(0)), h_next


class MinimalLSTM(nn.Module):
    def __init__(self, n_in, hidden=64):
        super().__init__()
        self.rnn = nn.LSTM(n_in, hidden, num_layers=1)
        self.head = nn.Linear(hidden, sum(ACTION_SIZES))

    def forward(self, x, h, c):
        out, (h_next, c_next) = self.rnn(x.unsqueeze(0), (h, c))
        return self.head(out.squeeze(0)), h_next, c_next


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rnn", choices=("gru", "lstm"), default="gru")
    ap.add_argument("--hidden", type=int, default=64)
    ap.add_argument("--stack", type=int, default=1, help="observation frames stacked (1-4)")
    ap.add_argument("--loadout", default="gunner:shield", help="chassis:module pair")
    ap.add_argument("--out", default="model.pt")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    torch.manual_seed(args.seed)
    chassis, _, module = args.loadout.partition(":")
    loadout = (chassis, module or "shield")

    n_in = OBS_SIZE * args.stack
    net = MinimalGRU(n_in, args.hidden) if args.rnn == "gru" else MinimalLSTM(n_in, args.hidden)
    mean = np.zeros(OBS_SIZE, dtype=np.float32)
    std = np.ones(OBS_SIZE, dtype=np.float32)
    export_model(
        net,
        args.out,
        recurrent=True,
        rnn=args.rnn,
        hidden=args.hidden,
        layers=1,
        stack=args.stack,
        mean=mean,
        std=std,
    )

    res = check_model(args.out, speed_limit_ms=20)
    assert res["ok"], res
    print(f"server checks ({args.rnn}):", res["message"], res["summary"].get("ms_p95"), "ms/step")

    rows, _ = play(args.seed, [loadout, ("gunner", "shield")], [ModelPolicy(args.out), IdleBot()])
    print(f"local match vs idle: outcome={rows[0]['outcome']} steps={rows[0]['steps']}")


if __name__ == "__main__":
    main()
