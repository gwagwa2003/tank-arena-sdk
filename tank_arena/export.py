"""Turn your PyTorch network into a model.pt the server accepts.

    from tank_arena.export import export_model
    export_model(net, "model.pt", stack=4, mean=mean, std=std)

Your network gets a float tensor [1, 91 x stack] (normalised, newest frame first, see agent.FrameStack) and returns
logits [1, 13]: move (3), body (3), turret (3), fire (2), skill (2). For an LSTM (recurrent=True, stack=1) it gets
(x, h, c) and returns (logits, h, c), with h and c shaped [layers, 1, hidden].
"""
import json
import warnings

import numpy as np

from .agent import FORMAT, _torch, load_model
from .observation import OBS_SIZE


def export_model(net, path, stack=1, mean=None, std=None, recurrent=False, hidden=1, layers=1, sample=False, extra=None):
    """Write `net` as TorchScript with its config.json. Returns the path.
    mean, std: the 91 numbers your inputs were normalised with (default 0 and 1).
    sample: True = the server samples each action from the softmax; False = it takes the most likely one."""
    torch = _torch()
    mean = np.zeros(OBS_SIZE) if mean is None else np.asarray(mean, dtype=np.float64)
    std = np.ones(OBS_SIZE) if std is None else np.asarray(std, dtype=np.float64)
    if recurrent and stack != 1: raise ValueError("an LSTM model must use stack=1")
    if not recurrent: hidden, layers = 1, 1
    cfg = dict(format=FORMAT, stack=int(stack), recurrent=bool(recurrent), hidden=int(hidden), layers=int(layers),
               sample=bool(sample), mean=[float(v) for v in mean], std=[float(max(v, 1e-6)) for v in std], **(extra or {}))

    class Wrapped(torch.nn.Module):
        def __init__(self, inner):
            super().__init__()
            self.inner = inner

        def forward(self, x, h, c):
            if recurrent:
                return self.inner(x, h, c)
            return self.inner(x), h, c

    net = net.eval()
    wrapped = Wrapped(net).eval()
    x = torch.zeros(1, OBS_SIZE * stack); h = torch.zeros(layers, 1, hidden); c = torch.zeros(layers, 1, hidden)
    with torch.no_grad(), warnings.catch_warnings():
        warnings.simplefilter("ignore")                  # tracing warns about shape checks; the input shape is fixed
        scripted = torch.jit.trace(wrapped, (x, h, c), check_trace=False)
    torch.jit.save(scripted, str(path), _extra_files={"config.json": json.dumps(cfg)})
    load_model(path)                                    # fails now rather than on the server
    return path
