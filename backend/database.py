"""SQLite CRUD katmanı."""
import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime
from typing import Optional

DB_YOL = os.getenv("DB_YOL", "./uyap.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS davalar (
    id TEXT PRIMARY KEY,
    mahkeme TEXT,
    konu TEXT,
    taraf TEXT,
    durum TEXT,
    sonraki_durusma DATE,
    dizi_yolu TEXT,
    olusturma_tarihi TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS dosyalar (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dava_id TEXT REFERENCES davalar(id) ON DELETE CASCADE,
    dosya_adi TEXT,
    format TEXT,
    metin TEXT,
    meta TEXT,
    baglamda INTEGER DEFAULT 0,
    dosya_yolu TEXT,
    yukleme_tarihi TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sessionlar (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dava_id TEXT REFERENCES davalar(id) ON DELETE CASCADE,
    klasor TEXT,
    baslik TEXT,
    ozet TEXT,
    olusturma_tarihi TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sohbet_gecmisi (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dava_id TEXT REFERENCES davalar(id) ON DELETE CASCADE,
    session_id INTEGER REFERENCES sessionlar(id) ON DELETE CASCADE,
    rol TEXT,
    icerik TEXT,
    tarih TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ictihat_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dava_id TEXT,
    sorgu TEXT,
    sonuc TEXT,
    tarih TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


@contextmanager
def baglan():
    conn = sqlite3.connect(DB_YOL)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with baglan() as c:
        c.executescript(SCHEMA)


def migrate():
    """Mevcut DB'ye yeni kolonları ve tabloları ekler — idempotent."""
    with baglan() as c:
        for stmt in [
            "ALTER TABLE dosyalar ADD COLUMN baglamda INTEGER DEFAULT 0",
            "ALTER TABLE dosyalar ADD COLUMN dosya_yolu TEXT",
            "ALTER TABLE davalar ADD COLUMN dizi_yolu TEXT",
            "ALTER TABLE sohbet_gecmisi ADD COLUMN session_id INTEGER",
        ]:
            try:
                c.execute(stmt)
            except sqlite3.OperationalError:
                pass
        c.execute("""
            CREATE TABLE IF NOT EXISTS sessionlar (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                dava_id TEXT REFERENCES davalar(id) ON DELETE CASCADE,
                klasor TEXT,
                baslik TEXT,
                ozet TEXT,
                olusturma_tarihi TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)


# ── Davalar ──────────────────────────────────────────────────────────────────

def dava_olustur(mahkeme: str, konu: str, taraf: str = "",
                 durum: str = "Aktif", sonraki_durusma: Optional[str] = None,
                 dizi_yolu: Optional[str] = None) -> str:
    dava_id = str(uuid.uuid4())[:8]
    with baglan() as c:
        c.execute(
            "INSERT INTO davalar (id, mahkeme, konu, taraf, durum, sonraki_durusma, dizi_yolu) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (dava_id, mahkeme, konu, taraf, durum, sonraki_durusma, dizi_yolu),
        )
    return dava_id


def davalari_listele() -> list:
    with baglan() as c:
        rows = c.execute("SELECT * FROM davalar ORDER BY olusturma_tarihi DESC").fetchall()
    return [dict(r) for r in rows]


def dava_getir(dava_id: str) -> Optional[dict]:
    with baglan() as c:
        r = c.execute("SELECT * FROM davalar WHERE id=?", (dava_id,)).fetchone()
    return dict(r) if r else None


_GUVENLI_ALANLAR = {"mahkeme", "konu", "taraf", "durum", "sonraki_durusma", "dizi_yolu"}


def dava_guncelle(dava_id: str, **alanlar):
    if not alanlar:
        return
    gecersiz = set(alanlar) - _GUVENLI_ALANLAR
    if gecersiz:
        raise ValueError(f"Geçersiz alan adları: {gecersiz}")
    set_str = ", ".join(f"{k}=?" for k in alanlar)
    with baglan() as c:
        c.execute(
            f"UPDATE davalar SET {set_str} WHERE id=?",
            (*alanlar.values(), dava_id),
        )


def dava_sil(dava_id: str):
    with baglan() as c:
        c.execute("DELETE FROM ictihat_cache WHERE dava_id=?", (dava_id,))
        c.execute("DELETE FROM davalar WHERE id=?", (dava_id,))
        # dosyalar, sessionlar, sohbet_gecmisi CASCADE ile silinir


def yarinki_durusmalar() -> list:
    with baglan() as c:
        rows = c.execute(
            "SELECT * FROM davalar WHERE sonraki_durusma = date('now', '+1 day')"
        ).fetchall()
    return [dict(r) for r in rows]


# ── Dosyalar ─────────────────────────────────────────────────────────────────

def dosya_ekle(dava_id: str, dosya_adi: str, format: str, metin: str,
               meta: dict, dosya_yolu: Optional[str] = None) -> int:
    with baglan() as c:
        cur = c.execute(
            "INSERT INTO dosyalar (dava_id, dosya_adi, format, metin, meta, dosya_yolu) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (dava_id, dosya_adi, format, metin, json.dumps(meta), dosya_yolu),
        )
        return cur.lastrowid


def dosyalari_listele(dava_id: str) -> list:
    with baglan() as c:
        rows = c.execute(
            "SELECT id, dosya_adi, format, meta, yukleme_tarihi, baglamda FROM dosyalar "
            "WHERE dava_id=? ORDER BY yukleme_tarihi DESC",
            (dava_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def dosyalari_metin_birlestir(dava_id: str) -> str:
    """Sadece baglamda=1 olan dosyaların metinlerini birleştirir."""
    with baglan() as c:
        rows = c.execute(
            "SELECT dosya_adi, metin FROM dosyalar "
            "WHERE dava_id=? AND baglamda=1 ORDER BY yukleme_tarihi",
            (dava_id,),
        ).fetchall()
    return "\n\n".join(f"=== {r['dosya_adi']} ===\n{r['metin']}" for r in rows)


def baglamda_idleri(dava_id: str) -> list:
    with baglan() as c:
        rows = c.execute(
            "SELECT id FROM dosyalar WHERE dava_id=? AND baglamda=1 ORDER BY id",
            (dava_id,),
        ).fetchall()
    return [r["id"] for r in rows]


def dosya_baglamda_guncelle(dosya_id: int, baglamda: int):
    with baglan() as c:
        c.execute("UPDATE dosyalar SET baglamda=? WHERE id=?", (baglamda, dosya_id))


def dosyanin_dava_id(dosya_id: int) -> Optional[str]:
    with baglan() as c:
        r = c.execute("SELECT dava_id FROM dosyalar WHERE id=?", (dosya_id,)).fetchone()
    return r["dava_id"] if r else None


def dosya_sil(dosya_id: int):
    with baglan() as c:
        c.execute("DELETE FROM dosyalar WHERE id=?", (dosya_id,))


# ── Sessionlar ───────────────────────────────────────────────────────────────

def session_olustur(dava_id: str, klasor: str, baslik: str) -> int:
    with baglan() as c:
        cur = c.execute(
            "INSERT INTO sessionlar (dava_id, klasor, baslik) VALUES (?, ?, ?)",
            (dava_id, klasor, baslik),
        )
        return cur.lastrowid


def sessionlari_listele(dava_id: str) -> list:
    with baglan() as c:
        rows = c.execute(
            "SELECT id, dava_id, klasor, baslik, ozet, olusturma_tarihi "
            "FROM sessionlar WHERE dava_id=? ORDER BY olusturma_tarihi ASC",
            (dava_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def session_getir(session_id: int) -> Optional[dict]:
    with baglan() as c:
        r = c.execute(
            "SELECT id, dava_id, klasor, baslik, ozet, olusturma_tarihi "
            "FROM sessionlar WHERE id=?",
            (session_id,),
        ).fetchone()
    return dict(r) if r else None


def session_ozet_guncelle(session_id: int, ozet: str):
    with baglan() as c:
        c.execute("UPDATE sessionlar SET ozet=? WHERE id=?", (ozet, session_id))


# ── Sohbet ───────────────────────────────────────────────────────────────────

def sohbet_kaydet(dava_id: str, session_id: int, rol: str, icerik: str):
    with baglan() as c:
        c.execute(
            "INSERT INTO sohbet_gecmisi (dava_id, session_id, rol, icerik) VALUES (?, ?, ?, ?)",
            (dava_id, session_id, rol, icerik),
        )


def sohbet_getir(dava_id: str, session_id: Optional[int] = None) -> list:
    with baglan() as c:
        if session_id is not None:
            rows = c.execute(
                "SELECT rol, icerik, tarih FROM sohbet_gecmisi "
                "WHERE dava_id=? AND session_id=? ORDER BY tarih ASC",
                (dava_id, session_id),
            ).fetchall()
        else:
            rows = c.execute(
                "SELECT rol, icerik, tarih FROM sohbet_gecmisi "
                "WHERE dava_id=? ORDER BY tarih ASC",
                (dava_id,),
            ).fetchall()
    return [dict(r) for r in rows]


# ── İçtihat cache ─────────────────────────────────────────────────────────────

def ictihat_cache_yaz(dava_id: Optional[str], sorgu: str, sonuc: str):
    with baglan() as c:
        c.execute(
            "INSERT INTO ictihat_cache (dava_id, sorgu, sonuc) VALUES (?, ?, ?)",
            (dava_id, sorgu, sonuc),
        )
