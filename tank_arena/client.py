"""Talk to a Tank Arena site from Python: register, log in, choose a loadout, upload a model, queue a ranked game,
read the ladder and download replays. Only the standard library is used.

    from tank_arena.client import ArenaClient
    c = ArenaClient()                      # https://arena.gwagwa.de5.net
    c.login("my_account", "my_password")
    c.set_loadout("gunner", "shield", tank_name="My Tank")
    print(c.upload("model.pt"))            # the server checks it; "status" is 通過 (passed) or 不通過 (failed)
    c.queue()                              # play one ranked game (watch it on the site's 直播 page)
"""
import gzip
import http.cookiejar
import json
import os
import time
import urllib.error
import urllib.request
import uuid

DEFAULT_SERVER = "https://arena.gwagwa.de5.net"


class ArenaError(Exception):
    def __init__(self, status, message):
        super().__init__(f"HTTP {status}: {message}")
        self.status, self.message = status, message


class ArenaClient:
    def __init__(self, server=None, timeout=120):
        self.server = (server or os.environ.get("TANK_ARENA_SERVER") or DEFAULT_SERVER).rstrip("/")
        self.timeout = timeout
        self.jar = http.cookiejar.CookieJar()
        self.http = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))
        self.http.addheaders = [("User-Agent", "tank-arena-sdk"), ("Accept-Encoding", "gzip")]

    # ───── plumbing ─────
    def _request(self, method, path, body=None, headers=None, raw=False):
        req = urllib.request.Request(self.server + path, data=body, method=method, headers=headers or {})
        try:
            with self.http.open(req, timeout=self.timeout) as r:
                data = r.read()
        except urllib.error.HTTPError as e:
            data = e.read()
            try: msg = json.loads(data).get("error") or data.decode()
            except Exception: msg = data.decode(errors="replace")
            raise ArenaError(e.code, msg) from None
        if data[:2] == b"\x1f\x8b": data = gzip.decompress(data)       # gzipped responses (and replays, stored gzipped)
        return data if raw else (json.loads(data) if data else None)

    def _get(self, path): return self._request("GET", path)
    def _post(self, path, payload=None):
        return self._request("POST", path, json.dumps(payload or {}).encode(), {"Content-Type": "application/json"})

    # ───── account ─────
    def register(self, account, password, tank_name=None):
        """New account (3-32 letters, digits, _ . -; password 6+ characters). Logs in."""
        return self._post("/api/register", dict(student_id=account, key=password, tank_name=tank_name))

    def login(self, account, password):
        return self._post("/api/login", dict(student_id=account, key=password))

    def logout(self): return self._post("/api/logout")
    def me(self):
        """Your account: rank, LP, loadout, active model, uploads and your last rounds."""
        return self._get("/api/me")

    def config(self):
        """Site settings: speed_limit_ms, max_model_mb, ranks, chassis and modules..."""
        return self._get("/api/config")

    def set_loadout(self, chassis, module, tank_name=None):
        """chassis: standard / heavy / scout / gunner / lancer; module: stealth / shield / boost / antizone / radar."""
        return self._post("/api/loadout", dict(chassis=chassis, module=module, tank_name=tank_name))

    def sit_out(self, resting=True):
        """Rest (no ranked games, nobody can be matched against you) or come back."""
        return self._post("/api/sit-out", dict(sit_out=bool(resting)))

    # ───── models ─────
    def upload(self, path, activate=True, label=""):
        """Upload a model.pt. The server checks it right away (this call waits for that) and returns
        dict(id, version, status "通過"/"不通過", message, summary, active)."""
        boundary = uuid.uuid4().hex
        with open(path, "rb") as f: content = f.read()
        parts = []
        for name, value in (("activate", "true" if activate else "false"), ("label", label or "")):
            parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode())
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{os.path.basename(path)}"\r\n'
                     f"Content-Type: application/octet-stream\r\n\r\n".encode() + content + b"\r\n")
        parts.append(f"--{boundary}--\r\n".encode())
        return self._request("POST", "/api/upload", b"".join(parts), {"Content-Type": f"multipart/form-data; boundary={boundary}"})

    def models(self): return self._get("/api/models")
    def set_active(self, model_id): return self._post("/api/active", dict(model_id=int(model_id)))

    # ───── ranked games ─────
    def queue(self):
        """開始排位: queue ranked games (one per call on the default site)."""
        return self._post("/api/queue")

    def cancel_queue(self): return self._request("DELETE", "/api/queue")

    def wait_round(self, poll=5.0, timeout=1800):
        """Wait until your latest round is over; returns it (status, message, games)."""
        end = time.time() + timeout
        while time.time() < end:
            rounds = self.me().get("rounds") or []
            if rounds and rounds[0]["status"] not in ("排隊中", "進行中"): return rounds[0]
            time.sleep(poll)
        raise TimeoutError("the round did not finish in time")

    # ───── public pages ─────
    def leaderboard(self): return self._get("/api/leaderboard")
    def player(self, user_id): return self._get(f"/api/players/{int(user_id)}")
    def games(self, limit=30, mine=False, user_id=None, season=None):
        q = [f"limit={int(limit)}"] + (["mine=true"] if mine else []) + ([f"user_id={int(user_id)}"] if user_id else []) \
            + ([f"season={int(season)}"] if season is not None else [])
        return self._get("/api/games?" + "&".join(q))

    def results(self, game_id): return self._get(f"/api/games/{int(game_id)}/results")
    def replay(self, game_id):
        """The replay of a game (frames for every 2nd step; see docs/api.md)."""
        return self._get(f"/api/replay/{int(game_id)}")

    def live(self):
        """The games being played right now."""
        return self._get("/api/live")
