import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
for d in ["raporlar", "loglar"]:
    os.makedirs(os.path.join(BASE_DIR, d), exist_ok=True)

LEAGUE_CONFIG = {
    "Premier League": {"country": "İngiltere", "level": 5, "avg_xg": 1.4},
    "Championship": {"country": "İngiltere", "level": 3, "avg_xg": 1.3},
    "La Liga": {"country": "İspanya", "level": 5, "avg_xg": 1.35},
    "Segunda División": {"country": "İspanya", "level": 2, "avg_xg": 1.2},
    "Bundesliga": {"country": "Almanya", "level": 5, "avg_xg": 1.5},
    "2. Bundesliga": {"country": "Almanya", "level": 2, "avg_xg": 1.3},
    "Serie A": {"country": "İtalya", "level": 5, "avg_xg": 1.3},
    "Serie B": {"country": "İtalya", "level": 2, "avg_xg": 1.15},
    "Ligue 1": {"country": "Fransa", "level": 4, "avg_xg": 1.25},
    "Ligue 2": {"country": "Fransa", "level": 2, "avg_xg": 1.15},
    "Süper Lig": {"country": "Türkiye", "level": 3, "avg_xg": 1.3},
    "TFF 1. Lig": {"country": "Türkiye", "level": 2, "avg_xg": 1.2},
    "Eredivisie": {"country": "Hollanda", "level": 3, "avg_xg": 1.6},
    "Primeira Liga": {"country": "Portekiz", "level": 3, "avg_xg": 1.35},
    "Scottish Premiership": {"country": "İskoçya", "level": 2, "avg_xg": 1.3},
    "Brasileirao": {"country": "Brezilya", "level": 4, "avg_xg": 1.35},
    "Primera División Argentina": {"country": "Arjantin", "level": 4, "avg_xg": 1.2},
    "J1 League": {"country": "Japonya", "level": 3, "avg_xg": 1.25},
    "K League 1": {"country": "Güney Kore", "level": 3, "avg_xg": 1.2},
    "Chinese Super League": {"country": "Çin", "level": 3, "avg_xg": 1.3},
    "Saudi Pro League": {"country": "Suudi Arabistan", "level": 3, "avg_xg": 1.4},
    "MLS": {"country": "ABD", "level": 3, "avg_xg": 1.4},
    "Liga MX": {"country": "Meksika", "level": 3, "avg_xg": 1.3},
    "A-League": {"country": "Avustralya", "level": 2, "avg_xg": 1.35},
    "Nigerian Premier League": {"country": "Nijerya", "level": 2, "avg_xg": 1.1},
    "Ghana Premier League": {"country": "Gana", "level": 2, "avg_xg": 1.15},
    "PSL": {"country": "Güney Afrika", "level": 2, "avg_xg": 1.2},
}

LIGLER = {
    'Süper Lig': {'gol_ort': 2.55, 'ev_avantaj': 48},
    'TFF 1. Lig': {'gol_ort': 2.45, 'ev_avantaj': 46},
    'Premier League': {'gol_ort': 2.65, 'ev_avantaj': 53},
    'Championship': {'gol_ort': 2.55, 'ev_avantaj': 50},
    'La Liga': {'gol_ort': 2.45, 'ev_avantaj': 55},
    'Bundesliga': {'gol_ort': 2.85, 'ev_avantaj': 50},
    'Serie A': {'gol_ort': 2.35, 'ev_avantaj': 52},
    'Ligue 1': {'gol_ort': 2.40, 'ev_avantaj': 51},
    'Eredivisie': {'gol_ort': 3.10, 'ev_avantaj': 55},
    'Primeira Liga': {'gol_ort': 2.50, 'ev_avantaj': 54},
    'Scottish Premiership': {'gol_ort': 2.60, 'ev_avantaj': 52},
    'Brasileirao': {'gol_ort': 2.40, 'ev_avantaj': 55},
    'MLS': {'gol_ort': 2.60, 'ev_avantaj': 52},
    'Saudi Pro League': {'gol_ort': 2.60, 'ev_avantaj': 52},
    'J1 League': {'gol_ort': 2.45, 'ev_avantaj': 50},
    'K League 1': {'gol_ort': 2.35, 'ev_avantaj': 49},
    'A-League': {'gol_ort': 2.55, 'ev_avantaj': 51},
    'Liga MX': {'gol_ort': 2.50, 'ev_avantaj': 53},
    'UEFA Champions League': {'gol_ort': 2.70, 'ev_avantaj': 45},
    'UEFA Europa League': {'gol_ort': 2.55, 'ev_avantaj': 44},
}

ELO_K = 32
ELO_EV_SAHASI = 53
POISSON_MAX_GOL = 6
DIXON_COLES_RHO = -0.13
KELLY_YARIM = True
KELLY_MIN_EDGE = 0.05
STAKE_MAX_YUZDE = 5
STOP_LOSS_YUZDE = 20
XG_PENALTI = 0.76
XG_BOS_KALE = 0.92
VALUE_EDGE_THRESHOLD = 7.0
TWIN_CETVEL_AGREEMENT_REQUIRED = True

MATCHES_CSV = os.path.join(DATA_DIR, "Matches.csv")
ELO_CSV = os.path.join(DATA_DIR, "EloRatings.csv")
GAMES_CSV = os.path.join(DATA_DIR, "games.csv")

print("✅ config.py hazır!")