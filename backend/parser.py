"""Dosya parser modulu — PDF/TIFF/UDF/ZIP/DOCX → düz metin."""
import os
import re
import tempfile
import zipfile

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


def udf_parse(yol: str) -> dict:
    parcalar = []
    with zipfile.ZipFile(yol, 'r') as z:
        for isim in z.namelist():
            if isim.endswith('.xml'):
                xml = z.read(isim).decode('utf-8', errors='replace')
                try:
                    parcalar.append(f"[XML:{isim}]\n{str(xmltodict.parse(xml))[:5000]}")
                except Exception:
                    parcalar.append(f"[XML ham:{isim}]\n{xml[:5000]}")
            elif isim.endswith('.pdf'):
                with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
                    tmp.write(z.read(isim))
                    tmp_yol = tmp.name
                try:
                    parcalar.append(f"[UDF>{isim}]\n{pdf_parse(tmp_yol)['metin']}")
                finally:
                    os.unlink(tmp_yol)
    return {"metin": "\n\n".join(parcalar), "meta": {"kaynak": "udf"}}


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
