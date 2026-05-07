"""Deterministik evrak analizi ve dava kronolojisi.

Gemini çağırmadan, parse edilmiş metinden hızlı metadata çıkarır. Amaç:
- yüklenen evrakların türünü/tarihini/taraflarını işaretlemek
- kronoloji ve belge envanteri üretmek
- AI promptlarına daha temiz bağlam hazırlamak
"""
import re
from datetime import datetime


_TUR_KURALLARI = [
    ("Bilirkişi Raporu", ["bilirkişi raporu", "bilirkişi heyeti", "rapor tanzim"]),
    ("Bilirkişi Raporuna İtiraz", ["bilirkişi raporuna itiraz", "rapora itiraz", "raporuna itiraz", "ek rapor alınması"]),
    ("Dava Dilekçesi", ["dava dilekçesi", "davacı", "davalı", "konu", "açıklamalar", "sonuç ve talep"]),
    ("Cevap Dilekçesi", ["cevap dilekçesi", "davaya cevap", "cevaplarımız"]),
    ("Beyan Dilekçesi", ["beyan dilekçesi", "beyanlarımız", "beyanlarımızın sunulması"]),
    ("Talep Dilekçesi", ["talep dilekçesi", "talebimiz", "talep ederiz"]),
    ("Duruşma Tutanağı", ["duruşma tutanağı", "celse", "açık yargılamaya devam olundu"]),
    ("Tensip Zaptı", ["tensip zaptı", "tensiben"]),
    ("Gerekçeli Karar", ["gerekçeli karar", "hüküm", "karar verildi"]),
    ("Ara Karar", ["ara karar", "duruşmanın bırakılmasına"]),
    ("Keşif Tutanağı", ["keşif tutanağı", "mahallinde keşif"]),
    ("Tebligat", ["tebliğ mazbatası", "tebligat", "tebliğ edildi"]),
    ("İstinaf Dilekçesi", ["istinaf", "bölge adliye mahkemesi"]),
    ("Temyiz Dilekçesi", ["temyiz", "yargıtay"]),
]

_TARIH_RE = re.compile(r"\b(0?[1-9]|[12][0-9]|3[01])[./-](0?[1-9]|1[0-2])[./-]((?:19|20)\d{2})\b")
_KANUN_RE = re.compile(r"\b(?:HMK|TBK|TMK|TCK|CMK|İİK|IİK|TTK|KTK|KVKK|AY|Anayasa)\s*m\.?\s*\d+[\w/.-]*", re.I)
_ESAS_RE = re.compile(r"\b(?:20\d{2})/\d+\s*(?:E\.?|Esas|D\.İş|D\. İş|K\.?)?", re.I)


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())


def _cumleler(metin: str, limit: int = 80) -> list[str]:
    temiz = re.sub(r"\s+", " ", metin or " ").strip()
    parcalar = re.split(r"(?<=[.!?])\s+", temiz)
    return [p.strip() for p in parcalar if len(p.strip()) > 20][:limit]


def _ilk_eslesen_satir(metin: str, etiketler: list[str]) -> str:
    for line in (metin or "").splitlines():
        l = line.strip()
        low = l.lower()
        if any(low.startswith(e.lower()) for e in etiketler):
            if ":" in l:
                return _norm(l.split(":", 1)[1])
            return _norm(l)
    return ""


def evrak_turu_bul(dosya_adi: str, metin: str) -> str:
    low = f"{dosya_adi}\n{metin[:5000]}".lower()
    skorlar = []
    for tur, anahtarlar in _TUR_KURALLARI:
        skor = sum(1 for a in anahtarlar if a in low)
        if skor:
            skorlar.append((skor, tur))
    if skorlar:
        return sorted(skorlar, reverse=True)[0][1]
    ext = dosya_adi.lower().rsplit(".", 1)[-1] if "." in dosya_adi else ""
    return {"pdf": "PDF Evrak", "udf": "UDF Evrak", "docx": "Word Evrak", "zip": "Arşiv"}.get(ext, "Evrak")


def tarihleri_bul(metin: str) -> list[str]:
    bulunan = []
    for g, a, y in _TARIH_RE.findall(metin or ""):
        tarih = f"{int(g):02d}.{int(a):02d}.{y}"
        if tarih not in bulunan:
            bulunan.append(tarih)
        if len(bulunan) >= 10:
            break
    return bulunan


def iso_tarih(tarih: str) -> str | None:
    try:
        return datetime.strptime(tarih, "%d.%m.%Y").date().isoformat()
    except Exception:
        return None


