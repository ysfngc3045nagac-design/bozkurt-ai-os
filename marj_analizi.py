"""
marj_analizi.py
================
Bahis oranlarının matematiksel analizini yapar: vig (bahis sitesi marjı),
no-vig (fair) olasılıklar ve bahis sitesi kalite skoru.

NOT: Orijinal tasarımda Shin's Method scipy.optimize ile yazılmıştı, ama bu
projenin requirements.txt dosyasında scipy/numpy yok. Bu yüzden aynı matematiği
saf Python ile (bisection / ikili arama) çözüyoruz — ekstra bağımlılık gerekmez.
"""
import math


def implied_probability(odds: float) -> float:
    return 1.0 / odds if odds and odds > 1 else 0.0


def vig_hesapla(oh: float, od: float, oa: float) -> dict:
    """Toplam vig (overround) ve implied olasılıkları hesaplar."""
    ph, pd, pa = implied_probability(oh), implied_probability(od), implied_probability(oa)
    toplam = ph + pd + pa
    vig = toplam - 1.0
    return {
        "p_home": round(ph, 4), "p_draw": round(pd, 4), "p_away": round(pa, 4),
        "toplam_implied": round(toplam, 4),
        "vig_orani": round(vig, 4),
        "vig_yuzde": round(vig * 100, 2),
        "vig_kalitesi": _vig_kalitesi(vig),
    }


def _vig_kalitesi(vig: float) -> str:
    if vig < 0.02:
        return "ÇOK DÜŞÜK (Profesyonel/Sharp site)"
    if vig < 0.05:
        return "DÜŞÜK (İyi site)"
    if vig < 0.08:
        return "ORTA (Standart)"
    if vig < 0.12:
        return "YÜKSEK (Dikkatli olun)"
    return "ÇOK YÜKSEK (Kaçının)"


def shin_no_vig(oh: float, od: float, oa: float, iterations: int = 60) -> dict:
    """
    Shin's Method: additive/multiplicative yöntemlerden daha isabetli no-vig
    olasılık tahmini üretir. "Insider trading" parametresi z'yi ikili arama
    (bisection) ile bulur, scipy gerektirmez.

    Referans formül (3 sonuçlu pazar için):
        p_i = (sqrt(z^2 + 4(1-z) * pi_i^2 / S) - z) / (2(1-z))
    burada pi_i = implied probability, S = sum(pi_i).
    z=0 durumunda additive yönteme eşdeğerdir.
    """
    pi1, pi2, pi3 = implied_probability(oh), implied_probability(od), implied_probability(oa)
    S = pi1 + pi2 + pi3

    def fair_probs(z):
        # NOT: z=0 durumu için özel bir kısayol YAZMA — genel formül z=0'da
        # zaten doğru sonucu (pi_i/sqrt(S)) verir. Önceki sürümde buraya
        # yanlışlıkla pi_i/S (basit normalize) konulmuştu; bu da bisection'ın
        # her zaman z=0'da "kök buldum" sanıp basit additive yönteme
        # dönmesine, yani Shin's Method'un aslında hiç çalışmamasına yol açıyordu.
        denom = 2 * (1 - z)
        if denom <= 1e-9:
            return pi1 / S, pi2 / S, pi3 / S
        try:
            p1 = (math.sqrt(max(z * z + 4 * (1 - z) * (pi1 ** 2) / S, 0)) - z) / denom
            p2 = (math.sqrt(max(z * z + 4 * (1 - z) * (pi2 ** 2) / S, 0)) - z) / denom
            p3 = (math.sqrt(max(z * z + 4 * (1 - z) * (pi3 ** 2) / S, 0)) - z) / denom
        except (ValueError, ZeroDivisionError):
            return pi1 / S, pi2 / S, pi3 / S
        return p1, p2, p3

    def total_minus_1(z):
        p1, p2, p3 = fair_probs(z)
        return (p1 + p2 + p3) - 1.0

    # z, [0, 1) aralığında; toplam olasılık 1'e insin diye ikili arama
    lo, hi = 0.0, 0.999
    f_lo = total_minus_1(lo)
    if f_lo <= 0:
        z = 0.0
    else:
        for _ in range(iterations):
            mid = (lo + hi) / 2
            f_mid = total_minus_1(mid)
            if abs(f_mid) < 1e-9:
                break
            if f_mid > 0:
                lo = mid
            else:
                hi = mid
        z = (lo + hi) / 2

    p1, p2, p3 = fair_probs(z)
    toplam = p1 + p2 + p3
    p1, p2, p3 = p1 / toplam, p2 / toplam, p3 / toplam

    return {
        "yontem": "Shin's Power Method",
        "z_parametresi": round(z, 4),
        "home": round(p1 * 100, 2),
        "draw": round(p2 * 100, 2),
        "away": round(p3 * 100, 2),
        "fair_odds": {
            "home": round(1 / p1, 2) if p1 > 0 else None,
            "draw": round(1 / p2, 2) if p2 > 0 else None,
            "away": round(1 / p3, 2) if p3 > 0 else None,
        },
    }


