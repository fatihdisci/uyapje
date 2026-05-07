"""Dosya parser modulu — PDF/TIFF/UDF/ZIP/DOCX → düz metin."""
import os
import re
import tempfile
import zipfile
from xml.etree import ElementTree as ET

import pdfplumber
import pytesseract
import xmltodict
from docx import Document
from PIL import Image

# Tesseract yolu (Windows)
_TESS_PATH = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
if os.path.exists(_TESS_PATH):
    pytesseract.pytesseract.tesseract_cmd = _TESS_PATH


def pdf_parse(yol: str) -> dict:
    parcalar = []
    with pdfplumber.open(yol) as pdf:
        for i, sayfa in enumerate(pdf.pages):
            metin = sayfa.extract_text() or ""
            parcalar.append(f"[Sayfa {i+1}]\n{metin}")
    return {"metin": "\n\n".join(parcalar), "meta": {"sayfa": len(parcalar)}}


def tiff_parse(yol: str) -> dict:
    parcalar = []
    img = Image.open(yol)
    try:
        for frame in range(getattr(img, 'n_frames', 1)):
            img.seek(frame)
            kopyasi = img.copy().convert("RGB")
            if kopyasi.width > 2000:
                oran = 2000 / kopyasi.width
                kopyasi = kopyasi.resize((2000, int(kopyasi.height * oran)))
            parcalar.append(pytesseract.image_to_string(kopyasi, lang='tur'))
    finally:
        img.close()
    return {"metin": "\n\n".join(parcalar), "meta": {"frame": len(parcalar)}}


def _xml_duz_metin(xml: str) -> str:
    """UYAP/HVL content.xml içinden okunabilir düz metin çıkarır."""
    try:
        root = ET.fromstring(xml.encode('utf-8'))
        content = root.find('.//content')
        if content is not None and content.text:
            return content.text.strip()
    except Exception:
        pass

    # Bazı UDF/XML dosyaları namespace/bozuk karakter yüzünden parse edilemeyebilir.
    m = re.search(r'<content[^>]*><!\[CDATA\[([\s\S]*?)\]\]></content>', xml, re.I)
    if m:
        return m.group(1).strip()
    m = re.search(r'<content[^>]*>([\s\S]*?)</content>', xml, re.I)
    if m:
        return re.sub(r'<[^>]+>', ' ', m.group(1)).strip()

    try:
        parsed = xmltodict.parse(xml)
        return str(parsed)[:10000]
    except Exception:
        return re.sub(r'<[^>]+>', ' ', xml)[:10000]


def _udf_cli_metin(yol: str) -> str:
    """udf-cli udf2md ile UDF'yi formatlı Markdown'a çevirir. Yoksa boş döner."""
    import shutil as _sh
    import subprocess as _sp
    cli = _sh.which('udf-cli') or _sh.which('udf-cli.cmd')
    if not cli:
        return ''
    try:
        proc = _sp.run(
            [cli, 'udf2md', yol],
            capture_output=True,
            timeout=60,
        )
        if proc.returncode == 0 and proc.stdout:
            return proc.stdout.decode('utf-8', errors='replace').strip()
    except Exception:
        pass
    return ''


def udf_parse(yol: str) -> dict:
    # Önce udf-cli ile dene — formatı koruyarak Markdown çıkarır.
    md = _udf_cli_metin(yol)
    if md:
        # UDF içinde gömülü PDF varsa onları da ekle (udf-cli sadece content.xml'i okur).
        ekler = []
        try:
            with zipfile.ZipFile(yol, 'r') as z:
                for isim in z.namelist():
                    if isim.lower().endswith('.pdf'):
                        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
                            tmp.write(z.read(isim))
                            tmp_yol = tmp.name
                        try:
                            ekler.append(f"[UDF>{isim}]\n{pdf_parse(tmp_yol)['metin']}")
                        finally:
                            os.unlink(tmp_yol)
        except zipfile.BadZipFile:
            pass
        gov = md if not ekler else md + "\n\n" + "\n\n".join(ekler)
        return {"metin": gov, "meta": {"kaynak": "udf", "yontem": "udf-cli"}}

    # Fallback: ham CDATA okuyucu (udf-cli kurulu değilse).
    parcalar = []
    with zipfile.ZipFile(yol, 'r') as z:
        for isim in z.namelist():
            lower = isim.lower()
            if lower.endswith('.xml'):
                xml = z.read(isim).decode('utf-8', errors='replace')
                metin = _xml_duz_metin(xml)
                if metin:
                    parcalar.append(f"[UDF>{isim}]\n{metin}")
            elif lower.endswith('.pdf'):
                with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
                    tmp.write(z.read(isim))
                    tmp_yol = tmp.name
                try:
                    parcalar.append(f"[UDF>{isim}]\n{pdf_parse(tmp_yol)['metin']}")
                finally:
                    os.unlink(tmp_yol)
    return {"metin": "\n\n".join(parcalar), "meta": {"kaynak": "udf", "yontem": "fallback"}}


def zip_parse(yol: str) -> dict:
    parcalar = []
    with zipfile.ZipFile(yol, 'r') as z:
        for isim in z.namelist():
            if isim.endswith('/'):
                continue
            ext = isim.lower().split('.')[-1]
            with tempfile.NamedTemporaryFile(suffix=f'.{ext}', delete=False) as tmp:
                tmp.write(z.read(isim))
                tmp_yol = tmp.name
            try:
                parcalar.append(f"[ZIP>{isim}]\n{dosya_parse(tmp_yol)['metin']}")
            except Exception as e:
                parcalar.append(f"[ZIP>{isim}] HATA: {e}")
            finally:
                os.unlink(tmp_yol)
    return {"metin": "\n\n".join(parcalar), "meta": {}}


def docx_parse(yol: str) -> dict:
    doc = Document(yol)
    satirlar = []
    for p in doc.paragraphs:
        prefix = "## " if p.style.name.startswith("Heading") else ""
        if p.text.strip():
            satirlar.append(prefix + p.text)
    return {"metin": "\n".join(satirlar), "meta": {}}


def tc_maskele(metin: str) -> str:
    return re.sub(r'\b[1-9][0-9]{10}\b', '[KIMLIK GIZLENDI]', metin)


_PARSERS = {
    'pdf': pdf_parse,
    'tiff': tiff_parse,
    'tif': tiff_parse,
    'udf': udf_parse,
    'zip': zip_parse,
    'docx': docx_parse,
}


def dosya_parse(yol: str) -> dict:
    ext = yol.lower().split('.')[-1]
    parser = _PARSERS.get(ext)
    if parser:
        sonuc = parser(yol)
    else:
        with open(yol, 'r', errors='replace') as f:
            sonuc = {"metin": f.read(), "meta": {}}
    sonuc["metin"] = tc_maskele(sonuc["metin"])
    return sonuc
