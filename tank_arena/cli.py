"""Command line: python -m tank_arena <command> (or `tank-arena <command>` after pip install).

    play A B           a local game: A and B are bot names (idle, turret, chaser) or model.pt files
    check model.pt     the server's checks, run on your machine
    upload model.pt    upload to the site (asks for your password, or reads TANK_ARENA_PASSWORD)
    queue              start a ranked game on the site (--wait: until it is over)
    ladder             the site's ladder
    replay ID          download a game's replay from the site as an HTML file you can open
"""
import argparse
import getpass
import json
import os
import random
import sys

LOADOUT_HELP = "chassis:module, e.g. gunner:shield (chassis: standard heavy scout gunner lancer; module: stealth shield boost antizone radar)"


def _policy(spec, seed):
    from .bots import BOTS
    if spec in BOTS:
        bot = BOTS[spec](seed=seed) if spec == "chaser" else BOTS[spec]()
        return bot
    if os.path.exists(spec):
        from .agent import ModelPolicy
        return ModelPolicy(spec, label=os.path.basename(spec))
    sys.exit(f"{spec!r} is neither a bot ({', '.join(BOTS)}) nor a file")


def _loadout(s):
    c, _, m = s.partition(":")
    return c, m or "shield"


def _client(args):
    from .client import ArenaClient
    c = ArenaClient(args.server)
    user = args.user or os.environ.get("TANK_ARENA_USER") or input("帳號 account: ")
    pw = os.environ.get("TANK_ARENA_PASSWORD") or getpass.getpass("密碼 password: ")
    c.login(user, pw)
    return c


def main(argv=None):
    ap = argparse.ArgumentParser(prog="tank-arena", description="Tank Arena SDK")
    ap.add_argument("--server", help="site URL (default: TANK_ARENA_SERVER or https://arena.gwagwa.de5.net)")
    ap.add_argument("--user", help="account name (default: TANK_ARENA_USER, or asked)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("play", help="play local games")
    p.add_argument("a"); p.add_argument("b")
    p.add_argument("--games", type=int, default=1); p.add_argument("--seed", type=int, default=None)
    p.add_argument("--loadout-a", default="gunner:shield", help=LOADOUT_HELP); p.add_argument("--loadout-b", default="gunner:shield")
    p.add_argument("--map", choices=["fort", "city"]); p.add_argument("--html", help="save the last game as an HTML replay")
    p = sub.add_parser("check", help="run the server's checks locally"); p.add_argument("model")
    p.add_argument("--limit", type=float, default=None, help="ms per step (default: the site's limit, or 50)")
    p = sub.add_parser("upload", help="upload a model.pt"); p.add_argument("model"); p.add_argument("--label", default="")
    p.add_argument("--keep-active", action="store_true", help="upload without making it your active model")
    p = sub.add_parser("queue", help="start a ranked game"); p.add_argument("--wait", action="store_true")
    sub.add_parser("ladder", help="show the ladder")
    p = sub.add_parser("replay", help="download a replay as HTML"); p.add_argument("game_id", type=int); p.add_argument("-o", "--out")
    args = ap.parse_args(argv)

    if args.cmd == "play":
        from .engine import play
        rng = random.Random(args.seed)
        tally = {"W": 0, "L": 0, "D": 0}
        a, b = _policy(args.a, rng.randrange(2 ** 31)), _policy(args.b, rng.randrange(2 ** 31))
        for i in range(args.games):
            seed = rng.randrange(2 ** 31)
            rows, rep = play(seed, [_loadout(args.loadout_a), _loadout(args.loadout_b)], [a, b], mapname=args.map,
                             replay=bool(args.html) and i == args.games - 1)
            r = rows[0]; tally[r["outcome"]] += 1
            print(f"game {i + 1}: {r['outcome']}  {r['steps'] / 20:5.1f} s  hp {r['hp']:.2f} vs {rows[1]['hp']:.2f}  "
                  f"hits {r['hits']}/{r['shots']} vs {rows[1]['hits']}/{rows[1]['shots']}  (seed {seed})")
        print(f"{args.a}: {tally['W']} W  {tally['L']} L  {tally['D']} D")
        if args.html:
            from .viewer import replay_html
            for p_, r_ in zip(rep["players"], rows): p_["outcome"] = r_["outcome"]
            print("replay:", replay_html(rep, args.html))
    elif args.cmd == "check":
        from .check import check_model
        limit = args.limit
        if limit is None:
            try:
                from .client import ArenaClient
                limit = float(ArenaClient(args.server, timeout=10).config()["speed_limit_ms"])
            except Exception:
                limit = 50.0
        res = check_model(args.model, limit)
        print(("✓ " if res["ok"] else "✗ ") + res["message"]); print(json.dumps(res["summary"], ensure_ascii=False, indent=1))
        sys.exit(0 if res["ok"] else 1)
    elif args.cmd == "upload":
        c = _client(args)
        res = c.upload(args.model, activate=not args.keep_active, label=args.label)
        print(f"{res['status']}：{res['message']}"); print(json.dumps(res.get("summary"), ensure_ascii=False, indent=1))
        sys.exit(0 if res["status"] == "通過" else 1)
    elif args.cmd == "queue":
        c = _client(args)
        c.queue(); print(f"queued — watch it live: {c.server}/#live")
        if args.wait:
            r = c.wait_round(); print(r.get("message") or r["status"])
    elif args.cmd == "ladder":
        from .client import ArenaClient
        lb = ArenaClient(args.server).leaderboard()
        for x in lb["rows"]:
            name = x.get("tank_name") or x.get("student_id")
            rank = "定級中" if x.get("placing") else f"{x['rank']} {x.get('lp', '')} LP"
            wr = "—" if x.get("winrate") is None else f"{x['winrate'] * 100:.0f}%"
            print(f"{x.get('place') or '-':>3}  {name:<24} {rank:<18} {wr}")
    elif args.cmd == "replay":
        from .client import ArenaClient
        from .viewer import replay_html
        c = ArenaClient(args.server)
        rep = c.replay(args.game_id)
        res = c.results(args.game_id)["players"]
        rep["players"] = [dict(label=p["label"], chassis=p["chassis"], module=p["module"], outcome=p.get("outcome")) for p in res]
        print("replay:", replay_html(rep, args.out or f"replay-{args.game_id}.html"))


if __name__ == "__main__":
    main()
