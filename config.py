import os

BASE_DIR = '/content/drive/MyDrive/Bozkurtasena'

for d in ['veriler', 'raporlar', 'loglar']:
    os.makedirs(os.path.join(BASE_DIR, d), exist_ok=True)

LIGLER = {
    'Premier League': {'gol_ort': 2.65, 'ev_avantaj': 53},
    'La Liga':        {'gol_ort': 2.45, 'ev_avantaj': 55},
    'Bundesliga':     {'gol_ort': 2.85, 'ev_avantaj': 50},
    'Serie A':        {'gol_ort': 2.35, 'ev_avantaj': 52},
    'Ligue 1':        {'gol_ort': 2.40, 'ev_avantaj': 51},
    'Süper Lig':      {'gol_ort': 2.55, 'ev_avantaj': 48},
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

print("✅ config.py hazır!")
