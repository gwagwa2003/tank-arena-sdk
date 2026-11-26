"""Check a model.pt before uploading: the same checks the server runs (format, output shape, speed, one test game).

    python -m tank_arena check model.pt
"""
import time
import zipfile

import numpy as np

from .agent import ModelPolicy, load_model
from .bots import ChaserBot
from .engine import play

MAX_MB = 10  # the server's current limit (GET /api/config -> max_model_mb)


def check_model(path, speed_limit_ms=20.0, loadout=("gunner", "shield"), timed_steps=400, max_mb=MAX_MB):
    """dict(ok, message, summary)."""
    import torch

    torch.set_num_threads(1)
    size = __import__("os").path.getsize(path)
    if size > max_mb * 1024 * 1024:
        return dict(ok=False, message=f"file is larger than {max_mb:g} MB", summary={})
    if not zipfile.is_zipfile(path):
        return dict(ok=False, message="not a TorchScript file (model.pt is a zip); export it with tank_arena.export", summary={})
    try:
        net, cfg, mean, std = load_model(path)
    except Exception as e:
        return dict(ok=False, message=f"cannot load the model: {e}", summary={})
    recurrent, stack = bool(cfg.get("recurrent", False)), int(cfg.get("stack", 1))
    fmt, obs_size = cfg["format"], len(mean)
    arch = str(cfg.get("rnn") or cfg.get("arch") or "").strip()[:24]
    rnn = (arch.upper() if arch else "STATEFUL") if recurrent else (arch.upper() if arch else None)
    summary = dict(
        format=fmt,
        obs_size=obs_size,
        rnn=rnn,
        params=sum(p.numel() for p in net.parameters()),
        stack=stack,
        recurrent=recurrent,
        sample=bool(cfg.get("sample", False)),
        size_mb=round(size / 2**20, 2),
    )
    try:
        pol = ModelPolicy(path)
        x = torch.zeros(1, obs_size * stack)
        with torch.no_grad():
            out = pol.net(x, pol.h, pol.c)
        if not (isinstance(out, tuple) and len(out) == 3 and isinstance(out[0], torch.Tensor) and isinstance(out[1], torch.Tensor) and isinstance(out[2], torch.Tensor)):
            return dict(ok=False, message="forward must return (logits, h, c) tensors", summary=summary)
        if tuple(out[0].shape) != (1, 13) or not torch.isfinite(out[0]).all():
            return dict(ok=False, message=f"logits must be finite and shaped (1, 13), got {tuple(out[0].shape)}", summary=summary)
        rng = np.random.default_rng(0)
        times = []
        for i in range(timed_steps + 50):
            obs = (mean + std * rng.standard_normal(obs_size).astype(np.float32)).clip(-2, 2)
            t = time.perf_counter()
            pol.act_obs(obs)
            dt = (time.perf_counter() - t) * 1e3
            if i >= 50:
                times.append(dt)
        p95 = float(np.percentile(times, 95))
        summary.update(ms_p95=round(p95, 3), ms_mean=round(float(np.mean(times)), 3))
        if p95 > speed_limit_ms:
            return dict(ok=False, message=f"too slow: p95 {p95:.2f} ms per step, limit {speed_limit_ms:g} ms", summary=summary)
    except Exception as e:
        return dict(ok=False, message=f"inference failed: {e}", summary=summary)
    try:
        rows, _ = play(12345, [tuple(loadout), ("gunner", "shield")], [ModelPolicy(path), ChaserBot(seed=0)])
        summary["test_game"] = dict(
            outcome=rows[0]["outcome"],
            hp=round(rows[0]["hp"], 2),
            kills=rows[0]["kills"],
            steps=rows[0]["steps"],
        )
        if rows[0]["errors"]:
            return dict(ok=False, message=f"{rows[0]['errors']} steps failed in the test game", summary=summary)
    except Exception as e:
        return dict(ok=False, message=f"test game failed: {e}", summary=summary)
    return dict(ok=True, message="passed", summary=summary)
