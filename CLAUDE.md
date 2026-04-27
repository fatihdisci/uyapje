# UYAP Hukuk Asistanı

Solo avukat için lokal hukuk asistanı. UYAP dosyalarını (PDF/TIFF/UDF/ZIP/DOCX) okuyup analiz eder, Gemini CLI üzerinden duruşma hazırlığı, dava özeti, risk analizi ve Yargıtay içtihat araştırması yapar.

## Mimari

```
[React+Vite UI:5173]  ←HTTP→  [FastAPI:8000]  ←subprocess→  [gemini CLI]
                                                                   ↓
                                                         [Yargı MCP tools]
```

- **API key kullanılmaz.** Gemini, sistem genelinde kurulu `gemini` CLI üzerinden `subprocess` ile çağrılır. Auth Google AI Pro üyeliğiyle bir kere yapılır (`gemini auth login`).
- **Yargı MCP** Gemini CLI'ın `~/.gemini/settings.json` dosyasına `yargi_mcp` (uvx) olarak eklenir. Backend'de ek kod yok — Gemini gerektiğinde otomatik tool call yapar.
- **State** SQLite (`uyap.db`) — davalar, dosyalar (parse edilmiş metin), sohbet geçmişi.
- **TC kimlik maskeleme** parser seviyesinde regex (`[1-9][0-9]{10}` → `[KIMLIK GIZLENDI]`).

## Klasör Yapısı

```
backend/
  main.py         FastAPI uygulaması, tüm endpointler
  parser.py       PDF/TIFF/UDF/ZIP/DOCX → metin
  gemini_cli.py   Gemini subprocess wrapper (stdin yoluyla)
  database.py     SQLite CRUD
  promptlar.py    Sistem promptları
  requirements.txt
frontend/
  src/
    App.jsx, main.jsx, api.js, styles.css
    components/
      Sidebar.jsx, ChatPanel.jsx, FileStrip.jsx, IctihatPanel.jsx
start.bat
.env  (UYAP_DIZIN, DB_YOL, GEMINI_TIMEOUT)
```

## Kurulum

1. `npm install -g @google/gemini-cli` ve `gemini auth login`
2. `pip install -r backend/requirements.txt`
3. `cd frontend && npm install`
4. (Opsiyonel) Yargı MCP — `~/.gemini/settings.json`:
   ```json
   { "mcpServers": { "yargi_mcp": { "command": "uvx", "args": ["yargi-mcp"] } } }
   ```
5. (Opsiyonel) Tesseract-OCR for `tur` dili (TIFF için)
6. `start.bat` ile çalıştır — http://localhost:5173

## Önemli Endpointler

```
GET  /api/sistem/durum         { gemini_kurulu, gemini_hazir, yargi_mcp_aktif }
POST /api/dava                 yeni dava
POST /api/dava/{id}/dosya      multipart upload, parse → SQLite
POST /api/dava/{id}/sohbet     { soru } → { yanit }
POST /api/dava/{id}/durusma    { tarih } → hazırlık notu
GET  /api/dava/{id}/ozet       dava özeti
GET  /api/dava/{id}/risk       risk analizi
POST /api/dava/{id}/ictihat    { sorgu? } → Yargıtay araştırması (Yargı MCP)
```

## Geliştirme Notları

- Tüm UI Türkçe.
- `gemini -p "<prompt>" --yolo --skip-trust` ile prompt doğrudan argüman olarak verilir.
- Gemini yanıtı 5–30 sn sürebilir; UI spinner + Türkçe açıklama gösterir.
- CORS sadece `localhost:5173` için açık.
- TC kimlik regex'i parser'da merkezi — yeni format eklerken `tc_maskele()` zincirde.
