"""Turn your PyTorch network into a model.pt the server accepts.

    from tank_arena.export import export_model
    export_model(net, "model.pt", stack=4, mean=mean, std=std)
    export_model(gru_net, "model.pt", recurrent=True, rnn="gru", hidden=128, stack=2, mean=mean, std=std)

Your network gets a float tensor [1, obs_size x stack] (118 x stack for tank-arena-v3; newest frame first)
and returns logits [1, 13]: move (3), body (3), turret (3), fire (2), skill (2).
Stateless: forward(x) -> logits.
Stateful 2-arg: forward(x, h) -> (logits, h).
Stateful 3-arg: forward(x, h, c) -> (logits, h, c).
"""
import inspect
import json
import warnings

import numpy as np

from .agent import FORMAT, FORMATS, _torch, load_model


def export_model(
    net,
    path,
    stack=1,
    mean=None,
    std=None,
    recurrent=False,
    hidden=1,
    layers=1,
    rnn="lstm",
    sample=False,
    format=FORMAT,
    extra=None,
    arch=None,
):
    """Write `net` as TorchScript with its config.json. Returns the path."""
    torch = _torch()
    if format not in FORMATS:
        raise ValueError(f"unsupported format {format!r}; expected one of {list(FORMATS)}")
    obs_size = FORMATS[format]
    mean = np.zeros(obs_size) if mean is None else np.asarray(mean, dtype=np.float64)
    std = np.ones(obs_size) if std is None else np.asarray(std, dtype=np.float64)
    if not 1 <= int(stack) <= 64:
        raise ValueError("stack must be 1..64")
    if recurrent:
        if not 1 <= int(hidden) <= 4096:
            raise ValueError("hidden must be 1..4096")
        if not 1 <= int(layers) <= 128:
            raise ValueError("layers must be 1..128")
        if int(layers) * int(hidden) > 131072:
            raise ValueError("state tensor too large (layers * hidden must be <= 131072)")
        label = str(arch or rnn or "stateful").strip()[:24]
    else:
        hidden, layers = 1, 1
        label = str(arch).strip()[:24] if arch else None

    cfg = dict(
        format=format,
        stack=int(stack),
        recurrent=bool(recurrent),
        rnn=label,
        hidden=int(hidden),
        layers=int(layers),
        sample=bool(sample),
        mean=[float(v) for v in mean],
        std=[float(max(v, 1e-6)) for v in std],
        **(extra or {}),
    )

    sig = inspect.signature(net.forward)
    n_pos = len(
        [
            p
            for p in sig.parameters.values()
            if p.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
        ]
    )
    use_2arg = bool(recurrent and n_pos == 2)

    class Wrapped(torch.nn.Module):
        def __init__(self, inner):
            super().__init__()
            self.inner = inner

        def forward(self, x, h, c):
            if use_2arg:
                logits, h_out = self.inner(x, h)
                return logits, h_out, c
            if recurrent:
                return self.inner(x, h, c)
            return self.inner(x), h, c

    net = net.eval()
    wrapped = Wrapped(net).eval()
    x = torch.zeros(1, obs_size * stack)
    h = torch.zeros(layers, 1, hidden)
    c = torch.zeros(layers, 1, hidden)
    with torch.no_grad(), warnings.catch_warnings():
        warnings.simplefilter("ignore")
        scripted = torch.jit.trace(wrapped, (x, h, c), check_trace=False)
    torch.jit.save(scripted, str(path), _extra_files={"config.json": json.dumps(cfg)})
    load_model(path)
    return path
