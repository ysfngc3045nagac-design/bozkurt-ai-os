import os, csv
from collections import defaultdict
from config import MATCHES_CSV, ELO_CSV, GAMES_CSV, LEAGUE_CONFIG

_CACHE = {"teams": None, "loaded": False}

COLS = {
    "home_team": ["home_team","HomeTeam","home","Home","team_home"],
    "away_team": ["away_team","AwayTeam","away","Away","team_away"],
    "home_goals": ["home_goals","FTHG","home_score","HomeGoals"],
    "away_goals": ["away_goals","FTAG","away_score","AwayGoals"],
    "league": ["league","League","Div","competition"],
    "home_elo": ["home_elo","elo_home","HomeElo"],
    "away_elo": ["away_elo","elo_away","AwayElo"],
    "team": ["team","Team","club","Club","name"],
    "elo": ["elo","Elo","ELO","rating"],
}

def _find_col(fieldnames, key):
    if not fieldnames: return None
    lower_map={f.lower():f for f in fieldnames}
    for cand in COLS[key]:
        if cand.lower() in lower_map: return lower_map[cand.lower()]
    return None

def _safe_float(v, default=0.0):
    try: return float(v)
    except: return default

def build_team_stats_from_csv():
    if _CACHE["loaded"]: return _CACHE["teams"]
    stats=defaultdict(lambda:{
        "elo":1500.0,"elo_n":0,"goals_for":0,"goals_against":0,
        "played":0,"home_played":0,"away_played":0,
        "home_points":0,"away_points":0,"points":0,
        "results":[],"league":"",
    })

    if os.path.exists(MATCHES_CSV):
        with open(MATCHES_CSV, newline="", encoding="utf-8", errors="ignore") as f:
            reader = csv.DictReader(f)
            fields = reader.fieldnames or []
            c_home=_find_col(fields,"home_team"); c_away=_find_col(fields,"away_team")
            c_hg=_find_col(fields,"home_goals"); c_ag=_find_col(fields,"away_goals")
            c_league=_find_col(fields,"league")
            c_helo=_find_col(fields,"home_elo"); c_aelo=_find_col(fields,"away_elo")
            if c_home and c_away:
                for row in reader:
                    h,a=row.get(c_home,"").strip(),row.get(c_away,"").strip()
                    if not h or not a: continue
                    hg=_safe_float(row.get(c_hg)) if c_hg else None
                    ag=_safe_float(row.get(c_ag)) if c_ag else None
                    league=row.get(c_league,"").strip() if c_league else ""
                    sh,sa=stats[h],stats[a]
                    if league: sh["league"]=sh["league"] or league; sa["league"]=sa["league"] or league
                    if c_helo:
                        he=_safe_float(row.get(c_helo))
                        if he: sh["elo"]=(sh["elo"]*sh["elo_n"]+he)/(sh["elo_n"]+1); sh["elo_n"]+=1
                    if c_aelo:
                        ae=_safe_float(row.get(c_aelo))
                        if ae: sa["elo"]=(sa["elo"]*sa["elo_n"]+ae)/(sa["elo_n"]+1); sa["elo_n"]+=1
                    if hg is not None and ag is not None:
                        sh["goals_for"]+=hg; sh["goals_against"]+=ag
                        sa["goals_for"]+=ag; sa["goals_against"]+=hg
                        sh["played"]+=1; sa["played"]+=1
                        sh["home_played"]+=1; sa["away_played"]+=1
                        if hg>ag: sh["points"]+=3; sh["home_points"]+=3; sh["results"].append("W"); sa["results"].append("L")
                        elif hg<ag: sa["points"]+=3; sa["away_points"]+=3; sa["results"].append("W"); sh["results"].append("L")
                        else: sh["points"]+=1; sa["points"]+=1; sh["home_points"]+=1; sa["away_points"]+=1; sh["results"].append("D"); sa["results"].append("D")

    if os.path.exists(ELO_CSV):
        with open(ELO_CSV, newline="", encoding="utf-8", errors="ignore") as f:
            reader = csv.DictReader(f)
            fields = reader.fieldnames or []
            c_team=_find_col(fields,"team"); c_elo=_find_col(fields,"elo")
            if c_team and c_elo:
                for row in reader:
                    t=row.get(c_team,"").strip()
                    if not t: continue
                    e=_safe_float(row.get(c_elo))
                    if e:
                        s=stats[t]; s["elo"]=(s["elo"]*s["elo_n"]+e)/(s["elo_n"]+1); s["elo_n"]+=1

    if os.path.exists(GAMES_CSV):
        with open(GAMES_CSV, newline="", encoding="utf-8", errors="ignore") as f:
            reader = csv.DictReader(f)
            fields = reader.fieldnames or []
            c_home=_find_col(fields,"home_team"); c_away=_find_col(fields,"away_team")
            c_hg=_find_col(fields,"home_goals"); c_ag=_find_col(fields,"away_goals")
            if c_home and c_away and c_hg and c_ag:
                for row in reader:
                    h,a=row.get(c_home,"").strip(),row.get(c_away,"").strip()
                    if not h or not a: continue
                    hg,ag=_safe_float(row.get(c_hg)),_safe_float(row.get(c_ag))
                    sh,sa=stats[h],stats[a]
                    sh["goals_for"]+=hg; sh["goals_against"]+=ag
                    sa["goals_for"]+=ag; sa["goals_against"]+=hg
                    sh["played"]+=1; sa["played"]+=1
                    if hg>ag: sh["results"].append("W"); sa["results"].append("L")
                    elif hg<ag: sa["results"].append("W"); sh["results"].append("L")
                    else: sh["results"].append("D"); sa["results"].append("D")

    teams={}
    for name,s in stats.items():
        played=max(1,s["played"])
        xg=round(s["goals_for"]/played,2)
        xga=round(s["goals_against"]/played,2)
        form="".join(s["results"][-5:]) or "DDDDD"
        teams[name]={
            "name":name,"league":s["league"],"elo":round(s["elo"],1),
            "xg":xg if xg>0 else 1.2,"xga":xga if xga>0 else 1.2,
            "form":list(form.ljust(5,"D")),"points":s["points"],
            "goals_for":int(s["goals_for"]),"goals_against":int(s["goals_against"]),
            "home_points":s["home_points"],"away_points":s["away_points"],
            "played":s["played"],"value":50,"injuries":0,"suspensions":0,
        }

    by_league=defaultdict(list)
    for t in teams.values(): by_league[t["league"]].append(t)
    for league,lst in by_league.items():
        lst.sort(key=lambda x:-x["points"])
        for i,t in enumerate(lst,1): t["rank"]=i

    _CACHE["teams"]=teams; _CACHE["loaded"]=True
    print(f"✅ {len(teams)} takım yüklendi")
    return teams

