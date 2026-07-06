import os, sqlite3, requests
from datetime import datetime
from flask import Flask, jsonify, request, render_template_string
from flask_cors import CORS
from apscheduler.schedulers.background import BackgroundScheduler
from config import BASE_DIR, LEAGUE_CONFIG
from data_loader import get_team_stats, get_all_team_names, build_team_stats_from_csv
from models import master_analyze
from teams_static import STATIC_TEAMS, total_static_team_count
from kupon_yonetimi import init_kupon_tables, mevcut_bankroll, bankroll_ekle, kupon_olustur, kupon_sonucla, performans_raporu

app = Flask(__name__)
CORS(app)

DB_PATH = os.path.join(BASE_DIR, "bozkurt.db")
FOOTBALL_DATA_KEY = os.environ.get("FOOTBALL_DATA_KEY", "")
ENABLE_LIVE_DATA = os.environ.get("ENABLE_LIVE_DATA", "true").lower() == "true"
ENABLE_SCHEDULER = os.environ.get("ENABLE_SCHEDULER", "true").lower() == "true"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS matches (
            id TEXT PRIMARY KEY,
            home_team TEXT, away_team TEXT, league TEXT, match_date TEXT,
            status TEXT DEFAULT 'scheduled',
            odds_home REAL, odds_draw REAL, odds_away REAL,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS value_bets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id TEXT, bet_type TEXT, odds REAL, probability REAL,
            ev REAL, kelly_stake REAL, created_at TEXT, result TEXT DEFAULT 'pending'
        );
        CREATE TABLE IF NOT EXISTS bultens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT, content TEXT, created_at TEXT
        );
    """)
    conn.commit()
    conn.close()

init_db()
_kupon_conn = get_db()
init_kupon_tables(_kupon_conn)
_kupon_conn.close()

def fetch_live_matches():
    matches = []
    try:
        url = "https://www.thesportsdb.com/api/v1/json/3/eventsnextleague.php?id=4328"
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            events = (r.json() or {}).get("events") or []
            for e in events[:20]:
                matches.append({
                    "id": str(e.get("idEvent","")),
                    "home": e.get("strHomeTeam",""), "away": e.get("strAwayTeam",""),
                    "league": e.get("strLeague",""),
                    "date": e.get("dateEvent","")+" "+(e.get("strTime","") or "15:00"),
                    "status": "scheduled",
                    "odds_home": 2.0, "odds_draw": 3.3, "odds_away": 3.5,
                })
    except: pass
    if FOOTBALL_DATA_KEY:
        try:
            headers = {"X-Auth-Token": FOOTBALL_DATA_KEY}
            r = requests.get("https://api.football-data.org/v4/matches?status=SCHEDULED", headers=headers, timeout=10)
            if r.status_code == 200:
                for m in r.json().get("matches",[])[:30]:
                    matches.append({
                        "id": str(m["id"]),
                        "home": m["homeTeam"]["name"], "away": m["awayTeam"]["name"],
                        "league": m["competition"]["name"],
                        "date": m["utcDate"][:16].replace("T"," "),
                        "status": m["status"],
                        "odds_home": 2.0, "odds_draw": 3.3, "odds_away": 3.5,
                    })
        except: pass
    return matches

def auto_refresh_matches():
    if not ENABLE_LIVE_DATA: return
    matches = fetch_live_matches()
    conn = get_db()
    for m in matches:
        try:
            conn.execute("""INSERT OR REPLACE INTO matches
                (id,home_team,away_team,league,match_date,status,odds_home,odds_draw,odds_away,created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (m["id"],m["home"],m["away"],m["league"],m["date"],
                 m["status"],m["odds_home"],m["odds_draw"],m["odds_away"],
                 datetime.now().isoformat()))
        except: pass
    conn.commit()
    conn.close()
    print(f"✅ {len(matches)} maç güncellendi")

