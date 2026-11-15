"""Running a model.pt exactly the way the server does: normalise, stack frames (or carry the LSTM state), forward, pick.

model.pt is a TorchScript module with forward(x, h, c) -> (logits[1, 13], h, c) and a config.json packed inside
(docs/model-format.md). export.py writes such files.
"""
import json

import numpy as np

from .engine import ACTION_SIZES
from .observation import OBS_SIZE, observation

FORMAT = "tank-arena-v1"


def _torch():
    try:
        import torch
    except ImportError as e:
        raise ImportError("running or exporting a model needs PyTorch: pip install torch") from e
    return torch


def load_model(path):
    """(TorchScript module, config dict, mean, std) after the same checks the server makes. Raises ValueError."""
    torch = _torch()
    extra = {"config.json": ""}
    net = torch.jit.load(str(path), map_location="cpu", _extra_files=extra)
    cfg = json.loads(extra["config.json"] or "{}")
    if cfg.get("format") != FORMAT:
        raise ValueError(f"model.pt has no valid config.json (format must be {FORMAT}); export it with tank_arena.export")
    stack, hidden = int(cfg["stack"]), int(cfg["hidden"])
    if not 1 <= stack <= 16: raise ValueError("stack must be 1..16")
    if not 1 <= hidden <= 2048: raise ValueError("hidden must be 1..2048")
    if not 1 <= int(cfg.get("layers", 1)) <= 4: raise ValueError("layers must be 1..4")
    mean, std = np.asarray(cfg["mean"], np.float32), np.asarray(cfg["std"], np.float32)
    if mean.shape != (OBS_SIZE,) or std.shape != (OBS_SIZE,) or not np.all(np.isfinite(mean)) or not np.all(std > 0):
        raise ValueError("mean and std must be 91 finite numbers, std > 0")
    if cfg["recurrent"] and stack != 1: raise ValueError("an LSTM model cannot also stack frames (stack must be 1)")
    return net.eval(), cfg, mean, std


class FrameStack:
    """The input the server builds for a non-recurrent model: the normalised observations of the last `stack` steps,
    newest first, concatenated (91 x stack numbers). At the start of a game the oldest frame is repeated.
    Use it when you collect training data, so your network sees exactly what it will see on the ladder."""
    def __init__(self, stack, mean=None, std=None):
        self.stack = stack
        self.mean = np.zeros(OBS_SIZE, np.float32) if mean is None else np.asarray(mean, np.float32)
        self.std = np.ones(OBS_SIZE, np.float32) if std is None else np.asarray(std, np.float32)
        self.reset()

    def reset(self):
        self.hist = []

    def push(self, obs):
        o = (np.asarray(obs, np.float32) - self.mean) / self.std
        self.hist = ([o] + self.hist)[:self.stack]
        while len(self.hist) < self.stack:
            self.hist.append(self.hist[-1])
        return np.concatenate(self.hist)


class ModelPolicy:
    """Drives a tank with a model.pt, like the server: ModelPolicy("model.pt").act(state) -> 5 ints."""
    def __init__(self, path, sample=None, label=None):
        self.torch = _torch()
        self.net, self.cfg, self.mean, self.std = load_model(path)
        self.recurrent, self.stack = bool(self.cfg["recurrent"]), int(self.cfg["stack"])
        self.sample = bool(self.cfg.get("sample", False)) if sample is None else sample
        self.hidden = int(self.cfg["hidden"]) if self.recurrent else 1
        self.layers = int(self.cfg.get("layers", 1)) if self.recurrent else 1
        self.label = label or str(path)
        self.frames = FrameStack(1 if self.recurrent else self.stack, self.mean, self.std)
        self.reset()

    def reset(self):
        torch = self.torch
        self.frames.reset()
        self.h = torch.zeros(self.layers, 1, self.hidden); self.c = torch.zeros(self.layers, 1, self.hidden)

    def act_obs(self, obs):
        """The action for an observation (91 numbers, not normalised)."""
        torch = self.torch
        x = self.frames.push(obs)
        with torch.no_grad():
            logits, self.h, self.c = self.net(torch.from_numpy(x)[None], self.h, self.c)
        parts = torch.split(logits[0], list(ACTION_SIZES))
        if self.sample:
            return [int(torch.distributions.Categorical(logits=p).sample()) for p in parts]
        return [int(p.argmax()) for p in parts]

    def act(self, state):
        return self.act_obs(observation(state))
