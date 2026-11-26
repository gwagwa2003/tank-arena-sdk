"""Running a model.pt exactly the way the server does: normalise, stack frames (and/or carry state), forward, pick.

Supports any TorchScript architecture (MLP, CNN, Transformer, LSTM, GRU, custom stateful nets):
- tank-arena-v3 (118 dims)
- tank-arena-v1 (91 dims sliced from first 91 dims of v3 obs)
Runtime contract: forward(x, h, c) -> (logits[1, 13], h, c).
"""
import json

import numpy as np

from .engine import ACTION_SIZES
from .observation import OBS_SIZE, observation

OBS_SIZE_V1 = 91
FORMAT_V1 = "tank-arena-v1"
FORMAT_V3 = "tank-arena-v3"
FORMAT = FORMAT_V3
FORMATS = {FORMAT_V1: OBS_SIZE_V1, FORMAT_V3: OBS_SIZE}


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
    fmt = cfg.get("format")
    if fmt not in FORMATS:
        raise ValueError(f"model.pt has no valid config.json (format must be {FORMAT_V3} or {FORMAT_V1}); export it with tank_arena.export")
    obs_size = FORMATS[fmt]
    stack = int(cfg.get("stack", 1))
    recurrent = bool(cfg.get("recurrent", False))
    hidden = int(cfg.get("hidden", 1))
    layers = int(cfg.get("layers", 1))
    if not 1 <= stack <= 64:
        raise ValueError("stack must be 1..64")
    if recurrent:
        if not 1 <= hidden <= 4096:
            raise ValueError("hidden must be 1..4096")
        if not 1 <= layers <= 128:
            raise ValueError("layers must be 1..128")
        if layers * hidden > 131072:
            raise ValueError("state tensor too large (layers * hidden must be <= 131072)")
    else:
        if hidden < 1 or layers < 1:
            raise ValueError("hidden and layers must be > 0")
    mean, std = np.asarray(cfg["mean"], np.float32), np.asarray(cfg["std"], np.float32)
    if mean.shape != (obs_size,) or std.shape != (obs_size,) or not np.all(np.isfinite(mean)) or not np.all(std > 0):
        raise ValueError(f"mean and std must be {obs_size} finite numbers, std > 0")
    return net.eval(), cfg, mean, std


class FrameStack:
    """The input the server builds: the normalised observations of the last `stack` steps,
    newest first, concatenated (obs_size x stack). Automatically slices obs[:obs_size]."""

    def __init__(self, stack, mean=None, std=None, obs_size=None):
        self.stack = stack
        if mean is None:
            n = obs_size or OBS_SIZE
            self.mean = np.zeros(n, np.float32)
        else:
            self.mean = np.asarray(mean, np.float32)
        self.obs_size = len(self.mean)
        self.std = np.ones(self.obs_size, np.float32) if std is None else np.asarray(std, np.float32)
        self.reset()

    def reset(self):
        self.hist = []

    def push(self, obs):
        arr = np.asarray(obs, np.float32)
        if arr.shape[0] < self.obs_size:
            raise ValueError(f"obs length {arr.shape[0]} < expected {self.obs_size}")
        o = (arr[:self.obs_size] - self.mean) / self.std
        self.hist = ([o] + self.hist)[:self.stack]
        while len(self.hist) < self.stack:
            self.hist.append(self.hist[-1])
        return np.concatenate(self.hist)


class ModelPolicy:
    """Drives a tank with a model.pt, like the server: ModelPolicy('model.pt').act(state) -> 5 ints."""

    def __init__(self, path, sample=None, label=None):
        self.torch = _torch()
        self.net, self.cfg, self.mean, self.std = load_model(path)
        self.format = self.cfg["format"]
        self.obs_size = len(self.mean)
        self.recurrent, self.stack = bool(self.cfg.get("recurrent", False)), int(self.cfg.get("stack", 1))
        arch = str(self.cfg.get("rnn") or self.cfg.get("arch") or "").strip()[:24]
        self.rnn = (arch or ("stateful" if self.recurrent else "")).lower()
        self.sample = bool(self.cfg.get("sample", False)) if sample is None else sample
        self.hidden = int(self.cfg.get("hidden", 1)) if self.recurrent else 1
        self.layers = int(self.cfg.get("layers", 1)) if self.recurrent else 1
        self.label = label or str(path)
        self.frames = FrameStack(self.stack, self.mean, self.std, obs_size=self.obs_size)
        self.reset()

    def reset(self):
        torch = self.torch
        self.frames.reset()
        self.h = torch.zeros(self.layers, 1, self.hidden)
        self.c = torch.zeros(self.layers, 1, self.hidden)

    def act_obs(self, obs):
        """The action for an observation (118 numbers for v3, or 91+ for v1, not normalised)."""
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
