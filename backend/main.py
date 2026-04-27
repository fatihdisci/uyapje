"""FastAPI ana uygulama."""
import json
import os
import pathlib
import shutil
import subprocess
import tempfile
import traceback
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import database as db
import gemini_cli as gc
from parser import dosya_parse

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    db.migrate()
    yield


# dava_id → {"ids": frozenset[int], "metin": str}
_metin_cache: dict = {}


def _cache_temizle(dava_id: str):
    _metin_cache.pop(dava_id, None)


app = FastAPI(title="UYAP Hukuk Asistanı", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ========== Modeller ==========

class BaglamdaIstek(BaseModel):
    baglamda: int  # 0 veya 1


class DavaIstek(BaseModel):
    mahkeme: str
    konu: str
    taraf: str = ""
    durum: str = "Aktif"
    sonraki_durusma: str | None = None


class DavaGuncelleIstek(BaseModel):
    mahkeme: str | None = None
    konu: str | None = None
    taraf: str | None = None
    durum: str | None = None
    sonraki_durusma: str | None = None


class SohbetIstek(BaseModel):
    soru: str


class DurusmaIstek(BaseModel):
    tarih: str


class IctihatIstek(BaseModel):
    sorgu: str | None = None


# ========== Sistem ==========

@app.get("/api/sistem/durum")
async def sistem_durum():
    gemini_yol = shutil.which("gemini")
    gemini_var = gemini_yol is not None
    gemini_hazir = False
    if gemini_var:
        try:
            result = subprocess.run(
                [gemini_yol, "-p", "1+1=?", "--skip-trust", "--yolo"],
                capture_output=True, text=True, timeout=30,
                env={**os.environ, "GEMINI_CLI_TRUST_WORKSPACE": "true"},
            )
            gemini_hazir = result.returncode == 0
        except Exception as e:
            print(f"Gemini test hatası: {e}")
    settings_yol = pathlib.Path.home() / ".gemini" / "settings.json"
    yargi_mcp = False
    if settings_yol.exists():
        try:
            s = json.loads(settings_yol.read_text(encoding="utf-8"))
            yargi_mcp = "yargi-mcp" in s.get("mcpServers", {}) or "yargi_mcp" in s.get("mcpServers", {})
        except Exception:
            pass
    return {
        "gemini_kurulu": gemini_var,
        "gemini_hazir": gemini_hazir,
        "yargi_mcp_aktif": yargi_mcp,
    }


# ========== Davalar ==========

@app.post("/api/dava")
def dava_olustur(istek: DavaIstek):
    dava_id = db.dava_olustur(
        mahkeme=istek.mahkeme, konu=istek.konu, taraf=istek.taraf,
        durum=istek.durum, sonraki_durusma=istek.sonraki_durusma,
    )
    return {"id": dava_id}


@app.get("/api/davalar")
def davalari_listele():
    return db.davalari_listele()


@app.get("/api/dava/{dava_id}")
def dava_getir(dava_id: str):
    d = db.dava_getir(dava_id)
    if not d:
        raise HTTPException(404, "Dava bulunamadı")
    return d


@app.patch("/api/dava/{dava_id}")
def dava_guncelle(dava_id: str, istek: DavaGuncelleIstek):
    alanlar = {k: v for k, v in istek.model_dump().items() if v is not None}
    db.dava_guncelle(dava_id, **alanlar)
    return {"ok": True}


@app.delete("/api/dava/{dava_id}")
def dava_sil(dava_id: str):
    db.dava_sil(dava_id)
    _cache_temizle(dava_id)
    return {"ok": True}


@app.get("/api/yarinki-durusmalar")
def yarinki():
    return db.yarinki_durusmalar()


# ========== Dosyalar ==========

@app.post("/api/dava/{dava_id}/dosya")
async def dosya_yukle(dava_id: str, file: UploadFile = File(...)):
    if not db.dava_getir(dava_id):
        raise HTTPException(404, "Dava bulunamadı")
    ext = (file.filename or "").lower().split(".")[-1]
    icerik = await file.read()
    with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False) as tmp:
        tmp.write(icerik)
        tmp_yol = tmp.name
    try:
        sonuc = dosya_parse(tmp_yol)
    except Exception as e:
        raise HTTPException(400, f"Dosya işlenemedi: {e}")
    finally:
        try:
            os.unlink(tmp_yol)
        except Exception:
            pass
    yeni_id = db.dosya_ekle(
        dava_id, file.filename or "dosya", ext,
        sonuc["metin"], sonuc.get("meta", {}),
    )
    _cache_temizle(dava_id)
    return {"id": yeni_id, "uzunluk": len(sonuc["metin"])}


@app.get("/api/dava/{dava_id}/dosyalar")
def dosyalari_listele(dava_id: str):
    return db.dosyalari_listele(dava_id)


@app.delete("/api/dosya/{dosya_id}")
def dosya_sil(dosya_id: int):
    dava_id = db.dosyanin_dava_id(dosya_id)
    db.dosya_sil(dosya_id)
    if dava_id:
        _cache_temizle(dava_id)
    return {"ok": True}


