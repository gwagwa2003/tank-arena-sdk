"""Write a replay as one self-contained HTML file you can open in any browser (no server, no internet needed)."""
import json

_PAGE = """<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Tank Arena replay</title><style>
:root{--bg:#fff;--fg:#18191b;--muted:#8b8d93;--arena:#f3f3f1;--wall:#9b978d;--zone:rgba(217,63,63,.12)}
@media (prefers-color-scheme:dark){:root{--bg:#111113;--fg:#ededef;--muted:#7e8087;--arena:#1c1c1f;--wall:#5c5a55;--zone:rgba(240,100,100,.14)}}
body{margin:0;background:var(--bg);color:var(--fg);font:15px system-ui,sans-serif}main{max-width:820px;margin:0 auto;padding:16px}
canvas{width:100%;height:auto;border-radius:10px;display:block}.bar{display:flex;gap:10px;align-items:center;margin:10px 0}
input[type=range]{flex:1}button,select{font:inherit;padding:4px 10px}.p{color:var(--muted)}
</style></head><body><main><div id="who" class="p"></div><canvas id="cv" width="800" height="800"></canvas>
<div class="bar"><button id="play">暫停</button><input type="range" id="seek" min="0" value="0">
<select id="speed"><option value="1">1×</option><option value="2" selected>2×</option><option value="4">4×</option></select><span id="t" class="p"></span></div></main>
<script>
const D = __DATA__, C = ["#e5484d", "#3e8ed0"], cv = document.getElementById("cv"), g = cv.getContext("2d");
const css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
const isV3 = D.rules === "v3_final";
const destWalls = D.walls.filter((w) => w[4]);
document.getElementById("who").textContent = D.players.map((p, i) => `${["●紅", "●藍"][i] || ""} ${p.label}（${p.chassis}+${p.module}）${p.outcome ? " " + p.outcome : ""}`).join("　vs　");
let f = 0, playing = true, last = performance.now();
const seek = document.getElementById("seek"); seek.max = D.frames.length - 1;
seek.oninput = () => { f = +seek.value; };
document.getElementById("play").onclick = (e) => { if (!playing && f >= D.frames.length - 1) f = 0; playing = !playing; e.target.textContent = playing ? "暫停" : "播放"; };
function frame(now) {
  const dt = (now - last) / 1000; last = now;
  if (playing) { f = Math.min(D.frames.length - 1, f + dt * 20 / D.every * +document.getElementById("speed").value); if (f >= D.frames.length - 1) { playing = false; document.getElementById("play").textContent = "重播"; } seek.value = Math.floor(f); }
  const A = D.frames[Math.floor(f)];
  g.fillStyle = css("--arena"); g.fillRect(0, 0, 800, 800);
  g.beginPath(); g.rect(0, 0, 800, 800); g.arc(D.zone[0], D.zone[1], A[1], 0, Math.PI * 2, true); g.fillStyle = css("--zone"); g.fill("evenodd");
  g.fillStyle = css("--wall"); D.walls.forEach(([x, y, w, h, d]) => { if (!d) g.fillRect(x, y, w, h); });
  const hps = (A[5] && A[5][0]) || [];
  destWalls.forEach(([x, y, w, h], idx) => { const hp = hps[idx] === undefined ? 1 : hps[idx]; if (hp <= 0) { g.fillStyle = "rgba(0,0,0,.12)"; g.fillRect(x + 2, y + 2, w - 4, h - 4); return; } g.fillStyle = hp > .5 ? "#38465c" : "#4a3338"; g.fillRect(x, y, w, h); g.strokeStyle = hp > .5 ? "#ffb547" : "#ff604d"; g.lineWidth = 1.5; g.strokeRect(x + .5, y + .5, w - 1, h - 1); if (hp < .8) { g.strokeStyle = "rgba(0,0,0,.6)"; g.beginPath(); g.moveTo(x + 4, y + 4); g.lineTo(x + w * .6, y + h * .65); g.lineTo(x + w - 4, y + h - 4); g.stroke(); } });
  const core = A[5] && A[5][1];
  if (core && core[0]) {
    const [st, cx, cy, prog] = core;
    g.save(); g.beginPath(); g.arc(cx, cy, 42, 0, Math.PI * 2);
    if (st === 1) { g.setLineDash([6, 4]); g.strokeStyle = "rgba(84,217,255,.7)"; g.lineWidth = 1.6; g.stroke(); }
    else { g.fillStyle = "rgba(84,217,255,.12)"; g.fill(); g.strokeStyle = "rgba(84,217,255,.45)"; g.lineWidth = 1.4; g.stroke();
      if (prog) { g.strokeStyle = C[prog > 0 ? 0 : 1]; g.lineWidth = 3.5; g.beginPath(); g.arc(cx, cy, 42, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * Math.min(1, Math.abs(prog) / 30)); g.stroke(); }
      g.beginPath(); for (let n = 0; n < 6; n++) { const a = n * Math.PI / 3; n ? g.lineTo(cx + Math.cos(a) * 10, cy + Math.sin(a) * 10) : g.moveTo(cx + Math.cos(a) * 10, cy + Math.sin(a) * 10); } g.closePath();
      g.fillStyle = "rgba(146,88,255,.45)"; g.fill(); g.strokeStyle = "#54d9ff"; g.lineWidth = 1.5; g.stroke(); }
    g.restore();
  }
  (A[4] || []).forEach(([x, y, r]) => { g.beginPath(); g.arc(x, y, r, 0, Math.PI * 2); g.fillStyle = "rgba(140,145,155,.45)"; g.fill(); });
  A[3].forEach(([x, y, o]) => { g.beginPath(); g.arc(x, y, 3.5, 0, Math.PI * 2); g.fillStyle = C[o]; g.fill(); });
  A[2].forEach(([x, y, hd, tu, hp, alive, skill, shield, , heat, over], k) => {
    g.save(); g.translate(x, y); g.globalAlpha = alive ? (D.players[k].module === "stealth" && skill ? .35 : 1) : .25;
    g.save(); g.rotate(hd); g.fillStyle = C[k]; g.fillRect(-16, -12, 32, 24); g.restore();
    g.save(); g.rotate(tu); g.strokeStyle = over ? "#ff453a" : (heat >= .75 ? "#ff9f0a" : css("--fg")); g.lineWidth = 4; g.beginPath(); g.moveTo(0, 0); g.lineTo(24, 0); g.stroke(); g.restore();
    if (alive && skill && D.players[k].module === "radar") { g.beginPath(); g.arc(0, 0, 32, 0, Math.PI * 2); g.strokeStyle = C[k]; g.lineWidth = 1.5; g.stroke(); }
    if (alive && shield) { g.beginPath(); if (isV3) g.arc(0, 0, 24, tu - 1.134, tu + 1.134); else g.arc(0, 0, 24, 0, Math.PI * 2); g.strokeStyle = "#5ab0ff"; g.lineWidth = 3; g.stroke(); }
    g.fillStyle = "#1f9d55"; g.fillRect(-23, 20, 46 * hp, 5); g.restore();
  });
  (D.bushes || []).forEach(([bx, by, br]) => { g.save(); g.beginPath(); g.arc(bx, by, br, 0, Math.PI * 2); g.fillStyle = "rgba(18,62,60,.45)"; g.fill(); g.setLineDash([5, 5]); g.strokeStyle = "rgba(79,227,193,.5)"; g.lineWidth = 1.2; g.stroke(); g.restore(); });
  document.getElementById("t").textContent = (A[0] / 20).toFixed(1) + " 秒";
  requestAnimationFrame(frame);
}
requestAnimationFrame(frame);
</script></body></html>"""


def replay_html(replay, path):
    """replay: what engine.play(..., replay=True) returns (or client.replay(game_id)). Writes `path`, returns it."""
    with open(path, "w", encoding="utf-8") as f:
        f.write(_PAGE.replace("__DATA__", json.dumps(replay, separators=(",", ":")).replace("</", "<\\/")))
    return path
