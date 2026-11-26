"""Example 1: write a basic rule bot, run a local match against ChaserBot, and view the replay.

Rule bots read the full game state and are only for local play and testing. Only exported TorchScript models
(model.pt) can play on the ladder.

    python examples/01_rule_bot.py          # then open replay.html in a browser
"""
import math

from tank_arena import ChaserBot, play
from tank_arena.bots import FWD, KEEP, LEFT, RIGHT, STOP, turn_toward
from tank_arena.geometry import visible_enemies, wrap
from tank_arena.rules import CHASSIS, TROT, TURRET_ROT_MULT
from tank_arena.viewer import replay_html


class MyBot:
    """Drive toward the zone centre; when an enemy is in sight, turn the turret to it and fire once it is lined up."""
    label = "my bot"

    def act(self, state):
        me, zone = state["self"], state["zone"]
        # body: head for the zone centre, stop when close
        to_zone = math.atan2(zone["y"] - me["y"], zone["x"] - me["x"])
        near_centre = math.hypot(zone["x"] - me["x"], zone["y"] - me["y"]) < 80
        body = turn_toward(me["heading"], to_zone, CHASSIS[me["chassis"]][1])
        move = STOP if near_centre else FWD
        # turret: aim at the nearest enemy we can see
        seen = visible_enemies(state)
        if not seen:
            return [move, body, RIGHT, 0, 0]            # sweep the turret while looking around
        e = seen[0]
        want = math.atan2(e["y"] - me["y"], e["x"] - me["x"])
        trot = TROT * TURRET_ROT_MULT.get(me["chassis"], 1.0)
        turret = turn_toward(me["turret"], want, trot)
        fire = int(abs(wrap(want - me["turret"])) < 0.1 and me["cooldown"] == 0)
        return [move, body, turret, fire, 0]


if __name__ == "__main__":
    wins = 0
    for seed in range(10):
        rows, rep = play(seed, [("gunner", "shield"), ("gunner", "shield")], [MyBot(), ChaserBot(seed=seed)], replay=True)
        wins += rows[0]["outcome"] == "W"
        print(f"seed {seed}: {rows[0]['outcome']}  my hp {rows[0]['hp']:.2f}, chaser hp {rows[1]['hp']:.2f}")
    print(f"my bot won {wins}/10")
    for p, r in zip(rep["players"], rows): p["outcome"] = r["outcome"]
    print("last game:", replay_html(rep, "replay.html"))