@app.patch("/api/dosya/{dosya_id}/baglamda")
def dosya_baglamda(dosya_id: int, istek: BaglamdaIstek):
    dava_id = db.dosyanin_dava_id(dosya_id)
    db.dosya_baglamda_guncelle(dosya_id, istek.baglamda)
    if dava_id:
        _cache_temizle(dava_id)
    return {"ok": True}


# ========== AI Endpointleri ==========

def _dava_metni(dava_id: str) -> str:
    secili_ids = db.baglamda_idleri(dava_id)
    if not secili_ids:
        raise HTTPException(
            400,
            "Bağlama eklenmiş dosya yok. Dosya listesindeki "
            "geçiş düğmesinden en az bir dosyayı seçin."
        )
    anahtar = frozenset(secili_ids)
    cached = _metin_cache.get(dava_id)
    if cached and cached["ids"] == anahtar:
        return cached["metin"]
    metin = db.dosyalari_metin_birlestir(dava_id)
    _metin_cache[dava_id] = {"ids": anahtar, "metin": metin}
    return metin


@app.post("/api/dava/{dava_id}/sohbet")
async def sohbet(dava_id: str, istek: SohbetIstek):
    dava = db.dava_getir(dava_id)
    metin = _dava_metni(dava_id)
    gecmis = db.sohbet_getir(dava_id)
    try:
        yanit = await gc.sohbet(metin, istek.soru, gecmis, taraf=dava.get("taraf") if dava else None)
    except Exception as e:
        print(f"[SOHBET HATASI] {type(e).__name__}: {e}")
        traceback.print_exc()
        raise HTTPException(500, str(e) or repr(e))
    db.sohbet_kaydet(dava_id, "user", istek.soru)
    db.sohbet_kaydet(dava_id, "assistant", yanit)
    return {"yanit": yanit}


@app.get("/api/dava/{dava_id}/sohbet")
def sohbet_gecmisi(dava_id: str):
    return db.sohbet_getir(dava_id)


@app.post("/api/dava/{dava_id}/durusma")
async def durusma(dava_id: str, istek: DurusmaIstek):
    dava = db.dava_getir(dava_id)
    metin = _dava_metni(dava_id)
    try:
        yanit = await gc.durusma_hazirligi(metin, istek.tarih, taraf=dava.get("taraf") if dava else None)
    except Exception as e:
        print(f"[DURUŞMA HATASI] {type(e).__name__}: {e}")
        traceback.print_exc()
        raise HTTPException(500, str(e) or repr(e))
    db.sohbet_kaydet(dava_id, "user", f"[Duruşma hazırlığı istendi — {istek.tarih}]")
    db.sohbet_kaydet(dava_id, "assistant", yanit)
    return {"yanit": yanit}


@app.get("/api/dava/{dava_id}/ozet")
async def ozet(dava_id: str):
    dava = db.dava_getir(dava_id)
    metin = _dava_metni(dava_id)
    try:
        yanit = await gc.dava_ozeti(metin, taraf=dava.get("taraf") if dava else None)
    except Exception as e:
        print(f"[ÖZET HATASI] {type(e).__name__}: {e}")
        traceback.print_exc()
        raise HTTPException(500, str(e) or repr(e))
    db.sohbet_kaydet(dava_id, "user", "[Dava özeti istendi]")
    db.sohbet_kaydet(dava_id, "assistant", yanit)
    return {"yanit": yanit}


@app.get("/api/dava/{dava_id}/risk")
async def risk(dava_id: str):
    dava = db.dava_getir(dava_id)
    metin = _dava_metni(dava_id)
    try:
        yanit = await gc.risk_analizi(metin, taraf=dava.get("taraf") if dava else None)
    except Exception as e:
        print(f"[RİSK HATASI] {type(e).__name__}: {e}")
        traceback.print_exc()
        raise HTTPException(500, str(e) or repr(e))
    db.sohbet_kaydet(dava_id, "user", "[Risk analizi istendi]")
    db.sohbet_kaydet(dava_id, "assistant", yanit)
    return {"yanit": yanit}


@app.post("/api/dava/{dava_id}/ictihat")
async def ictihat(dava_id: str, istek: IctihatIstek):
    dava = db.dava_getir(dava_id)
    metin = None
    if not istek.sorgu:
        metin = _dava_metni(dava_id)
    try:
        sonuc = await gc.ictihat_arastir(dava_metni=metin, ozel_sorgu=istek.sorgu, taraf=dava.get("taraf") if dava else None)
    except Exception as e:
        print(f"[İÇTİHAT HATASI] {type(e).__name__}: {e}")
        traceback.print_exc()
        raise HTTPException(500, str(e) or repr(e))
    db.ictihat_cache_yaz(dava_id, istek.sorgu or "(otomatik)", sonuc)
    etiket = f"[İçtihat araştırması — {istek.sorgu}]" if istek.sorgu else "[İçtihat araştırması istendi]"
    db.sohbet_kaydet(dava_id, "user", etiket)
    db.sohbet_kaydet(dava_id, "assistant", sonuc)
    return {"yanit": sonuc}
