"""
kupon_yonetimi.py
==================
Bankroll takibi + kupon (bahis) sonuç geçmişi. Value bet önerilerinin
gerçekte tutup tutmadığını ölçmek için gereken katman: eskiden sistem sadece
"öneri" üretiyordu, sonucun ne olduğunu hiçbir yerde saklamıyordu.
"""
import sqlite3
from datetime import datetime, timedelta


def init_kupon_tables(conn: sqlite3.Connection):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS bankroll_gecmisi (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tarih TEXT, islem_turu TEXT, miktar REAL,
            bankroll_oncesi REAL, bankroll_sonrasi REAL, aciklama TEXT
        );
        CREATE TABLE IF NOT EXISTS kuponlar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kupon_id TEXT UNIQUE,
            tarih TEXT,
            match_id TEXT,
            ev_sahibi TEXT, deplasman TEXT, lig TEXT,
            secim TEXT, oran REAL, stake REAL,
            potansiyel_kazanc REAL,
            sonuc TEXT DEFAULT 'bekliyor',
            kar_zarar REAL DEFAULT 0,
            bankroll_oncesi REAL, bankroll_sonrasi REAL
        );
    """)
    conn.commit()


def mevcut_bankroll(conn: sqlite3.Connection) -> float:
    row = conn.execute(
        "SELECT bankroll_sonrasi FROM bankroll_gecmisi ORDER BY id DESC LIMIT 1"
    ).fetchone()
    return row[0] if row else 0.0


def bankroll_ekle(conn: sqlite3.Connection, miktar: float, aciklama: str = "") -> float:
    onceki = mevcut_bankroll(conn)
    sonraki = onceki + miktar
    conn.execute(
        """INSERT INTO bankroll_gecmisi (tarih, islem_turu, miktar, bankroll_oncesi, bankroll_sonrasi, aciklama)
           VALUES (?,?,?,?,?,?)""",
        (datetime.now().isoformat(), "yatirim" if miktar > 0 else "cekim",
         abs(miktar), onceki, sonraki, aciklama),
    )
    conn.commit()
    return sonraki


def kupon_olustur(conn: sqlite3.Connection, match_id, ev_sahibi, deplasman, lig,
                   secim, oran, stake) -> dict:
    bankroll = mevcut_bankroll(conn)
    if stake > bankroll and bankroll > 0:
        stake = bankroll  # bankroll'dan fazla bahis yapılamaz
    kupon_id = f"KUP-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
    yeni_bankroll = bankroll - stake

    conn.execute(
        """INSERT INTO kuponlar (kupon_id, tarih, match_id, ev_sahibi, deplasman, lig,
           secim, oran, stake, potansiyel_kazanc, sonuc, bankroll_oncesi, bankroll_sonrasi)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (kupon_id, datetime.now().isoformat(), match_id, ev_sahibi, deplasman, lig,
         secim, oran, stake, round(stake * oran, 2), "bekliyor", bankroll, yeni_bankroll),
    )
    conn.execute(
        """INSERT INTO bankroll_gecmisi (tarih, islem_turu, miktar, bankroll_oncesi, bankroll_sonrasi, aciklama)
           VALUES (?,?,?,?,?,?)""",
        (datetime.now().isoformat(), "bahis", stake, bankroll, yeni_bankroll, f"Kupon: {kupon_id}"),
    )
    conn.commit()
    return {
        "kupon_id": kupon_id, "stake": stake, "oran": oran,
        "potansiyel_kazanc": round(stake * oran, 2),
        "bankroll_kalan": round(yeni_bankroll, 2),
    }


def kupon_sonucla(conn: sqlite3.Connection, kupon_id: str, sonuc: str) -> dict:
    """sonuc: 'kazandi' | 'kaybetti' | 'iade'"""
    row = conn.execute("SELECT stake, oran FROM kuponlar WHERE kupon_id=?", (kupon_id,)).fetchone()
    if not row:
        return {"hata": "Kupon bulunamadı"}
    stake, oran = row

    if sonuc == "kazandi":
        kar_zarar = round(stake * oran - stake, 2)
    elif sonuc == "iade":
        kar_zarar = 0.0
    else:
        kar_zarar = -stake

    onceki = mevcut_bankroll(conn)
    sonraki = onceki + (kar_zarar if sonuc != "iade" else stake)

    conn.execute("UPDATE kuponlar SET sonuc=?, kar_zarar=? WHERE kupon_id=?",
                 (sonuc, kar_zarar, kupon_id))
    conn.execute(
        """INSERT INTO bankroll_gecmisi (tarih, islem_turu, miktar, bankroll_oncesi, bankroll_sonrasi, aciklama)
           VALUES (?,?,?,?,?,?)""",
        (datetime.now().isoformat(), "sonuc", abs(kar_zarar) if sonuc != 'iade' else stake,
         onceki, sonraki, f"Kupon sonuç: {kupon_id} ({sonuc})"),
    )
    conn.commit()
    return {"kupon_id": kupon_id, "sonuc": sonuc, "kar_zarar": kar_zarar, "yeni_bankroll": round(sonraki, 2)}


def performans_raporu(conn: sqlite3.Connection, gun: int = 30) -> dict:
    baslangic = (datetime.now() - timedelta(days=gun)).isoformat()
    rows = conn.execute(
        "SELECT sonuc, kar_zarar, stake, oran FROM kuponlar WHERE tarih >= ? AND sonuc != 'bekliyor'",
        (baslangic,),
    ).fetchall()

    if not rows:
        return {"donem_gun": gun, "toplam_kupon": 0, "mesaj": "Bu dönemde sonuçlanmış kupon yok"}

    kazanan = sum(1 for r in rows if r[0] == "kazandi")
    kaybeden = sum(1 for r in rows if r[0] == "kaybetti")
    toplam_stake = sum(r[2] for r in rows)
    toplam_kz = sum(r[1] for r in rows)

    return {
        "donem_gun": gun,
        "toplam_kupon": len(rows),
        "kazanan": kazanan,
        "kaybeden": kaybeden,
        "kazanma_orani": round(kazanan / len(rows) * 100, 1),
        "toplam_stake": round(toplam_stake, 2),
        "toplam_kar_zarar": round(toplam_kz, 2),
        "roi_yuzde": round(toplam_kz / toplam_stake * 100, 2) if toplam_stake else 0,
        "mevcut_bankroll": round(mevcut_bankroll(conn), 2),
    }


print("✅ kupon_yonetimi.py hazır!")
