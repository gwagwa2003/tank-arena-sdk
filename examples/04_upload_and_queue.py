"""Example 4: upload a model to the ladder from Python and queue a ranked match.

    TANK_ARENA_USER=my_account TANK_ARENA_PASSWORD=... python examples/04_upload_and_queue.py model.pt gunner:shield

The same works from the command line:  python -m tank_arena upload model.pt  and  python -m tank_arena queue --wait
"""
import os
import sys

from tank_arena.client import ArenaClient, ArenaError

path = sys.argv[1] if len(sys.argv) > 1 else "model.pt"
chassis, _, module = (sys.argv[2] if len(sys.argv) > 2 else "gunner:shield").partition(":")

c = ArenaClient()                                       # TANK_ARENA_SERVER, or the default site
user, pw = os.environ["TANK_ARENA_USER"], os.environ["TANK_ARENA_PASSWORD"]
try:
    c.login(user, pw)
except ArenaError as e:
    if e.status != 401: raise
    print("no such account (or wrong password): registering", user)
    c.register(user, pw, tank_name=user)                # fails if the site is full or the name is taken

c.set_loadout(chassis, module or "shield")              # must match the loadout the model was built for
res = c.upload(path)
print(f"upload: {res['status']} - {res['message']}")
if res["status"] != "通過":
    sys.exit(1)

c.queue()
print(f"queued one ranked game - watch it live at {c.server}/#live")
r = c.wait_round()
print("result:", r.get("message"))
me = c.me()["rank"]
print("rank:", "placement" if me["placing"] else f"{me['rank']} {me['lp']} LP")
