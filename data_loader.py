import os, csv, json
from collections import defaultdict
from config import MATCHES_CSV, ELO_CSV, GAMES_CSV, LEAGUE_CONFIG, normalize_league_name
from teams_static import get_static_team, all_static_team_names, total_static_team_count

_CACHE = {"teams": None, "loaded": False}

TEAMS_JSON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "teams_data.json")

def build_team_stats_from_csv():
    if _CACHE["loaded"]: return _CACHE["teams"]

    teams = {}

    # Önce teams_data.json'dan yükle (95K maç verisi)
    if os.path.exists(TEAMS_JSON):
        with open(TEAMS_JSON, 'r', encoding='utf-8') as f:
            teams = json.load(f)
        for t in teams.values():
            t.setdefault("elo", 1500)
            t.setdefault("rank", 10)
            t.setdefault("value", 50)
            t.setdefault("injuries", 0)
            t.setdefault("suspensions", 0)
            # --- BUG FIX: dış kaynaklardan gelen lig isimleri (örn. "English
            # Premier League") kanonik isimle (örn. "Premier League") eşleşmiyordu.
            # Bu satır olmadan get_team_stats lig eşleşmesi bulamıyor, takım
            # istatistiği yerine varsayılan değerler kullanılıyordu.
            if t.get("league"):
                t["league"] = normalize_league_name(t["league"])
            if isinstance(t.get("form"), list):
                pass
            else:
                t["form"] = ["D","D","D","D","D"]
        print(f"✅ teams_data.json'dan {len(teams)} takım yüklendi!")
    else:
        print("⚠️ teams_data.json bulunamadı, varsayılan değerler kullanılacak")

    _CACHE["teams"] = teams
    _CACHE["loaded"] = True
    return teams

def _normalize_name(name):
    import re
    n = name.lower()
    n = re.sub(r'[^a-z0-9]', '', n)
    return n

def _fuzzy_find_team(team_name, teams):
    target = _normalize_name(team_name)
    if not target:
        return None
    best_match = None
    best_score = 0
    for existing_name in teams.keys():
        existing_norm = _normalize_name(existing_name)
        if existing_norm == target:
            return existing_name
        if target in existing_norm or existing_norm in target:
            shorter = min(len(target), len(existing_norm))
            longer = max(len(target), len(existing_norm))
            score = shorter / longer if longer > 0 else 0
            if score > best_score and score > 0.7:
                best_score = score
                best_match = existing_name
    return best_match

def get_team_stats(team_name, league=""):
    league = normalize_league_name(league)
    teams = build_team_stats_from_csv()
    if team_name not in teams:
        fuzzy_match = _fuzzy_find_team(team_name, teams)
        if fuzzy_match:
            team_name = fuzzy_match
    if team_name in teams:
        t = dict(teams[team_name])
        t.setdefault("squad_depth", 5)
        t.setdefault("manager_exp", 5)
        t.setdefault("stadium_capacity", 30000)
        t.setdefault("matches_last7", 2)
        t.setdefault("rest_days", 3)
        t.setdefault("uefa_match_in_3days", False)
        t.setdefault("international_players", 0)
        t.setdefault("cup_match_in_3days", False)
        t.setdefault("new_players", 0)
        t.setdefault("news_factor", 0)
        t.setdefault("style", "balanced")
        t.setdefault("home_points", 0)
        t.setdefault("away_points", 0)
        t.setdefault("goals_for", 0)
        t.setdefault("goals_against", 0)
        t["last5_xg"] = [t["xg"]] * 5
        t["last5_xga"] = [t["xga"]] * 5
        if league and not t.get("league"):
            t["league"] = league
        return t

    # JSON'da yoksa statik listeden bak
    static_league = get_static_team(team_name)
    effective_league = league or static_league or ""
    cfg = LEAGUE_CONFIG.get(effective_league, {"avg_xg": 1.2})
    return {
        "name": team_name, "league": effective_league, "elo": 1500,
        "xg": cfg["avg_xg"], "xga": cfg["avg_xg"],
        "form": ["D","D","D","D","D"], "rank": 10,
        "points": 40, "value": 50, "injuries": 0, "suspensions": 0,
        "home_points": 20, "away_points": 20,
        "goals_for": 30, "goals_against": 30,
        "last5_xg": [cfg["avg_xg"]] * 5,
        "last5_xga": [cfg["avg_xg"]] * 5,
        "squad_depth": 5, "manager_exp": 5,
        "stadium_capacity": 30000, "matches_last7": 2,
        "rest_days": 3, "uefa_match_in_3days": False,
        "international_players": 0, "cup_match_in_3days": False,
        "new_players": 0, "news_factor": 0, "style": "balanced",
    }

def get_all_team_names(search=""):
    teams = build_team_stats_from_csv()
    names = sorted(set(list(teams.keys()) + all_static_team_names()))
    if search:
        names = [n for n in names if search.lower() in n.lower()]
    return names

def get_static_team_count():
    return total_static_team_count()

print("✅ data_loader.py güncellendi! (v2 - lig ismi normalizasyonu)")
