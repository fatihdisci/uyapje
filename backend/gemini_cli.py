"""Gemini CLI subprocess wrapper. API key yok — sistem CLI'ı kullanılır."""
import asyncio
import os
import shutil
import subprocess

from promptlar import (
    DURUSMA_PROMPTU,
    OZET_PROMPTU,
    RISK_PROMPTU,
    SISTEM_PROMPTU,
)

TIMEOUT = int(os.getenv("GEMINI_TIMEOUT", "180"))


def gemini_kurulu_mu() -> bool:
    return shutil.which("gemini") is not None


def _gemini_sync(prompt: str) -> str:
    """Gemini CLI'ı senkron subprocess olarak çalıştırır (thread içinden çağrılır)."""
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

    try:
        result = subprocess.run(
            [gemini_yol, "-p", " ", "--yolo", "--skip-trust"],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
            env=ortam,
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
    """Gemini CLI'ı thread pool üzerinden çalıştırır (Windows uyumlu)."""
    return await asyncio.to_thread(_gemini_sync, prompt)


async def sohbet(dava_metni: str, soru: str, gecmis: list) -> str:
    gecmis_str = "\n".join(
        f"{'Avukat' if m['rol']=='user' else 'Asistan'}: {m['icerik']}"
        for m in gecmis[-6:]
    )
    prompt = f"""{SISTEM_PROMPTU}

DAVA DOSYASI:
{dava_metni[:50000]}

SOHBET GEÇMİŞİ:
{gecmis_str}

AVUKATIN SORUSU: {soru}

YANIT:"""
    return await gemini_calistir(prompt)


async def durusma_hazirligi(dava_metni: str, tarih: str) -> str:
    prompt = SISTEM_PROMPTU + "\n\n" + DURUSMA_PROMPTU.format(
        dava_metni=dava_metni[:50000], tarih=tarih
    )
    return await gemini_calistir(prompt)


async def dava_ozeti(dava_metni: str) -> str:
    prompt = SISTEM_PROMPTU + "\n\n" + OZET_PROMPTU.format(dava_metni=dava_metni[:50000])
    return await gemini_calistir(prompt)


async def risk_analizi(dava_metni: str) -> str:
    prompt = SISTEM_PROMPTU + "\n\n" + RISK_PROMPTU.format(dava_metni=dava_metni[:50000])
    return await gemini_calistir(prompt)


async def ictihat_arastir(dava_metni: str = None, ozel_sorgu: str = None) -> str:
    """Yargı MCP tool'ları Gemini settings.json'da kayıtlıysa otomatik çağrılır."""
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
        prompt = f"""{SISTEM_PROMPTU}

Aşağıdaki dava dosyasını analiz et. Yargı MCP araçlarını kullanarak:
1. Davadaki temel hukuki konulara dair Yargıtay/Danıştay kararlarını araştır.
2. Kararları Markdown formatında düzenli bir şekilde listele (Karar numarası, tarihi, dairesi ve özet bilgisini içersin).
3. Bu kararların davayla ilişkisini net bir şekilde açıkla.

DAVA:
{(dava_metni or '')[:20000]}"""
    return await gemini_calistir(prompt)
