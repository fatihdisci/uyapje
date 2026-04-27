"""SQLite CRUD katmanı."""
import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import date, datetime
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
    olusturma_tarihi TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS dosyalar (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dava_id TEXT REFERENCES davalar(id) ON DELETE CASCADE,
    dosya_adi TEXT,
    format TEXT,
    metin TEXT,
    meta TEXT,
    yukleme_tarihi TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sohbet_gecmisi (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dava_id TEXT REFERENCES davalar(id) ON DELETE CASCADE,
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


def dava_olustur(mahkeme: str, konu: str, taraf: str = "",
                 durum: str = "Aktif", sonraki_durusma: Optional[str] = None) -> str:
    dava_id = str(uuid.uuid4())[:8]
    with baglan() as c:
        c.execute(
            "INSERT INTO davalar (id, mahkeme, konu, taraf, durum, sonraki_durusma) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (dava_id, mahkeme, konu, taraf, durum, sonraki_durusma),
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


def dava_guncelle(dava_id: str, **alanlar):
    if not alanlar:
        return
    set_str = ", ".join(f"{k}=?" for k in alanlar)
    with baglan() as c:
        c.execute(
            f"UPDATE davalar SET {set_str} WHERE id=?",
            (*alanlar.values(), dava_id),
        )


def dava_sil(dava_id: str):
    with baglan() as c:
        c.execute("DELETE FROM dosyalar WHERE dava_id=?", (dava_id,))
        c.execute("DELETE FROM sohbet_gecmisi WHERE dava_id=?", (dava_id,))
        c.execute("DELETE FROM ictihat_cache WHERE dava_id=?", (dava_id,))
        c.execute("DELETE FROM davalar WHERE id=?", (dava_id,))


def dosya_ekle(dava_id: str, dosya_adi: str, format: str, metin: str, meta: dict) -> int:
    with baglan() as c:
        cur = c.execute(
            "INSERT INTO dosyalar (dava_id, dosya_adi, format, metin, meta) "
            "VALUES (?, ?, ?, ?, ?)",
            (dava_id, dosya_adi, format, metin, json.dumps(meta)),
        )
        return cur.lastrowid


def dosyalari_listele(dava_id: str) -> list:
    with baglan() as c:
        rows = c.execute(
            "SELECT id, dosya_adi, format, meta, yukleme_tarihi FROM dosyalar "
            "WHERE dava_id=? ORDER BY yukleme_tarihi DESC",
            (dava_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def dosyalari_metin_birlestir(dava_id: str) -> str:
    with baglan() as c:
        rows = c.execute(
            "SELECT dosya_adi, metin FROM dosyalar WHERE dava_id=? ORDER BY yukleme_tarihi",
            (dava_id,),
        ).fetchall()
    return "\n\n".join(f"=== {r['dosya_adi']} ===\n{r['metin']}" for r in rows)


def dosya_sil(dosya_id: int):
    with baglan() as c:
        c.execute("DELETE FROM dosyalar WHERE id=?", (dosya_id,))


def sohbet_kaydet(dava_id: str, rol: str, icerik: str):
    with baglan() as c:
        c.execute(
            "INSERT INTO sohbet_gecmisi (dava_id, rol, icerik) VALUES (?, ?, ?)",
            (dava_id, rol, icerik),
        )


def sohbet_getir(dava_id: str, limit: int = 50) -> list:
    with baglan() as c:
        rows = c.execute(
            "SELECT rol, icerik, tarih FROM sohbet_gecmisi "
            "WHERE dava_id=? ORDER BY tarih ASC LIMIT ?",
            (dava_id, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def yarinki_durusmalar() -> list:
    with baglan() as c:
        rows = c.execute(
            "SELECT * FROM davalar WHERE sonraki_durusma = date('now', '+1 day')"
        ).fetchall()
    return [dict(r) for r in rows]


def ictihat_cache_yaz(dava_id: Optional[str], sorgu: str, sonuc: str):
    with baglan() as c:
        c.execute(
            "INSERT INTO ictihat_cache (dava_id, sorgu, sonuc) VALUES (?, ?, ?)",
            (dava_id, sorgu, sonuc),
        )