def get_team_stats(team_name, league=""):
    teams=build_team_stats_from_csv()
    if team_name in teams:
        t=dict(teams[team_name])
        t.setdefault("squad_depth",5); t.setdefault("manager_exp",5)
        t.setdefault("stadium_capacity",30000); t.setdefault("matches_last7",2)
        t.setdefault("rest_days",3); t.setdefault("uefa_match_in_3days",False)
        t.setdefault("international_players",0); t.setdefault("cup_match_in_3days",False)
        t.setdefault("new_players",0); t.setdefault("news_factor",0)
        t.setdefault("style","balanced"); t.setdefault("rank",10)
        t["last5_xg"]=[t["xg"]]*5; t["last5_xga"]=[t["xga"]]*5
        if league and not t.get("league"): t["league"]=league
        return t
    cfg=LEAGUE_CONFIG.get(league,{"avg_xg":1.2})
    return {
        "name":team_name,"league":league,"elo":1500,"xg":cfg["avg_xg"],
        "xga":cfg["avg_xg"],"form":["D","D","D","D","D"],"rank":10,
        "points":40,"value":50,"injuries":0,"suspensions":0,
        "home_points":20,"away_points":20,"goals_for":30,"goals_against":30,
        "last5_xg":[cfg["avg_xg"]]*5,"last5_xga":[cfg["avg_xg"]]*5,
        "squad_depth":5,"manager_exp":5,"stadium_capacity":30000,
        "matches_last7":2,"rest_days":3,"uefa_match_in_3days":False,
        "international_players":0,"cup_match_in_3days":False,
        "new_players":0,"news_factor":0,"style":"balanced",
    }

def get_all_team_names(search=""):
    teams=build_team_stats_from_csv()
    names=sorted(teams.keys())
    if search: names=[n for n in names if search.lower() in n.lower()]
    return names

print("✅ data_loader.py hazır! (v2 - bellek optimizasyonu)")
