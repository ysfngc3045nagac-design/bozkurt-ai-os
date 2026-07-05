import sys
sys.path.insert(0, '/content/drive/MyDrive/Bozkurtasena')

from flask import Flask, jsonify, request
from analiz import analiz

app = Flask(__name__)

HTML = """<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>🐺 Bozkurt AI</title>
<style>
* { margin:0; padding:0; box-sizing:border-box; }
body { background:#0a0e17; color:#e0e0e0; font-family:system-ui; padding:16px; }
h1 { color:#ffd700; text-align:center; font-size:1.8em; margin-bottom:4px; }
p.sub { color:#00d4ff; text-align:center; margin-bottom:20px; }
.card { background:#1b2838; border-radius:12px; padding:16px; margin-bottom:16px; border:1px solid #2d3f5a; }
input, select { width:100%; padding:10px; margin:6px 0; background:#0d1b2a; border:1px solid #2d3f5a; color:#e0e0e0; border-radius:8px; font-size:1em; }
button { width:100%; padding:14px; background:linear-gradient(135deg,#00d4ff,#4ad9d9); color:#0a0e17; border:none; border-radius:10px; font-weight:bold; font-size:1em; cursor:pointer; margin-top:8px; }
.sonuc { background:#0d2a1d; border-left:4px solid #4ad94a; border-radius:8px; padding:14px; margin:8px 0; }
.value { background:#1a2d0d; border-left:4px solid #ffd700; border-radius:8px; padding:14px; margin:8px 0; }
.label { color:#a0a0a0; font-size:0.85em; }
.val { color:#ffd700; font-weight:bold; font-size:1.1em; }
.green { color:#4ad94a; } .red { color:#ff4a6a; } .blue { color:#00d4ff; }
#yukleniyor { display:none; text-align:center; padding:20px; color:#00d4ff; }
</style>
</head>
<body>
<h1>🐺 Bozkurt AI</h1>
<p class="sub">OMEGA V10 — Analiz Motoru</p>

<div class="card">
  <input id="ev" placeholder="Ev Sahibi" value="Galatasaray">
  <input id="dep" placeholder="Deplasman" value="Fenerbahçe">
  <select id="lig">
    <option>Süper Lig</option>
    <option>Premier League</option>
    <option>La Liga</option>
    <option>Bundesliga</option>
    <option>Serie A</option>
    <option>Ligue 1</option>
  </select>
  <input id="o1" type="number" step="0.01" placeholder="Ev Oranı" value="2.20">
  <input id="oX" type="number" step="0.01" placeholder="Beraberlik" value="3.20">
  <input id="o2" type="number" step="0.01" placeholder="Deplasman Oranı" value="3.40">
  <input id="ev_elo" type="number" placeholder="Ev ELO (opsiyonel)" value="1550">
  <input id="dep_elo" type="number" placeholder="Dep ELO (opsiyonel)" value="1520">
  <input id="bankroll" type="number" placeholder="Bankroll (TL)" value="1000">
  <button onclick="analizYap()">🔍 ANALİZ ET</button>
</div>

<div id="yukleniyor">⏳ Hesaplanıyor...</div>
<div id="sonuc"></div>

<script>
async function analizYap() {
  document.getElementById('yukleniyor').style.display = 'block';
  document.getElementById('sonuc').innerHTML = '';
  
  const data = {
    ev: document.getElementById('ev').value,
    dep: document.getElementById('dep').value,
    lig: document.getElementById('lig').value,
    o1: parseFloat(document.getElementById('o1').value),
    oX: parseFloat(document.getElementById('oX').value),
    o2: parseFloat(document.getElementById('o2').value),
    ev_elo: parseFloat(document.getElementById('ev_elo').value),
    dep_elo: parseFloat(document.getElementById('dep_elo').value),
    bankroll: parseFloat(document.getElementById('bankroll').value)
  };

  const r = await fetch('/analiz', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(data)});
  const res = await r.json();
  
  document.getElementById('yukleniyor').style.display = 'none';
  
  let html = `<div class="card">
    <div class="label">Maç</div>
    <div class="val">${res.mac}</div>
    <br>
    <div class="label">Beklenen Gol</div>
    <div class="val">Ev: ${res.beklenen_gol.ev} — Dep: ${res.beklenen_gol.dep}</div>
  </div>
  
  <div class="card">
    <div class="label">Poisson Olasılıkları</div><br>
    <div class="sonuc">MS1 (Ev): <span class="green">${res.poisson.MS1}%</span></div>
    <div class="sonuc">MSX (Ber): <span class="blue">${res.poisson.MSX}%</span></div>
    <div class="sonuc">MS2 (Dep): <span class="red">${res.poisson.MS2}%</span></div>
  </div>
  
  <div class="card">
    <div class="label">No-Vig (Gerçek Olasılık) — Marj: %${res.novig.marj}</div><br>
    <div class="sonuc">MS1: <span class="green">${res.novig.MS1}%</span></div>
    <div class="sonuc">MSX: <span class="blue">${res.novig.MSX}%</span></div>
    <div class="sonuc">MS2: <span class="red">${res.novig.MS2}%</span></div>
  </div>
  
  <div class="card">
    <div class="label">Kelly Kriteri (Half Kelly)</div><br>
    <div class="sonuc">MS1: ${res.kelly.MS1.oneri} — ${res.kelly.MS1.miktar} TL (%${res.kelly.MS1.yuzde})</div>
    <div class="sonuc">MSX: ${res.kelly.MSX.oneri} — ${res.kelly.MSX.miktar} TL (%${res.kelly.MSX.yuzde})</div>
    <div class="sonuc">MS2: ${res.kelly.MS2.oneri} — ${res.kelly.MS2.miktar} TL (%${res.kelly.MS2.yuzde})</div>
  </div>`;
  
  if (res.value_betler.length > 0) {
    html += `<div class="card"><div class="label">🎯 Value Bet'ler</div><br>`;
    res.value_betler.forEach(v => {
      html += `<div class="value">
        <span class="val">${v.sonuc}</span> @ ${v.oran} — Edge: <span class="green">+${v.edge}%</span><br>
        Kelly: ${v.kelly.miktar} TL (%${v.kelly.yuzde})
      </div>`;
    });
    html += `</div>`;
  } else {
    html += `<div class="card"><div class="red">⚠️ Bu maçta value bet bulunamadı.</div></div>`;
  }
  
  document.getElementById('sonuc').innerHTML = html;
}
</script>
</body>
</html>"""

@app.route('/')
def home():
    return HTML

@app.route('/analiz', methods=['POST'])
def analiz_endpoint():
    d = request.get_json()
    sonuc = analiz(
        ev=d['ev'], dep=d['dep'], lig=d['lig'],
        o1=d['o1'], oX=d['oX'], o2=d['o2'],
        ev_elo=d.get('ev_elo', 1500),
        dep_elo=d.get('dep_elo', 1500),
        bankroll=d.get('bankroll', 1000)
    )
    return jsonify(sonuc)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

print("✅ app.py hazır!")
