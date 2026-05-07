"""UYAP UDF dilekçe oluşturucu.

Eskiden manuel ZIP/HVL formatı yazıyorduk. Artık `udf-cli` (saidsurucu/udf-cli)
Node.js paketine devrediyoruz. Bu paket HTML/Markdown ↔ UDF dönüşümünü
production-grade yapıyor (tablolar, runs, stiller, image, vs).

Akış:
  Gemini'nin verdiği XML  →  semantik HTML  →  `udf-cli html2udf` (subprocess)  →  UDF bytes

Frontend XML şeması ve DilekcePreview UI değişmedi; sadece UDF üretimi değişti.

Gerekli kurulum: `npm install -g udf-cli` (udf-cli komutu PATH'te olmalı).
"""
import re
import shutil
import subprocess
from html import escape as h
from xml.etree import ElementTree as ET


# ── XML ayrıştır ────────────────────────────────────────────────────────────

def _xml_parse(xml_str: str) -> ET.Element:
    xml_str = xml_str.strip()
    xml_str = re.sub(r"^```xml\s*", "", xml_str)
    xml_str = re.sub(r"^```\s*", "", xml_str)
    xml_str = re.sub(r"\s*```$", "", xml_str)
    xml_str = xml_str.strip()
    if not xml_str.startswith("<?xml"):
        xml_str = '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_str
    return ET.fromstring(xml_str.encode("utf-8"))


def _temiz_metin(metin: str) -> str:
    metin = metin or ""
    metin = re.sub(r"</?[^>]+>", "", metin)
    metin = re.sub(r"\n{3,}", "\n\n", metin)
    return metin.strip()


def _txt(el: ET.Element, tag: str, default: str = "") -> str:
    if el is None:
        return default
    found = el.find(tag)
    if found is None:
        return default
    return _temiz_metin("".join(found.itertext()))


def _maddeler(el: ET.Element) -> list:
    if el is None:
        return []
    return [_temiz_metin("".join(m.itertext())) for m in el.findall("madde") if _temiz_metin("".join(m.itertext()))]


def _basliktan_arindir(metin: str, basliklar: list[str]) -> str:
    metin = _temiz_metin(metin)
    for baslik in basliklar:
        metin = re.sub(rf"^\s*{re.escape(baslik)}\s*:?\s*", "", metin, flags=re.I)
    return metin.strip()


# ── XML → HTML çevirimi (udf-cli için semantik HTML) ────────────────────────

def dilekce_html(root: ET.Element) -> str:
    """Gemini'nin XML'inden UYAP dilekçe formatına uygun semantik HTML üretir."""
    mahkeme      = _txt(root, "mahkeme")
    esas_no      = _txt(root, "esas_no")
    tarih        = _txt(root, "tarih")
    konu_metin   = _txt(root, "konu_metin") or _txt(root, "konu")

    bas_el       = root.find("basliklar")
    mahkeme_adi  = _txt(bas_el, "mahkeme_adi") if bas_el is not None else f"{mahkeme} MAHKEMESİ SAYIN HAKİMLİĞİNE"
    mahkeme_adi  = mahkeme_adi.replace(" SAYIN HAKİMLİĞİNE", "NE")

    tar_el       = root.find("taraflar")
    davaci_et    = _txt(tar_el, "davaci_etiketi") if tar_el is not None else "DAVACI"
    davaci_bilgi = _txt(tar_el, "davaci_bilgi")   if tar_el is not None else ""
    davali_et    = _txt(tar_el, "davali_etiketi") if tar_el is not None else "DAVALI"
    davali_bilgi = _txt(tar_el, "davali_bilgi")   if tar_el is not None else ""
    vekil_bilgi  = _txt(tar_el, "vekil_bilgi")    if tar_el is not None else "Av. Fatih Dişçi"

    aciklamalar  = _maddeler(root.find("aciklamalar"))
    sonuclar     = _maddeler(root.find("sonuc"))
    hukuki       = _basliktan_arindir(_txt(root, "hukuki_dayanak"), ["HUKUKİ DAYANAK", "HUKUKI DAYANAK"])

    imza_el      = root.find("imza")
    imza_tarih   = _txt(imza_el, "tarih_yer") if imza_el is not None else tarih
    imza_unvan   = _txt(imza_el, "unvan")     if imza_el is not None else "Av. Fatih Dişçi"

    davaci_label = re.sub(r"\s+", " ", davaci_et.replace("(MÜVEKKİL)", "")).strip().rstrip(":") or "DAVACI"
    davali_label = re.sub(r"\s+", " ", davali_et).strip().rstrip(":") or "DAVALI"

    parts: list[str] = []
    parts.append(
        f'<p style="text-align:justify;font-weight:bold">{h(mahkeme_adi)}</p>'
    )
    parts.append("<p>&nbsp;</p>")

    def _etiket(label: str, value: str) -> str:
        # Etiket bold + underline (UYAP klasik), değer normal — aynı paragrafta.
        val = f" {h(value)}" if value else ""
        return (
            f'<p style="text-align:justify">'
            f'<strong><u>{h(label)}\t\t:</u></strong>{val}'
            f'</p>'
        )

    if esas_no:
        no = esas_no if esas_no.endswith(".") else f"{esas_no}."
        parts.append(_etiket("DOSYA NO", no))
        parts.append("<p>&nbsp;</p>")

    parts.append(_etiket(davaci_label, davaci_bilgi))
    parts.append(_etiket("VEKİLİ", vekil_bilgi))
    parts.append("<p>&nbsp;</p>")
    if davali_bilgi:
        parts.append(_etiket(davali_label, davali_bilgi))
        parts.append("<p>&nbsp;</p>")

    parts.append(_etiket("KONU", konu_metin))
    parts.append("<p>&nbsp;</p>")

    parts.append(_etiket("AÇIKLAMALAR", ""))
    parts.append("<p>&nbsp;</p>")
    for i, madde in enumerate(aciklamalar, 1):
        if not madde:
            continue
        madde = re.sub(r"^\s*\d+\s*[-.)]\s*", "", madde)
        parts.append(
            f'<p style="text-align:justify;text-indent:28pt">'
            f'<strong>{i}.</strong> {h(madde)}'
            f'</p>'
        )
        parts.append("<p>&nbsp;</p>")

    if hukuki:
        parts.append(_etiket("HUKUKİ DAYANAK", hukuki))
        parts.append("<p>&nbsp;</p>")

    parts.append(_etiket("NETİCE VE TALEP", "Yukarıda arz ve izah edilen nedenlerle;"))
    parts.append("<p>&nbsp;</p>")
    for madde in sonuclar:
        if not madde:
            continue
        madde = re.sub(r"^\s*\d+\s*[-.)]\s*", "", madde)
        parts.append(
            f'<p style="text-align:justify;text-indent:28pt">{h(madde)}</p>'
        )
        parts.append("<p>&nbsp;</p>")

    if imza_tarih:
        parts.append(f'<p style="text-align:right">{h(imza_tarih)}</p>')
    if imza_unvan:
        parts.append(f'<p style="text-align:right;font-weight:bold">{h(imza_unvan)}</p>')

    body = "\n".join(parts)
    return (
        '<!DOCTYPE html><html><head><meta charset="utf-8"></head>'
        f'<body style="font-family:Times New Roman;font-size:12pt">{body}</body></html>'
    )


