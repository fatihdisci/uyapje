"""Gemini CLI subprocess wrapper. API key yok — sistem CLI'ı kullanılır."""
import asyncio
import os
import shutil
import subprocess

from promptlar import (
    DILEKCE_PROMPTU,
    DURUSMA_PROMPTU,
    OZET_PROMPTU,
    RISK_PROMPTU,
    SISTEM_PROMPTU,
    TARAF_BILGISI,
)

try:
    TIMEOUT = int(os.getenv("GEMINI_TIMEOUT", "270"))
except (ValueError, TypeError):
    TIMEOUT = 270

try:
    MAX_METIN = int(os.getenv("GEMINI_MAX_METIN", "500000"))
except (ValueError, TypeError):
    MAX_METIN = 500000


def gemini_kurulu_mu() -> bool:
    return shutil.which("gemini") is not None


def _gemini_sync(prompt: str) -> str:
    gemini_yol = shutil.which("gemini")
    if not gemini_yol:
        raise RuntimeError(
            "Gemini CLI bulunamadı. Lütfen 'npm install -g @google/gemini-cli' çalıştırın."
        )
    ortam = {
        **os.environ,
        "PYTHONIOENCODING": "utf-8",
        "GEMINI_CLI_TRUST_WORKSPACE": "true",
    }
    
    import tempfile
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            result = subprocess.run(
                [gemini_yol, "-p", " ", "--yolo", "--skip-trust"],
                input=prompt,
                capture_output=True,
                text=True,
                timeout=TIMEOUT,
                env=ortam,
                cwd=temp_dir,
                encoding="utf-8",
                errors="replace",
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError(
                f"Gemini {TIMEOUT} saniyede yanıt vermedi. Dava metni çok büyük olabilir."
            )
        
        if result.returncode != 0:
            hata = (result.stderr or "").strip()
            print(f"[GEMINI HATA] returncode={result.returncode}")
            print(f"[GEMINI STDERR] {hata[:1000]}")
            print(f"[GEMINI STDOUT] {(result.stdout or '')[:500]}")
            if "auth" in hata.lower() or "login" in hata.lower():
                raise RuntimeError("Gemini auth hatası. Lütfen 'gemini auth login' çalıştırın.")
            if "trust" in hata.lower():
                raise RuntimeError("Gemini trust hatası. Lütfen dizini güvenilir olarak işaretleyin.")
            raise RuntimeError(f"Gemini hatası (kod {result.returncode}): {hata[:500] or (result.stdout or '')[:500]}")
    yanit = (result.stdout or "").strip()
    if not yanit:
        print(f"[GEMINI UYARI] Boş yanıt. stderr: {(result.stderr or '')[:500]}")
    return yanit


async def gemini_calistir(prompt: str) -> str:
    return await asyncio.to_thread(_gemini_sync, prompt)


def get_sistem_promptu(taraf: str = None) -> str:
    p = SISTEM_PROMPTU
    if taraf:
        p += "\n" + TARAF_BILGISI.format(taraf=taraf)
    return p


def gecmis_formatla(gecmis: list, max_karakter: int = 20000) -> str:
    """En yeni mesajlardan geriye doğru max_karakter sığana kadar alır."""
    satirlar = []
    toplam = 0
    for m in reversed(gecmis):
        satir = f"{'Avukat' if m['rol']=='user' else 'Asistan'}: {m['icerik']}"
        if toplam + len(satir) + 1 > max_karakter:
            break
        satirlar.append(satir)
        toplam += len(satir) + 1
    return "\n".join(reversed(satirlar))


async def session_ozeti(gecmis: list) -> str:
    """Uzun bir konuşma geçmişini 3-5 cümleyle özetler (önbellek için)."""
    gecmis_str = gecmis_formatla(gecmis, max_karakter=30000)
    prompt = (
        "Aşağıdaki hukuki danışmanlık konuşmasını kısa ve bilgilendirici şekilde özetle. "
        "Tartışılan hukuki konuları, önemli tespitleri ve varılan sonuçları belirt. "
        "Özet 3-5 cümle olsun, Türkçe yaz.\n\n"
        f"KONUŞMA:\n{gecmis_str}\n\nÖZET:"
    )
    return await gemini_calistir(prompt)


async def sohbet(dava_metni: str, soru: str, gecmis_str: str, taraf: str = None) -> str:
    prompt = f"""{get_sistem_promptu(taraf)}

DAVA DOSYASI:
{dava_metni[:MAX_METIN]}

SOHBET GEÇMİŞİ:
{gecmis_str}

AVUKATIN SORUSU: {soru}

YANIT:"""
    return await gemini_calistir(prompt)


async def durusma_hazirligi(dava_metni: str, tarih: str, taraf: str = None) -> str:
    prompt = get_sistem_promptu(taraf) + "\n\n" + DURUSMA_PROMPTU.format(
        dava_metni=dava_metni[:MAX_METIN], tarih=tarih
    )
    return await gemini_calistir(prompt)


async def dava_ozeti(dava_metni: str, taraf: str = None) -> str:
    prompt = get_sistem_promptu(taraf) + "\n\n" + OZET_PROMPTU.format(dava_metni=dava_metni[:MAX_METIN])
    return await gemini_calistir(prompt)


async def risk_analizi(dava_metni: str, taraf: str = None) -> str:
    prompt = get_sistem_promptu(taraf) + "\n\n" + RISK_PROMPTU.format(dava_metni=dava_metni[:MAX_METIN])
    return await gemini_calistir(prompt)


async def _dava_hukuki_ozet(dava_metni: str, dilekce_turu: str) -> str:
    """Dava metninden içtihat araştırması için kısa hukuki özet çıkarır."""
    prompt = (
        f"Aşağıdaki dava dosyasını oku ve '{dilekce_turu}' yazılması için "
        f"gereken Yargıtay/Danıştay içtihadını bulmak amacıyla kullanılacak "
        f"kısa bir hukuki özet çıkar. Özet: uyuşmazlık konusu, ilgili kanun maddeleri, "
        f"tarafların temel argümanları. 10-15 cümle, sadece Türkçe.\n\n"
        f"DAVA:\n{dava_metni[:80000]}"
    )
    try:
        return await gemini_calistir(prompt)
    except RuntimeError:
        return dava_metni[:3000]


async def _dilekce_ictihat(ozet: str, dilekce_turu: str) -> str:
    """Dava özetine göre dilekçe için 3-5 içtihat araştırır."""
    prompt = (
        f"Yargı MCP araçlarını kullanarak '{dilekce_turu}' için aşağıdaki davaya "
        f"en uygun 3-5 Yargıtay/Danıştay kararını bul ve listele.\n"
        f"Her karar için: karar no, daire, tarih ve ilgili tek cümle özet yaz.\n\n"
        f"DAVA ÖZETİ:\n{ozet}"
    )
    try:
        return await gemini_calistir(prompt)
    except RuntimeError:
        return ""


async def dilekce_olustur(
    dava_metni: str,
    dilekce_turu: str,
    tarih: str,
    mahkeme: str,
    esas_no: str,
    konu: str,
    ek_talimat: str = "",
    ictihat_ekle: bool = False,
) -> str:
    ictihat_metni = ""
    if ictihat_ekle:
        print(f"[DİLEKÇE] 1/3: İçtihat için hukuki özet çıkarılıyor...")
        ozet = await _dava_hukuki_ozet(dava_metni, dilekce_turu)
        print(f"[DİLEKÇE] 2/3: Yargı MCP ile içtihat araştırılıyor...")
        ictihat_metni = await _dilekce_ictihat(ozet, dilekce_turu)
    else:
        print(f"[DİLEKÇE] İçtihat araştırması atlandı (hızlı mod).")

    ek_talimat_str = f"EK TALİMAT: {ek_talimat}" if ek_talimat else ""
    print(f"[DİLEKÇE] Ana dilekçe metni yazılıyor...")
    ictihat_blok = (
        f"\nİLGİLİ YARGITAY KARARLARI (hukuki dayanak olarak kullan):\n{ictihat_metni}\n"
        if ictihat_metni else ""
    )

    prompt = DILEKCE_PROMPTU.format(
        dava_metni=dava_metni[:MAX_METIN],
        dilekce_turu=dilekce_turu,
        tarih=tarih,
        mahkeme=mahkeme,
        esas_no=esas_no,
        konu=konu,
        ek_talimat=ictihat_blok + ek_talimat_str,
    )
    return await gemini_calistir(prompt)


async def ictihat_arastir(dava_metni: str = None, ozel_sorgu: str = None, taraf: str = None) -> str:
    if ozel_sorgu:
        prompt = (
            f"Yargı MCP araçlarını kullanarak şu konuyu detaylıca araştır: {ozel_sorgu}\n"
            "Bulduğun kararları Markdown formatında, okunaklı bir şekilde listele:\n"
            "- Karar numarası ve tarihini belirgin (**kalın**) yaz.\n"
            "- İlgili daireyi ve mahkemeyi belirt.\n"
            "- Kararın özetini veya ilgili kısmını madde imleriyle yaz.\n"
            "Yanıtı sade ve hukuki bir Türkçe ile ver."
        )
    else:
        prompt = f"""{get_sistem_promptu(taraf)}

Aşağıdaki dava dosyasını analiz et. Yargı MCP araçlarını kullanarak:
1. Davadaki temel hukuki konulara dair Yargıtay/Danıştay kararlarını araştır.
2. Kararları Markdown formatında düzenli bir şekilde listele (Karar numarası, tarihi, dairesi ve özet bilgisini içersin).
3. Bu kararların davayla ilişkisini net bir şekilde açıkla.

DAVA:
{(dava_metni or '')[:MAX_METIN]}"""
    return await gemini_calistir(prompt)
