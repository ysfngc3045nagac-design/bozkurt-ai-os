import math
import sys
sys.path.insert(0, '/content/drive/MyDrive/Bozkurtasena')
from config import LIGLER, POISSON_MAX_GOL, DIXON_COLES_RHO, KELLY_YARIM, KELLY_MIN_EDGE

def poisson_pmf(k, lam):
    if lam <= 0: return 0.0
    return (lam ** k) * math.exp(-lam) / math.factorial(k)

def dixon_coles_tau(x, y, lam_ev, lam_dep, rho):
    if x == 0 and y == 0: return 1.0 - (lam_ev * lam_dep * rho)
    elif x == 1 and y == 0: return 1.0 + (lam_dep * rho)
    elif x == 0 and y == 1: return 1.0 + (lam_ev * rho)
    elif x == 1 and y == 1: return 1.0 - rho
    return 1.0

def skor_matrisi(lam_ev, lam_dep):
    n = POISSON_MAX_GOL + 1
    matris = []
    for i in range(n):
        satir = []
        for j in range(n):
            p = poisson_pmf(i, lam_ev) * poisson_pmf(j, lam_dep)
            p *= dixon_coles_tau(i, j, lam_ev, lam_dep, DIXON_COLES_RHO)
            satir.append(p)
        matris.append(satir)
    toplam = sum(sum(s) for s in matris)
    return [[p/toplam for p in s] for s in matris]

def mac_sonuclari(matris):
    ms1 = msx = ms2 = 0.0
    for i, satir in enumerate(matris):
        for j, p in enumerate(satir):
            if i > j: ms1 += p
            elif i == j: msx += p
            else: ms2 += p
    return {'MS1': round(ms1*100,2), 'MSX': round(msx*100,2), 'MS2': round(ms2*100,2)}

def kelly(p, oran, bankroll=1000):
    b = oran - 1.0
    q = 1.0 - p
    f = (b*p - q) / b if b > 0 else -1
    if f <= 0: return {'miktar': 0, 'yuzde': 0, 'oneri': '❌ PAS'}
    if KELLY_YARIM: f = f / 2
    return {'miktar': round(f*bankroll, 2), 'yuzde': round(f*100, 2), 'oneri': '✅ Bahis'}

def novig(o1, oX, o2):
    z1, zX, z2 = 1/o1, 1/oX, 1/o2
    t = z1 + zX + z2
    return {'MS1': round(z1/t*100,2), 'MSX': round(zX/t*100,2), 'MS2': round(z2/t*100,2), 'marj': round((t-1)/t*100,2)}

def analiz(ev, dep, lig, o1, oX, o2, ev_elo=1500, dep_elo=1500, bankroll=1000):
    lig_bilgi = LIGLER.get(lig, LIGLER['Premier League'])
    elo_fark = ev_elo - dep_elo
    lam_ev = max(0.3, min(4.0, lig_bilgi['gol_ort'] * (elo_fark + 100) / 400))
    lam_dep = max(0.3, min(4.0, lig_bilgi['gol_ort'] * (100 - elo_fark) / 400))
    
    matris = skor_matrisi(lam_ev, lam_dep)
    sonuc = mac_sonuclari(matris)
    nv = novig(o1, oX, o2)
    
    k1 = kelly(sonuc['MS1']/100, o1, bankroll)
    kX = kelly(sonuc['MSX']/100, oX, bankroll)
    k2 = kelly(sonuc['MS2']/100, o2, bankroll)
    
    value = []
    for s, pm, pn, o, k in [('MS1', sonuc['MS1'], nv['MS1'], o1, k1),
                              ('MSX', sonuc['MSX'], nv['MSX'], oX, kX),
                              ('MS2', sonuc['MS2'], nv['MS2'], o2, k2)]:
        edge = pm - pn
        if edge > 5:
            value.append({'sonuc': s, 'edge': round(edge,2), 'oran': o, 'kelly': k})
    
    return {
        'mac': f'{ev} vs {dep}',
        'beklenen_gol': {'ev': round(lam_ev,2), 'dep': round(lam_dep,2)},
        'poisson': sonuc,
        'novig': nv,
        'kelly': {'MS1': k1, 'MSX': kX, 'MS2': k2},
        'value_betler': value
    }

print("✅ analiz.py hazır!")