# ── udf-cli subprocess wrapper ──────────────────────────────────────────────

def _udf_cli_yolu() -> str:
    yol = shutil.which("udf-cli")
    if yol:
        return yol
    # Windows global npm bin: udf-cli.cmd
    yol = shutil.which("udf-cli.cmd")
    if yol:
        return yol
    raise RuntimeError(
        "udf-cli bulunamadı. Lütfen 'npm install -g udf-cli' çalıştırın."
    )


def html_to_udf(html: str) -> bytes:
    """udf-cli html2udf ile HTML'i UDF binary'sine çevirir."""
    cli = _udf_cli_yolu()
    proc = subprocess.run(
        [cli, "html2udf", "-"],
        input=html.encode("utf-8"),
        capture_output=True,
        timeout=60,
    )
    if proc.returncode != 0:
        stderr = (proc.stderr or b"").decode("utf-8", errors="replace")
        raise RuntimeError(f"udf-cli html2udf hatası: {stderr.strip() or 'bilinmeyen hata'}")
    if not proc.stdout:
        raise RuntimeError("udf-cli html2udf boş çıktı verdi.")
    return proc.stdout


def md_to_udf(markdown: str) -> bytes:
    cli = _udf_cli_yolu()
    proc = subprocess.run(
        [cli, "md2udf", "-"],
        input=markdown.encode("utf-8"),
        capture_output=True,
        timeout=60,
    )
    if proc.returncode != 0:
        stderr = (proc.stderr or b"").decode("utf-8", errors="replace")
        raise RuntimeError(f"udf-cli md2udf hatası: {stderr.strip() or 'bilinmeyen hata'}")
    return proc.stdout


def udf_to_markdown(udf_bytes: bytes) -> str:
    """UDF binary'sini Markdown formatına çevirir (formatlı, okunaklı)."""
    cli = _udf_cli_yolu()
    proc = subprocess.run(
        [cli, "udf2md", "-"],
        input=udf_bytes,
        capture_output=True,
        timeout=60,
    )
    if proc.returncode != 0:
        stderr = (proc.stderr or b"").decode("utf-8", errors="replace")
        raise RuntimeError(f"udf-cli udf2md hatası: {stderr.strip() or 'bilinmeyen hata'}")
    return (proc.stdout or b"").decode("utf-8", errors="replace")


def udf_to_html(udf_bytes: bytes) -> str:
    cli = _udf_cli_yolu()
    proc = subprocess.run(
        [cli, "udf2html", "-"],
        input=udf_bytes,
        capture_output=True,
        timeout=60,
    )
    if proc.returncode != 0:
        stderr = (proc.stderr or b"").decode("utf-8", errors="replace")
        raise RuntimeError(f"udf-cli udf2html hatası: {stderr.strip() or 'bilinmeyen hata'}")
    return (proc.stdout or b"").decode("utf-8", errors="replace")


# ── Üst seviye API (main.py bunu çağırıyor) ─────────────────────────────────

def xml_to_udf(xml_str: str, baslik: str = "dilekce") -> bytes:
    """Gemini'nin XML çıktısını alır → semantik HTML → udf-cli → UDF bytes."""
    root = _xml_parse(xml_str)
    html = dilekce_html(root)
    return html_to_udf(html)
