"""Tank Arena SDK: the game, the observation, local training, export and the site's API.

    from tank_arena import play, Game, observation, TankEnv, ChaserBot, export_model, ArenaClient
"""
__version__ = "0.2.1"

from .bots import ChaserBot, IdleBot, TurretBot
from .client import ArenaClient
from .engine import ACTION_SIZES, IDLE, Game, play
from .env import TankEnv
from .observation import OBS_SIZE, observation


def __getattr__(name):            # the parts that need PyTorch load only when used
    if name in ("ModelPolicy", "FrameStack", "load_model"):
        from . import agent
        return getattr(agent, name)
    if name == "export_model":
        from .export import export_model
        return export_model
    if name == "check_model":
        from .check import check_model
        return check_model
    raise AttributeError(name)