def generate_daily_bulten():
    conn = get_db()
    matches = conn.execute("SELECT * FROM matches WHERE date(match_date)=date('now') AND status='scheduled'").fetchall()
    conn.close()
    bulten = f"📋 BOZKURT AI - GÜNLÜK BÜLTEN ({datetime.now().strftime('%d.%m.%Y')})\n\n"
    bulten += f"📊 Bugün {len(matches)} maç\n\n"
    for m in matches[:10]:
        bulten += f"⚽ {m['home_team']} vs {m['away_team']} ({m['league']})\n   {m['match_date']}\n\n"
    bulten += "🐺 Bozkurt AI\n"
    conn = get_db()
    conn.execute("INSERT INTO bultens (date,content,created_at) VALUES (?,?,?)",
                 (datetime.now().date().isoformat(), bulten, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return bulten

if ENABLE_SCHEDULER:
    scheduler = BackgroundScheduler()
    scheduler.add_job(auto_refresh_matches, "interval", minutes=30)
    scheduler.add_job(generate_daily_bulten, "cron", hour=7, minute=0)
    scheduler.start()
    auto_refresh_matches()

build_team_stats_from_csv()

@app.route("/")
def index():
    return render_template_string(HTML)

@app.route("/api/matches")
def get_matches():
    conn = get_db()
    league = request.args.get("league","all")
    search = request.args.get("search","")
    q = "SELECT * FROM matches WHERE status='scheduled'"
    params = []
    if league != "all": q += " AND league=?"; params.append(league)
    if search: q += " AND (home_team LIKE ? OR away_team LIKE ?)"; params+=[f"%{search}%"]*2
    q += " ORDER BY match_date LIMIT 100"
    rows = conn.execute(q, params).fetchall()
    conn.close()
    return jsonify({"status":"ok","matches":[dict(r) for r in rows],"count":len(rows)})

@app.route("/api/analyze/<match_id>")
def analyze_match(match_id):
    conn = get_db()
    m = conn.execute("SELECT * FROM matches WHERE id=?", (match_id,)).fetchone()
    conn.close()
    if not m: return jsonify({"status":"error","message":"Maç bulunamadı"})
    m = dict(m)
    home = get_team_stats(m["home_team"], m["league"])
    away = get_team_stats(m["away_team"], m["league"])
    odds = {"home":m.get("odds_home",2.0),"draw":m.get("odds_draw",3.3),"away":m.get("odds_away",3.5)}
    result = master_analyze(home, away, odds)
    if result["value_bet"]:
        conn = get_db()
        side_odds = odds["home"] if result["value_bet"]=="Ev" else odds["draw"] if result["value_bet"]=="Beraberlik" else odds["away"]
        side_prob = result["home_prob"] if result["value_bet"]=="Ev" else result["draw_prob"] if result["value_bet"]=="Beraberlik" else result["away_prob"]
        conn.execute("""INSERT INTO value_bets (match_id,bet_type,odds,probability,ev,kelly_stake,created_at)
            VALUES (?,?,?,?,?,?,?)""",
            (match_id,result["value_bet"],side_odds,side_prob,
             max(result["ev_home"],result["ev_draw"],result["ev_away"]),
             result["kelly_stake"],datetime.now().isoformat()))
        conn.commit()
        conn.close()
    return jsonify({"status":"ok","match":m,"result":result})

@app.route("/api/analyze/custom", methods=["POST"])
def analyze_custom():
    data = request.json or {}
    home_name = data.get("home","")
    away_name = data.get("away","")
    league = data.get("league","")
    odds = data.get("odds",{"home":2.0,"draw":3.3,"away":3.5})
    bankroll = data.get("bankroll",1000)
    if not home_name or not away_name:
        return jsonify({"status":"error","message":"Takım adı gerekli"})
    home = get_team_stats(home_name, league)
    away = get_team_stats(away_name, league)
    result = master_analyze(home, away, odds, bankroll=bankroll)
    return jsonify({"status":"ok","result":result})

@app.route("/api/teams")
def get_teams():
    search = request.args.get("q","")
    names = get_all_team_names(search)
    return jsonify({"status":"ok","teams":[{"name":n} for n in names[:100]]})

@app.route("/api/leagues")
def get_leagues():
    leagues = list(STATIC_TEAMS.keys())
    return jsonify({"status":"ok","leagues":leagues})

@app.route("/api/teams_by_league")
def get_teams_by_league():
    league = request.args.get("league","")
    teams = STATIC_TEAMS.get(league, [])
    return jsonify({"status":"ok","league":league,"teams":sorted(teams)})

@app.route("/api/bankroll", methods=["GET"])
def bankroll_gor():
    conn = get_db()
    bakiye = mevcut_bankroll(conn)
    conn.close()
    return jsonify({"status":"ok","bankroll":bakiye})

@app.route("/api/bankroll", methods=["POST"])
def bankroll_ekle_route():
    data = request.json or {}
    miktar = float(data.get("miktar", 0))
    aciklama = data.get("aciklama", "")
    conn = get_db()
    yeni = bankroll_ekle(conn, miktar, aciklama)
    conn.close()
    return jsonify({"status":"ok","yeni_bankroll":yeni})

@app.route("/api/kupon", methods=["POST"])
def kupon_olustur_route():
    data = request.json or {}
    conn = get_db()
    sonuc = kupon_olustur(
        conn,
        match_id=data.get("match_id",""),
        ev_sahibi=data.get("ev_sahibi",""),
        deplasman=data.get("deplasman",""),
        lig=data.get("lig",""),
        secim=data.get("secim",""),
        oran=float(data.get("oran",1.0)),
        stake=float(data.get("stake",0)),
    )
    conn.close()
    return jsonify({"status":"ok", **sonuc})

@app.route("/api/kupon/<kupon_id>/sonuc", methods=["POST"])
def kupon_sonuc_route(kupon_id):
    data = request.json or {}
    conn = get_db()
    sonuc = kupon_sonucla(conn, kupon_id, data.get("sonuc","kaybetti"))
    conn.close()
    return jsonify({"status":"ok", **sonuc})

@app.route("/api/kuponlar")
def kuponlar_listele():
    conn = get_db()
    rows = conn.execute("SELECT * FROM kuponlar ORDER BY tarih DESC LIMIT 50").fetchall()
    conn.close()
    return jsonify({"status":"ok","kuponlar":[dict(r) for r in rows]})

@app.route("/api/performans")
def performans_route():
    gun = int(request.args.get("gun", 30))
    conn = get_db()
    rapor = performans_raporu(conn, gun)
    conn.close()
    return jsonify({"status":"ok","rapor":rapor})

@app.route("/api/bulten")
def get_bulten():
    conn = get_db()
    b = conn.execute("SELECT * FROM bultens ORDER BY created_at DESC LIMIT 1").fetchone()
    conn.close()
    if b: return jsonify({"status":"ok","bulten":dict(b)})
    return jsonify({"status":"ok","bulten":{"content":generate_daily_bulten()}})

@app.route("/api/value_bets")
def get_value_bets():
    conn = get_db()
    rows = conn.execute("SELECT * FROM value_bets ORDER BY created_at DESC LIMIT 20").fetchall()
    conn.close()
    return jsonify({"status":"ok","value_bets":[dict(r) for r in rows]})

@app.route("/api/refresh")
def manual_refresh():
    auto_refresh_matches()
    return jsonify({"status":"ok","message":"Güncellendi"})

@app.route("/api/stats")
def get_stats():
    conn = get_db()
    total_m = conn.execute("SELECT COUNT(*) FROM matches").fetchone()[0]
    total_vb = conn.execute("SELECT COUNT(*) FROM value_bets").fetchone()[0]
    conn.close()
    teams = build_team_stats_from_csv()
    return jsonify({"status":"ok","stats":{
        "matches":total_m,"value_bets":total_vb,
        "leagues":len(STATIC_TEAMS),
        "total_teams_db":len(teams) or total_static_team_count(),
        "models":10,"filters":21,
    }})

HTML = """<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>🐺 BOZKURT AI - OMEGA V10</title>
<script src="https://cdn.tailwindcss.com"></script>
<style>
*{box-sizing:border-box}
body{background:#0a0e1a;color:#e2e8f0;font-family:system-ui}
.glass{background:rgba(255,255,255,0.05);backdrop-filter:blur(10px);border:1px solid rgba(255,255,255,0.1);border-radius:12px}
.tab{padding:8px 16px;border-radius:8px;cursor:pointer;font-size:14px}
.tab.active{background:#3b82f6;color:white}
.tab:not(.active){background:rgba(255,255,255,0.05);color:#94a3b8}
input,select{background:rgba(255,255,255,0.08);border:1px solid rgba(255,255,255,0.15);border-radius:8px;color:white;padding:8px 12px;width:100%;outline:none}
.match-card{padding:12px;border-radius:10px;border:1px solid rgba(255,255,255,0.08);background:rgba(255,255,255,0.03);cursor:pointer;transition:all .2s}
.match-card:hover{background:rgba(59,130,246,0.1);border-color:rgba(59,130,246,0.3)}
.prob-bar{height:8px;border-radius:4px;overflow:hidden;display:flex;gap:2px}
.spinner{border:3px solid rgba(255,255,255,0.1);border-top:3px solid #3b82f6;border-radius:50%;width:32px;height:32px;animation:spin .8s linear infinite;margin:auto}
@keyframes spin{to{transform:rotate(360deg)}}
.badge{padding:3px 8px;border-radius:20px;font-size:11px;font-weight:600}
</style>
</head>
<body>
<nav style="background:rgba(0,0,0,.6);backdrop-filter:blur(20px);border-bottom:1px solid rgba(255,255,255,.08);padding:12px 16px;position:sticky;top:0;z-index:100">
<div style="max-width:1200px;margin:auto;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px">
<div style="display:flex;align-items:center;gap:10px">
<span style="font-size:28px">🐺</span>
<div>
<div style="font-weight:800;font-size:18px;letter-spacing:1px">BOZKURT AI <span style="color:#3b82f6">V10</span></div>
<div style="font-size:11px;color:#64748b">300K Maç • 10 Model • 21 Filtre • İkiz Cetvel</div>
</div>
</div>
<div style="display:flex;gap:8px;flex-wrap:wrap">
<span class="badge" style="background:rgba(34,197,94,.2);color:#22c55e">🟢 Canlı</span>
<span class="badge" style="background:rgba(168,85,247,.2);color:#c084fc">10 Model</span>
<span class="badge" style="background:rgba(245,158,11,.2);color:#fbbf24">21 Filtre</span>
<button onclick="manualRefresh()" style="background:rgba(59,130,246,.2);border:1px solid rgba(59,130,246,.3);color:#60a5fa;padding:6px 12px;border-radius:8px;font-size:12px;cursor:pointer">🔄 Güncelle</button>
</div>
</div>
</nav>
<div style="max-width:1200px;margin:auto;padding:16px">
<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:12px;margin-bottom:20px">
<div class="glass" style="padding:14px;text-align:center"><div style="font-size:22px;font-weight:800;color:#22c55e" id="statMatches">-</div><div style="font-size:11px;color:#64748b">Bugünkü Maç</div></div>
<div class="glass" style="padding:14px;text-align:center"><div style="font-size:22px;font-weight:800;color:#f59e0b" id="statVB">-</div><div style="font-size:11px;color:#64748b">Value Bet</div></div>
<div class="glass" style="padding:14px;text-align:center"><div style="font-size:22px;font-weight:800;color:#60a5fa" id="statTeams">-</div><div style="font-size:11px;color:#64748b">Takım</div></div>
<div class="glass" style="padding:14px;text-align:center"><div style="font-size:22px;font-weight:800;color:#c084fc">10</div><div style="font-size:11px;color:#64748b">Model</div></div>
<div class="glass" style="padding:14px;text-align:center"><div style="font-size:22px;font-weight:800;color:#f87171">21</div><div style="font-size:11px;color:#64748b">Filtre</div></div>
</div>
<div style="display:flex;gap:8px;margin-bottom:16px;overflow-x:auto;padding-bottom:4px">
<button class="tab active" onclick="switchTab('matches',this)">⚽ Maçlar</button>
<button class="tab" onclick="switchTab('manual',this)">🔍 Manuel Analiz</button>
<button class="tab" onclick="switchTab('valuebets',this)">💰 Value Betler</button>
<button class="tab" onclick="switchTab('bulten',this)">📋 Bülten</button>
<button class="tab" onclick="switchTab('kuponlar',this)">🎫 Kuponlarım</button>
</div>
<div id="tab-matches">
<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:12px">
<input type="text" id="searchInput" placeholder="Takım ara..." oninput="filterMatches()">
<select id="leagueFilter" onchange="filterMatches()"><option value="all">Tüm Ligler</option></select>
</div>
<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
<div>
<div style="font-size:13px;color:#64748b;margin-bottom:8px" id="matchCount">Yükleniyor...</div>
<div id="matchList" style="display:flex;flex-direction:column;gap:8px;max-height:70vh;overflow-y:auto"></div>
</div>
<div id="analysisPanel" class="glass" style="padding:16px;height:fit-content;position:sticky;top:80px">
<div style="text-align:center;color:#475569;padding:40px 0"><div style="font-size:40px">🐺</div><div>Maç seçin</div></div>
</div>
</div>
</div>
<div id="tab-manual" style="display:none">
<div class="glass" style="padding:20px;max-width:600px">
<h3 style="margin:0 0 16px;color:#60a5fa">🔍 Manuel Analiz</h3>
<div style="display:flex;flex-direction:column;gap:10px">
<select id="leagueInput" onchange="onLeagueChange()"><option value="">Önce lig seçin...</option></select>
<select id="homeInput"><option value="">Önce lig seçin...</option></select>
<select id="awayInput"><option value="">Önce lig seçin...</option></select>
<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px">
<input type="number" id="oddsHome" value="2.00" step="0.01" placeholder="MS1">
<input type="number" id="oddsDraw" value="3.30" step="0.01" placeholder="X">
<input type="number" id="oddsAway" value="3.50" step="0.01" placeholder="MS2">
</div>
<input type="number" id="bankrollInput" value="1000" placeholder="Bankroll (TL)">
<button onclick="runManualAnalysis()" style="background:#3b82f6;color:white;border:none;padding:12px;border-radius:8px;font-size:15px;font-weight:600;cursor:pointer">🧠 ANALİZ ET</button>
</div>
</div>
<div id="manualResult" style="margin-top:16px"></div>
<datalist id="teamList"></datalist>
</div>
<div id="tab-valuebets" style="display:none"><div id="valueBetList"></div></div>
<div id="tab-bulten" style="display:none"><div class="glass" style="padding:20px;white-space:pre-wrap;font-family:monospace;font-size:13px" id="bultenContent">Yükleniyor...</div></div>
<div id="tab-kuponlar" style="display:none">
  <div class="glass" style="padding:16px;margin-bottom:16px">
    <h3 style="margin:0 0 12px;color:#60a5fa">💰 Bankroll</h3>
    <div style="font-size:24px;font-weight:800;color:#22c55e;margin-bottom:12px" id="bankrollValue">-</div>
    <div style="display:flex;gap:8px">
      <input type="number" id="bankrollAmount" placeholder="Miktar">
      <button onclick="bankrollIslem(1)" style="background:#22c55e;color:white;border:none;padding:8px 14px;border-radius:8px;cursor:pointer">+ Yatır</button>
      <button onclick="bankrollIslem(-1)" style="background:#ef4444;color:white;border:none;padding:8px 14px;border-radius:8px;cursor:pointer">- Çek</button>
    </div>
  </div>
  <div class="glass" style="padding:16px;margin-bottom:16px" id="performansPanel">Yükleniyor...</div>
  <div id="kuponListesi"></div>
</div>
</div>
<script>
let allMatches=[],currentMatchId=null;
let lastAnalysisContext=null;
async function loadStats(){
  try{const r=await fetch('/api/stats');const d=await r.json();
  if(d.status==='ok'){document.getElementById('statTeams').textContent=d.stats.total_teams_db;document.getElementById('statVB').textContent=d.stats.value_bets;}}catch(e){}
}
async function loadMatches(){
  try{const r=await fetch('/api/matches');const d=await r.json();
  allMatches=d.matches||[];document.getElementById('statMatches').textContent=allMatches.length;
  populateLeagueFilter();renderMatches();}
  catch(e){document.getElementById('matchList').innerHTML='<div style="color:#f87171;text-align:center;padding:20px">Yüklenemedi</div>';}
}
async function loadLeagues(){
  try{const r=await fetch('/api/leagues');const d=await r.json();
  const ls=document.getElementById('leagueInput');
  (d.leagues||[]).forEach(l=>{const o=document.createElement('option');o.value=l;o.textContent=l;ls.appendChild(o);});}catch(e){}
}
async function loadTeams(){
  try{const r=await fetch('/api/teams');const d=await r.json();
  const dl=document.getElementById('teamList');
  (d.teams||[]).forEach(t=>{const o=document.createElement('option');o.value=t.name;dl.appendChild(o);});}catch(e){}
}
function populateLeagueFilter(){
  const leagues=[...new Set(allMatches.map(m=>m.league))].filter(Boolean).sort();
  const sel=document.getElementById('leagueFilter');
  leagues.forEach(l=>{const o=document.createElement('option');o.value=l;o.textContent=l;sel.appendChild(o);});
}
function filterMatches(){
  const search=document.getElementById('searchInput').value.toLowerCase();
  const league=document.getElementById('leagueFilter').value;
  const filtered=allMatches.filter(m=>{
    const ms=!search||(m.home_team||'').toLowerCase().includes(search)||(m.away_team||'').toLowerCase().includes(search);
    const ml=league==='all'||m.league===league;return ms&&ml;});
  renderMatches(filtered);
}
function renderMatches(matches){
  const list=matches||allMatches;
  document.getElementById('matchCount').textContent=`${list.length} maç`;
  if(!list.length){document.getElementById('matchList').innerHTML='<div style="color:#64748b;text-align:center;padding:30px">Maç bulunamadı. Manuel Analiz sekmesini kullanın.</div>';return;}
  document.getElementById('matchList').innerHTML=list.map(m=>`
    <div class="match-card" onclick="analyzeMatch('${m.id}')">
      <div style="font-size:11px;color:#3b82f6;font-weight:600">${m.league||''}</div>
      <div style="display:flex;justify-content:space-between;align-items:center;margin-top:4px">
        <div style="font-weight:600;font-size:14px">${m.home_team||''}</div>
        <div style="color:#475569;font-size:12px;font-weight:700">VS</div>
        <div style="font-weight:600;font-size:14px">${m.away_team||''}</div>
      </div>
      <div style="font-size:10px;color:#475569;margin-top:4px">${m.match_date||''}</div>
    </div>`).join('');
}
async function analyzeMatch(matchId){
  currentMatchId=matchId;
  const panel=document.getElementById('analysisPanel');
  panel.innerHTML='<div style="padding:40px 0"><div class="spinner"></div></div>';
  try{const r=await fetch(`/api/analyze/${matchId}`);const d=await r.json();
  if(d.status==='ok'){lastAnalysisContext={matchId:d.match.id,home:d.match.home_team,away:d.match.away_team,league:d.match.league,odds:{home:d.match.odds_home,draw:d.match.odds_draw,away:d.match.odds_away},result:d.result};panel.innerHTML=renderAnalysisHTML(d.result,`${d.match.home_team} vs ${d.match.away_team}`,d.match.league,d.match.match_date);}
  else panel.innerHTML='<div style="color:#f87171;text-align:center;padding:30px">Hata</div>';}
  catch(e){panel.innerHTML='<div style="color:#f87171;text-align:center;padding:30px">Bağlantı hatası</div>';}
}
function renderAnalysisHTML(r,title,league,date){
  return `<div style="display:flex;flex-direction:column;gap:12px">
  <div style="text-align:center;padding-bottom:12px;border-bottom:1px solid rgba(255,255,255,.08)">
    <div style="font-weight:700;font-size:15px">${title}</div>
    <div style="font-size:11px;color:#64748b">${league||''} • ${date||''}</div>
  </div>
  <div>
    <div style="display:flex;justify-content:space-between;font-size:12px;margin-bottom:4px">
      <span style="color:#60a5fa;font-weight:600">Ev %${r.home_prob}</span>
      <span style="color:#94a3b8">Ber %${r.draw_prob}</span>
      <span style="color:#f87171;font-weight:600">Dep %${r.away_prob}</span>
    </div>
    <div class="prob-bar">
      <div style="width:${r.home_prob}%;background:#3b82f6;height:100%"></div>
      <div style="width:${r.draw_prob}%;background:#475569;height:100%"></div>
      <div style="width:${r.away_prob}%;background:#ef4444;height:100%"></div>
    </div>
  </div>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">
    <div class="glass" style="padding:10px;text-align:center"><div style="font-size:22px;font-weight:800;color:#f59e0b">${r.score}</div><div style="font-size:10px;color:#64748b">En Olası Skor</div></div>
    <div class="glass" style="padding:10px;text-align:center"><div style="font-size:22px;font-weight:800;color:#c084fc">%${r.confidence}</div><div style="font-size:10px;color:#64748b">Güven</div></div>
  </div>
  <div class="glass" style="padding:10px;font-size:12px">
    <div style="color:#64748b;margin-bottom:4px">No-Vig • Marj %${r.overround_margin}</div>
    Ev: ${r.novig.home}% | Ber: ${r.novig.draw}% | Dep: ${r.novig.away}%
  </div>
  <div class="glass" style="padding:10px;font-size:12px;line-height:1.8">
    <div style="color:#64748b;margin-bottom:4px">Modeller</div>
    ELO: ${r.elo.home}/${r.elo.draw}/${r.elo.away}<br>
    Poisson: ${r.poisson.home}/${r.poisson.draw}/${r.poisson.away}<br>
    Monte Carlo: ${r.monte_carlo.home}/${r.monte_carlo.draw}/${r.monte_carlo.away}<br>
    Asian HCP: ${r.asian_handicap.rec}<br>
    BTTS: ${r.btts.rec} (%${r.btts.yes})<br>
    Alt/Üst 2.5: ${r.over_under.rec}<br>
    Korner: ${r.corners.rec}<br>
    Filtre: %${r.filter_pct} ${r.filter_passed?'✅':'⚠️'}<br>
    İkiz Cetvel: Ev ${r.twin_cetvel['ÖZET'].home_wins} - Dep ${r.twin_cetvel['ÖZET'].away_wins}
  </div>
  <div class="glass" style="padding:12px;${r.value_bet?'border:1px solid rgba(34,197,94,.5)':''}">
    <div style="font-weight:700;${r.value_bet?'color:#22c55e':'color:#94a3b8'}">${r.recommendation}</div>
  </div>
  <button onclick="kuponaEkle()" style="background:#f59e0b;color:#000;border:none;padding:10px;border-radius:8px;font-weight:700;cursor:pointer;width:100%">🎫 Kupona Ekle</button>
  </div>`;
}
async function runManualAnalysis(){
  const home=document.getElementById('homeInput').value.trim();
  const away=document.getElementById('awayInput').value.trim();
  if(!home||!away){alert('İki takım da girin');return;}
  const league=document.getElementById('leagueInput').value;
  const bankroll=parseFloat(document.getElementById('bankrollInput').value)||1000;
  const odds={home:parseFloat(document.getElementById('oddsHome').value),draw:parseFloat(document.getElementById('oddsDraw').value),away:parseFloat(document.getElementById('oddsAway').value)};
  const box=document.getElementById('manualResult');
  box.innerHTML='<div style="padding:30px 0"><div class="spinner"></div></div>';
  try{const r=await fetch('/api/analyze/custom',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({home,away,league,odds,bankroll})});
  const d=await r.json();
  if(d.status==='ok'){lastAnalysisContext={matchId:null,home,away,league,odds,result:d.result};box.innerHTML='<div class="glass" style="padding:16px">'+renderAnalysisHTML(d.result,`${home} vs ${away}`,league,'')+'</div>';}
  else box.innerHTML=`<div style="color:#f87171;padding:16px">${d.message||'Hata'}</div>`;}
  catch(e){box.innerHTML='<div style="color:#f87171;padding:16px">Bağlantı hatası</div>';}
}
async function loadValueBets(){
  try{const r=await fetch('/api/value_bets');const d=await r.json();
  const list=d.value_bets||[];
  document.getElementById('valueBetList').innerHTML=list.length?list.map(v=>`
    <div class="glass" style="padding:14px;margin-bottom:8px;border-left:3px solid #22c55e">
      <div style="font-weight:700;color:#22c55e">${v.bet_type} @ ${v.odds}</div>
      <div style="font-size:12px;color:#64748b">Olasılık: %${v.probability} | EV: %${v.ev} | Kelly: ${v.kelly_stake} TL</div>
      <div style="font-size:10px;color:#475569;margin-top:4px">${v.created_at}</div>
    </div>`).join(''):'<div style="color:#64748b;text-align:center;padding:30px">Henüz value bet yok</div>';}catch(e){}
}
async function loadBulten(){
  try{const r=await fetch('/api/bulten');const d=await r.json();
  document.getElementById('bultenContent').textContent=(d.bulten&&d.bulten.content)||'Bülten yok';}catch(e){}
}
async function manualRefresh(){await fetch('/api/refresh');await loadMatches();await loadStats();}
function switchTab(tab,el){
  document.querySelectorAll('[id^="tab-"]').forEach(t=>t.style.display='none');
  document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
  document.getElementById('tab-'+tab).style.display='block';
  el.classList.add('active');
  if(tab==='matches')loadMatches();
  if(tab==='valuebets')loadValueBets();
  if(tab==='bulten')loadBulten();
  if(tab==='kuponlar'){loadKuponlar();loadPerformans();loadBankroll();}
}
async function onLeagueChange(){
  const league=document.getElementById('leagueInput').value;
  const homeSel=document.getElementById('homeInput');
  const awaySel=document.getElementById('awayInput');
  if(!league){homeSel.innerHTML='<option value="">Önce lig seçin...</option>';awaySel.innerHTML='<option value="">Önce lig seçin...</option>';return;}
  homeSel.innerHTML='<option value="">Yükleniyor...</option>';
  awaySel.innerHTML='<option value="">Yükleniyor...</option>';
  try{
    const r=await fetch(`/api/teams_by_league?league=${encodeURIComponent(league)}`);
    const d=await r.json();
    const teams=d.teams||[];
    const opts='<option value="">Takım seçin...</option>'+teams.map(t=>`<option value="${t}">${t}</option>`).join('');
    homeSel.innerHTML=opts;
    awaySel.innerHTML=opts;
  }catch(e){homeSel.innerHTML='<option value="">Yüklenemedi</option>';awaySel.innerHTML='<option value="">Yüklenemedi</option>';}
}
async function kuponaEkle(){
  if(!lastAnalysisContext){alert('Önce analiz yapın');return;}
  const c=lastAnalysisContext;
  const r=c.result;
  let secim=r.value_bet||'MS1';
  let oran=c.odds.home;
  if(secim==='Beraberlik')oran=c.odds.draw;
  else if(secim==='Deplasman')oran=c.odds.away;
  const stakeStr=prompt('Stake miktarı (TL):','50');
  if(!stakeStr)return;
  const stake=parseFloat(stakeStr);
  if(!stake||stake<=0){alert('Geçersiz miktar');return;}
  try{
    const res=await fetch('/api/kupon',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
      match_id:c.matchId||'',ev_sahibi:c.home,deplasman:c.away,lig:c.league||'',secim,oran,stake
    })});
    const d=await res.json();
    if(d.status==='ok'){alert(`Kupon oluşturuldu! Kalan bankroll: ${d.bankroll_kalan} TL`);}
    else{alert('Hata: '+(d.message||'bilinmeyen'));}
  }catch(e){alert('Bağlantı hatası');}
}
async function loadBankroll(){
  try{const r=await fetch('/api/bankroll');const d=await r.json();
  document.getElementById('bankrollValue').textContent=d.bankroll.toFixed(2);}catch(e){}
}
async function bankrollIslem(yon){
  const val=parseFloat(document.getElementById('bankrollAmount').value);
  if(!val||val<=0){alert('Geçerli bir miktar girin');return;}
  try{await fetch('/api/bankroll',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({miktar:val*yon,aciklama:yon>0?'Yatırım':'Çekim'})});
  document.getElementById('bankrollAmount').value='';
  loadBankroll();}catch(e){}
}
async function loadPerformans(){
  try{const r=await fetch('/api/performans');const d=await r.json();
  const p=d.rapor;
  document.getElementById('performansPanel').innerHTML=p.toplam_kupon?`
    <h3 style="margin:0 0 10px;color:#60a5fa">📊 Son ${p.donem_gun} Gün Performans</h3>
    <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px;font-size:13px">
      <div>Toplam: <b>${p.toplam_kupon}</b></div>
      <div style="color:#22c55e">Kazanan: <b>${p.kazanan}</b></div>
      <div style="color:#f87171">Kaybeden: <b>${p.kaybeden}</b></div>
      <div>Kazanma: <b>%${p.kazanma_orani}</b></div>
      <div>ROI: <b>%${p.roi_yuzde}</b></div>
      <div>Bankroll: <b>${p.mevcut_bankroll} TL</b></div>
    </div>`:`<div style="color:#64748b">${p.mesaj||'Veri yok'}</div>`;
  }catch(e){}
}
async function loadKuponlar(){
  try{const r=await fetch('/api/kuponlar');const d=await r.json();
  const list=d.kuponlar||[];
  document.getElementById('kuponListesi').innerHTML=list.length?list.map(k=>`
    <div class="glass" style="padding:12px;margin-bottom:8px;border-left:3px solid ${k.sonuc==='kazandi'?'#22c55e':k.sonuc==='kaybetti'?'#ef4444':'#64748b'}">
      <div style="font-weight:700">${k.ev_sahibi} vs ${k.deplasman} <span style="color:#64748b;font-size:11px">(${k.lig||''})</span></div>
      <div style="font-size:12px;color:#94a3b8">${k.secim} @ ${k.oran} • Stake: ${k.stake} TL • Olası kazanç: ${k.potansiyel_kazanc} TL</div>
      <div style="font-size:12px;margin-top:4px">Durum: <b>${k.sonuc}</b> ${k.sonuc==='bekliyor'?`
        <button onclick="kuponSonuclandir('${k.kupon_id}','kazandi')" style="background:#22c55e;color:#000;border:none;padding:3px 8px;border-radius:6px;font-size:11px;margin-left:6px;cursor:pointer">Kazandı</button>
        <button onclick="kuponSonuclandir('${k.kupon_id}','kaybetti')" style="background:#ef4444;color:#fff;border:none;padding:3px 8px;border-radius:6px;font-size:11px;margin-left:4px;cursor:pointer">Kaybetti</button>
      `:''}</div>
    </div>`).join(''):'<div style="color:#64748b;text-align:center;padding:20px">Henüz kupon yok</div>';
  }catch(e){}
}
async function kuponSonuclandir(kuponId,sonuc){
  try{await fetch(`/api/kupon/${kuponId}/sonuc`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({sonuc})});
  loadKuponlar();loadPerformans();loadBankroll();}catch(e){}
}
loadStats();loadMatches();loadLeagues();loadTeams();
</script>
</body>
</html>"""

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)

print("✅ app.py hazır!")