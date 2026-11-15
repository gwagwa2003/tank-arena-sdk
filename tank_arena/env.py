"""A training environment in the usual reset / step shape (no gym needed; it follows the Gymnasium API).

    env = TankEnv(opponent=ChaserBot(), loadout=("gunner", "shield"))
    obs, info = env.reset(seed=1)
    while True:
        obs, reward, terminated, truncated, info = env.step(my_action(obs))
        if terminated or truncated: break

obs is the 91-number observation (not normalised, not stacked: agent.FrameStack does what the server does).
The reward is a simple default you can replace (reward_fn): damage dealt and taken, plus +-10 for winning / losing.
"""
import random

from .engine import IDLE, Game, valid_action
from .observation import observation


def default_reward(prev, now, done, outcome):
    """prev, now: {"me": my tank, "op": the opponent} before and after the step (dicts with hp, damage, taken...).
    +0.1 per HP of damage dealt, -0.1 per HP lost (bullets and the zone), +10 / -10 for a win / loss at the end."""
    r = 0.1 * (now["me"]["damage"] - prev["me"]["damage"]) - 0.1 * max(0.0, prev["me"]["hp"] - now["me"]["hp"])
    if done:
        r += {"W": 10.0, "L": -10.0, "D": 0.0}[outcome]
    return r


class TankEnv:
    """1v1 against a fixed opponent policy (a bot, or agent.ModelPolicy for a model.pt).
    loadout / opponent_loadout: (chassis, module). Each reset plays a new map, zone and start position (random unless
    a seed is given). You are always tank 0."""
    def __init__(self, opponent, loadout=("gunner", "shield"), opponent_loadout=("gunner", "shield"), reward_fn=default_reward,
                 mapname=None):
        self.opponent, self.loadout, self.opponent_loadout = opponent, tuple(loadout), tuple(opponent_loadout)
        self.reward_fn, self.mapname = reward_fn, mapname
        self.game = None
        self._rng = random.Random()

    def reset(self, seed=None):
        if seed is not None: self._rng.seed(seed)
        self.game = Game(self._rng.randrange(2 ** 31), [self.loadout, self.opponent_loadout], self.mapname)
        if hasattr(self.opponent, "reset"): self.opponent.reset()
        return observation(self.game.state(0)), self._info()

    def _snap(self):
        me, op = self.game.tanks
        return {"me": dict(me), "op": dict(op)}

    def _info(self):
        g = self.game
        return dict(t=g.tick, map=g.mapname, hp=g.tanks[0]["hp_frac"], enemy_hp=g.tanks[1]["hp_frac"])

    def step(self, action):
        g = self.game
        if g is None or g.over: raise RuntimeError("call reset() first")
        prev = self._snap()
        try:
            op = valid_action(self.opponent.act(g.state(1))) if g.tanks[1]["alive"] else None
        except Exception:
            op = list(IDLE)
        g.step([action, op])
        done = g.over
        outcome = g.results()[0]["outcome"] if done else None
        reward = self.reward_fn(prev, self._snap(), done, outcome)
        info = self._info()
        if done: info.update(outcome=outcome, results=g.results())
        terminated = done and g.steps < 1200
        truncated = done and not terminated
        return observation(g.state(0)), reward, terminated, truncated, info