def edge_hesapla(model_prob_pct: float, fair_prob_pct: float) -> float:
    """Model olasılığının fair (no-vig) olasılığa göre kaç puan üstünde olduğu."""
    return round(model_prob_pct - fair_prob_pct, 2)


def tam_marj_analizi(oh: float, od: float, oa: float, model_probs: dict = None) -> dict:
    """
    Bir maç için tam marj raporu: vig + Shin fair oranlar + (varsa) model
    olasılıklarına göre edge.
    model_probs: {"home": %, "draw": %, "away": %} - modelin ürettiği olasılıklar
    """
    vig = vig_hesapla(oh, od, oa)
    shin = shin_no_vig(oh, od, oa)

    sonuc = {
        "giris_oranlari": {"home": oh, "draw": od, "away": oa},
        "vig_analizi": vig,
        "shin_fair": shin,
    }

    if model_probs:
        sonuc["edge"] = {
            "home": edge_hesapla(model_probs.get("home", 0), shin["home"]),
            "draw": edge_hesapla(model_probs.get("draw", 0), shin["draw"]),
            "away": edge_hesapla(model_probs.get("away", 0), shin["away"]),
        }

    return sonuc


def oran_degisim_analizi(acilis: dict, guncel: dict) -> dict:
    """
    Açılış oranları ile güncel oranları karşılaştırıp "para nereye akıyor"
    yorumu üretir. acilis/guncel: {"home":..,"draw":..,"away":..}
    Oran düşmesi = o sonuca daha çok para/güven yatması demektir.
    """
    def pct_change(old, new):
        if not old or old <= 1:
            return 0.0
        return round((new - old) / old * 100, 2)

    h_chg = pct_change(acilis.get("home"), guncel.get("home"))
    d_chg = pct_change(acilis.get("draw"), guncel.get("draw"))
    a_chg = pct_change(acilis.get("away"), guncel.get("away"))

    yorum = "Oranlar stabil, belirgin bir para akışı yok"
    if h_chg <= -8:
        yorum = "Ev sahibine doğru güçlü para akışı var (oran düştü)"
    elif a_chg <= -8:
        yorum = "Deplasmana doğru güçlü para akışı var (oran düştü)"
    elif d_chg <= -8:
        yorum = "Beraberliğe doğru para akışı var (oran düştü)"
    elif h_chg >= 8:
        yorum = "Ev sahibi değer kaybediyor (oran yükseldi)"
    elif a_chg >= 8:
        yorum = "Deplasman değer kaybediyor (oran yükseldi)"

    return {
        "acilis": acilis, "guncel": guncel,
        "degisim_yuzde": {"home": h_chg, "draw": d_chg, "away": a_chg},
        "yorum": yorum,
    }


print("✅ marj_analizi.py hazır! (Shin's Method, saf Python)")