def taraflari_bul(metin: str) -> dict:
    return {
        "davaci": _ilk_eslesen_satir(metin, ["DAVACI", "DAVACILAR", "TALEP EDEN"]),
        "davali": _ilk_eslesen_satir(metin, ["DAVALI", "DAVALILAR", "KARŞI TARAF"]),
        "vekil": _ilk_eslesen_satir(metin, ["VEKİLİ", "DAVACI VEKİLİ", "DAVALI VEKİLİ"]),
    }


def maddeleri_bul(metin: str, kelimeler: list[str], maks: int = 5) -> list[str]:
    out = []
    for c in _cumleler(metin):
        low = c.lower()
        if any(k in low for k in kelimeler):
            out.append(c[:500])
        if len(out) >= maks:
            break
    return out


def ozet_cikar(metin: str, tur: str) -> str:
    satirlar = [_norm(x) for x in (metin or "").splitlines() if len(_norm(x)) > 40]
    secilen = satirlar[:3]
    if not secilen:
        return f"{tur} olarak sınıflandırıldı; anlamlı özet çıkaracak kadar metin bulunamadı."
    ozet = " ".join(secilen)
    return ozet[:900] + ("…" if len(ozet) > 900 else "")


def evrak_analiz_et(dosya_adi: str, metin: str, format: str = "") -> dict:
    metin = metin or ""
    tur = evrak_turu_bul(dosya_adi, metin)
    tarihler = tarihleri_bul(metin)
    hukuki = []
    for m in _KANUN_RE.findall(metin):
        v = _norm(m)
        if v not in hukuki:
            hukuki.append(v)
        if len(hukuki) >= 12:
            break
    esaslar = []
    for m in _ESAS_RE.findall(metin):
        v = _norm(m)
        if v not in esaslar:
            esaslar.append(v)
        if len(esaslar) >= 8:
            break
    talepler = maddeleri_bul(metin, ["talep", "kabul", "redd", "itiraz", "karar veril", "arz"], 6)
    deliller = maddeleri_bul(metin, ["delil", "fotoğraf", "kamera", "bilirkişi", "rapor", "keşif", "tanık", "belge"], 6)
    taraflar = taraflari_bul(metin)
    ana_tarih = tarihler[0] if tarihler else ""
    return {
        "evrak_turu": tur,
        "evrak_tarihi": ana_tarih,
        "evrak_tarihi_iso": iso_tarih(ana_tarih) if ana_tarih else None,
        "tarihler": tarihler,
        "taraflar": taraflar,
        "esas_no_lar": esaslar,
        "hukuki_dayanaklar": hukuki,
        "talepler": talepler,
        "deliller": deliller,
        "ozet": ozet_cikar(metin, tur),
        "format": format,
    }


def analiz_markdown(dosyalar: list[dict]) -> str:
    if not dosyalar:
        return "Bu davada analiz edilecek evrak yok."
    lines = ["## Belge Analizi", ""]
    for d in dosyalar:
        a = d.get("analiz") or {}
        lines.append(f"### {d.get('dosya_adi', 'Evrak')}")
        lines.append(f"- **Tür:** {a.get('evrak_turu', 'Evrak')}")
        if a.get("evrak_tarihi"):
            lines.append(f"- **Tarih:** {a['evrak_tarihi']}")
        if a.get("esas_no_lar"):
            lines.append(f"- **Dosya/Karar No:** {', '.join(a['esas_no_lar'][:3])}")
        lines.append(f"- **Özet:** {a.get('ozet', '')}")
        if a.get("hukuki_dayanaklar"):
            lines.append(f"- **Hukuki dayanak:** {', '.join(a['hukuki_dayanaklar'][:6])}")
        if a.get("talepler"):
            lines.append("- **Öne çıkan talep/sonuç:**")
            lines.extend([f"  - {x}" for x in a["talepler"][:3]])
        lines.append("")
    return "\n".join(lines)


def kronoloji_markdown(dosyalar: list[dict]) -> str:
    events = []
    for d in dosyalar:
        a = d.get("analiz") or {}
        tarih = a.get("evrak_tarihi")
        iso = a.get("evrak_tarihi_iso")
        if tarih and iso:
            events.append((iso, tarih, a.get("evrak_turu", "Evrak"), d.get("dosya_adi", ""), a.get("ozet", "")[:220]))
    if not events:
        return "## Kronoloji\n\nTarih tespit edilebilen evrak bulunamadı."
    lines = ["## Dava Kronolojisi", ""]
    for _, tarih, tur, ad, ozet in sorted(events):
        lines.append(f"- **{tarih}** — {tur} (`{ad}`): {ozet}")
    return "\n".join(lines)
