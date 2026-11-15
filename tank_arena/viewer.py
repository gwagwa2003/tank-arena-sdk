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
  g.fillStyle = css("--wall"); D.walls.forEach(([x, y, w, h]) => g.fillRect(x, y, w, h));
  A[3].forEach(([x, y, o]) => { g.beginPath(); g.arc(x, y, 3.5, 0, Math.PI * 2); g.fillStyle = C[o]; g.fill(); });
  A[2].forEach(([x, y, hd, tu, hp, alive, skill, shield], k) => {
    g.save(); g.translate(x, y); g.globalAlpha = alive ? (D.players[k].module === "stealth" && skill ? .35 : 1) : .25;
    g.save(); g.rotate(hd); g.fillStyle = C[k]; g.fillRect(-16, -12, 32, 24); g.restore();
    g.save(); g.rotate(tu); g.strokeStyle = css("--fg"); g.lineWidth = 4; g.beginPath(); g.moveTo(0, 0); g.lineTo(24, 0); g.stroke(); g.restore();
    if (alive && shield) { g.beginPath(); g.arc(0, 0, 24, 0, Math.PI * 2); g.strokeStyle = "#5ab0ff"; g.lineWidth = 2.5; g.stroke(); }
    g.fillStyle = "#1f9d55"; g.fillRect(-23, 20, 46 * hp, 5); g.restore();
  });
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
