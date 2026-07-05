"""
app_ekleri.py
=============
NOT: Paylaştığın app.py'nin HTML kısmı sohbette yarım kesilmiş geldiği için
tüm dosyayı riske atıp yeniden yazmadım — olası veri kaybını önlemek için
bunun yerine mevcut app.py'ne EKLENECEK parçaları ayrı bir dosyada topladım.

KURULUM (app.py içine 3 adım):

1) Dosyanın en üstündeki importlara ekle:

    from kupon_yonetimi import init_kupon_tables, mevcut_bankroll, bankroll_ekle, \\
        kupon_olustur, kupon_sonucla, performans_raporu
    from marj_analizi import tam_marj_analizi
    from config import normalize_league_name

2) init_db() fonksiyonunun sonuna (conn.commit() öncesine) ekle:

    conn.executescript('''
        ALTER TABLE matches ADD COLUMN odds_open_home REAL;
    ''') if not _column_exists(conn, 'matches', 'odds_open_home') else None
    # (yoksa basitçe: aşağıdaki _ensure_odds_open_columns(conn) fonksiyonunu çağır)

   Daha kolay ve güvenli yol: init_db() içinde, mevcut CREATE TABLE'lardan hemen
   sonra şunu çağır:

    _ensure_odds_open_columns(get_db())
    init_kupon_tables(get_db())

3) analyze_match ve analyze_custom fonksiyonlarında, get_team_stats çağrılarından
   önce lig adını normalize et:

    m["league"] = normalize_league_name(m["league"])   # analyze_match içinde
    league = normalize_league_name(data.get("league",""))  # analyze_custom içinde

   ve master_analyze çağrısına odds_open parametresini ekle (varsa):

    odds_open = None
    if m.get("odds_open_home"):
        odds_open = {"home": m["odds_open_home"], "draw": m["odds_open_draw"], "away": m["odds_open_away"]}
    result = master_analyze(home, away, odds, match_data=None, odds_open=odds_open)

Aşağıdaki fonksiyonları ve route'ları app.py'nin sonuna (if __name__ kısmından
önce) yapıştırman yeterli.
"""

import sqlite3
from flask import request, jsonify


def _column_exists(conn, table, column):
    cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
    return column in cols


def _ensure_odds_open_columns(conn):
    """Maçlar tablosuna açılış oranı kolonları ekler (yoksa)."""
    for col in ("odds_open_home", "odds_open_draw", "odds_open_away"):
        if not _column_exists(conn, "matches", col):
            conn.execute(f"ALTER TABLE matches ADD COLUMN {col} REAL")
    conn.commit()


# ============================================================
# Aşağıdaki route'ları app.py'ye (app = Flask(...) tanımlı olduğu dosyaya) ekle.
# `app`, `get_db` fonksiyonu zaten mevcut app.py'nde tanımlı olmalı.
# ============================================================

def register_extra_routes(app, get_db):

    @app.route("/api/bankroll", methods=["GET"])
    def bankroll_gor():
        conn = get_db()
        bakiye = mevcut_bankroll(conn)
        conn.close()
        return jsonify({"status": "ok", "bankroll": bakiye})

    @app.route("/api/bankroll", methods=["POST"])
    def bankroll_ekle_route():
        data = request.json or {}
        miktar = float(data.get("miktar", 0))
        aciklama = data.get("aciklama", "")
        conn = get_db()
        yeni = bankroll_ekle(conn, miktar, aciklama)
        conn.close()
        return jsonify({"status": "ok", "yeni_bankroll": yeni})

    @app.route("/api/kupon", methods=["POST"])
    def kupon_olustur_route():
        data = request.json or {}
        conn = get_db()
        sonuc = kupon_olustur(
            conn,
            match_id=data.get("match_id"),
            ev_sahibi=data.get("ev_sahibi", ""),
            deplasman=data.get("deplasman", ""),
            lig=data.get("lig", ""),
            secim=data.get("secim", ""),
            oran=float(data.get("oran", 1.0)),
            stake=float(data.get("stake", 0)),
        )
        conn.close()
        return jsonify({"status": "ok", **sonuc})

    @app.route("/api/kupon/<kupon_id>/sonuc", methods=["POST"])
    def kupon_sonuc_route(kupon_id):
        data = request.json or {}
        conn = get_db()
        sonuc = kupon_sonucla(conn, kupon_id, data.get("sonuc", "kaybetti"))
        conn.close()
        return jsonify({"status": "ok", **sonuc})

    @app.route("/api/kuponlar", methods=["GET"])
    def kuponlar_listele():
        conn = get_db()
        rows = conn.execute("SELECT * FROM kuponlar ORDER BY tarih DESC LIMIT 50").fetchall()
        conn.close()
        return jsonify({"status": "ok", "kuponlar": [dict(r) for r in rows]})

    @app.route("/api/performans", methods=["GET"])
    def performans_route():
        gun = int(request.args.get("gun", 30))
        conn = get_db()
        rapor = performans_raporu(conn, gun)
        conn.close()
        return jsonify({"status": "ok", "rapor": rapor})

    @app.route("/api/marj/<match_id>", methods=["GET"])
    def marj_route(match_id):
        conn = get_db()
        m = conn.execute("SELECT * FROM matches WHERE id=?", (match_id,)).fetchone()
        conn.close()
        if not m:
            return jsonify({"status": "error", "message": "Maç bulunamadı"})
        m = dict(m)
        analiz = tam_marj_analizi(m.get("odds_home", 2.0), m.get("odds_draw", 3.3), m.get("odds_away", 3.5))
        return jsonify({"status": "ok", "match": m, "marj": analiz})

    return app
