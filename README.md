# UYAP Hukuk Asistanı

Solo avukat için lokal hukuk asistanı. UYAP dosyalarını (PDF/TIFF/UDF/ZIP/DOCX) okuyup analiz eder, Gemini CLI üzerinden duruşma hazırlığı, dava özeti, risk analizi ve Yargıtay içtihat araştırması yapar. UDF üretimi/okuması `udf-cli` (saidsurucu/udf-cli) ile yapılır.

**Hiçbir yere veri gönderilmez.** Gemini, bilgisayarınızda kurulu `gemini` CLI aracılığıyla çalışır. API key yoktur. Tüm dosyalar, sohbet geçmişi ve cache lokal SQLite'ta tutulur.

---

## Mimari (kuş bakışı)

```
[Tarayıcı: React UI :5173]
        ↕ HTTP (JSON)
[FastAPI :8000]  ──→  SQLite (uyap.db)        ← tüm dava/dosya/sohbet burada
        ↓
   subprocess
        ↓
[gemini CLI]  ──MCP──→  [Yargı MCP (uvx)]    ← Yargıtay/Danıştay araması
        ↓                                         (Gemini gerek görürse otomatik)
   Google AI Pro hesabı (auth bir kere)

[udf-cli (Node)]  ← UDF üretimi/okuması için subprocess
```

İki temel ilke:
- **API key yok.** Gemini, sistemde yüklü `gemini` CLI'a `subprocess` ile prompt geçirilerek çağrılıyor — auth Google AI Pro üyeliğiyle bir defa yapılır.
- **Her şey lokal.** SQLite veritabanı, dosya metinleri, sohbet — hepsi senin makinende. Sadece Gemini'ye gönderilen prompt internete çıkıyor.

---

## Kurulum

1. **Gemini CLI** — `npm install -g @google/gemini-cli` ardından `gemini auth login` (Google AI Pro hesabıyla)
2. **udf-cli** — `npm install -g udf-cli` (UDF üretimi/okuması için zorunlu; saidsurucu/udf-cli)
3. **Python bağımlılıkları** — `pip install -r backend/requirements.txt`
4. **Frontend** — `cd frontend && npm install`
5. **(Opsiyonel) Yargı MCP** — `~/.gemini/settings.json`:
   ```json
   { "mcpServers": { "yargi_mcp": { "command": "uvx", "args": ["yargi-mcp"] } } }
   ```
6. **(Opsiyonel) Tesseract-OCR** — `tur` dili paketiyle (TIFF dosyaları için)
7. `start.bat` ile çalıştır → http://localhost:5173

---

## 1. Dava oluşturma

Sol panelden **"+ Yeni Dava"** → ad/mahkeme/konu/taraf girersin.

**Arkada:**
- `POST /api/dava` (`backend/main.py`) — SQLite'a `davalar` tablosuna satır eklenir. `dava_id` üretilir.
- AI'a hiçbir şey gitmez. Sadece kayıt.

---

## 2. Evrak yükleme

Davayı seç → dosya sürükle-bırak veya **"+ Dosya Yükle"**. PDF / TIFF / UDF / ZIP / DOCX kabul ediliyor.

**Arkada:** `POST /api/dava/{id}/dosya` çağrılır, sonra şunlar olur:

### a) Parse — `backend/parser.py`
Dosya uzantısına göre uygun parser çalışır:
- **PDF** → `pdfplumber` ile sayfa sayfa metin
- **TIFF** → her frame için Tesseract OCR (`tur` dili)
- **UDF** → önce `udf-cli udf2md` (zengin Markdown — bold/başlık korunur), olmazsa ZIP içindeki `content.xml`'in CDATA'sından düz metin
- **ZIP** → içindeki her dosya için aynı parser zinciri tekrar çağrılır
- **DOCX** → python-docx ile paragraflar

### b) TC kimlik maskeleme
`parser.py` → `tc_maskele()` — 11 haneli TC sayılarını regex ile yakalayıp `[KIMLIK GIZLENDI]` ile değiştirir. **Bu Gemini'ye gönderilmeden önce uygulanır.**

### c) Deterministik analiz — `backend/evrak_zeka.py`
AI çağırmadan, regex ve anahtar kelimelerle:
- **Evrak türü** ("Bilirkişi Raporu", "Cevap Dilekçesi" vs.) — anahtar kelime puanlaması
- **Tarihler** — 10 taneye kadar
- **Esas/Karar no'ları**
- **Hukuki dayanaklar** (HMK m.X, TBK m.X gibi)
- **Taraflar** (DAVACI/DAVALI/VEKİLİ satırlarından)
- **Talep/delil cümleleri** (anahtar kelime eşleşmesi)
- **Kısa özet** (ilk anlamlı 3 satır)

Bu hızlıdır (milisaniye), sonradan AI promptlarına bağlam olarak verilir.

### d) Kayıt
Hepsi `dosyalar` tablosuna yazılır: dosya adı, parse edilmiş tam metin, analiz JSON'u. **Bir daha parse edilmez** — SQLite'tan okunur.

> **Hiçbir AI çağrısı yapılmaz bu aşamada.** Yükleme dakikalar değil saniyeler sürer (TIFF OCR hariç).

---

## 3. Sohbet (mesaj kutusu)

Sağdaki sohbet paneline soru yazıp Enter.

**Arkada:** `POST /api/dava/{id}/sohbet` → `gemini_cli.py` → `sohbet()`.

### Prompt nasıl oluşturuluyor:
```
[SISTEM PROMPTU]              ← promptlar.py: "Sen Türk hukuku uzmanı..."
[TARAF BİLGİSİ]               ← Davada "müvekkilimiz davacı" gibi yön ver
DAVA DOSYASI:
  [tüm yüklenmiş dosyaların metinleri birleştirilmiş, max 500.000 karakter]
SOHBET GEÇMİŞİ:
  [son ~20.000 karakter, en yeni mesajdan geriye doğru]
AVUKATIN SORUSU: ...
YANIT:
```

### Subprocess çağrısı:
```
gemini -p " " --yolo --skip-trust       ← prompt stdin'den geçer
```
- `--yolo`: Gemini'nin onay sormadan tool çağırmasına izin ver
- `--skip-trust`: workspace güven kontrolünü atla
- 270 saniye timeout (`GEMINI_TIMEOUT`)
- stdout'tan dönen metin doğrudan yanıt

### Sohbet kaydı:
Hem soru hem yanıt SQLite'taki `sohbet_gecmisi` tablosuna yazılır (`session_id` ile gruplu). Yeni dava açınca yeni session başlar; eski sessionlar sol panelde listelenir.

---

## 4. Hızlı eylem butonları

Üst toolbar'daki tek-tıkla işlevler. Her biri **kendi promptu**yla `gemini`'yi tetikler.

### a) **Özet** → `GET /api/dava/{id}/ozet`
`OZET_PROMPTU`: "Taraflar, talep, aşama, kritik meseleler, güçlü/zayıf noktalar."

### b) **Risk Analizi** → `GET /api/dava/{id}/risk`
"Güçlü Noktalar / Zayıf Noktalar / Öneriler / Olası Sonuç Senaryoları" başlıklarıyla yanıt.

### c) **Duruşma Hazırlığı** → `POST /api/dava/{id}/durusma`
Tarih sorulur. "Duruşmada Söylenecekler / Dikkat Edilecekler / Yanınıza Alacağınız Belgeler / İlgili Yargıtay Kararları" başlıklarıyla yanıt.
- **Yargıtay kararları** kısmında Gemini Yargı MCP'yi otomatik çağırır (gerek görürse).

### d) **İçtihat Araştırması** → `POST /api/dava/{id}/ictihat`
Sorgu vermesen tüm dava metniyle, versen sadece o sorguyla Yargı MCP'ye gider.

**Burada önemli:** Yargı MCP backend'de değil, **Gemini CLI'ın içinde** kayıtlı (`~/.gemini/settings.json`). Yani:
1. Backend prompt'u Gemini'ye verir.
2. Gemini "bu soru için Yargıtay aramam lazım" diye karar verir.
3. Gemini, MCP üzerinden `search_bedesten_unified`, `get_emsal_document_markdown` gibi araçları otomatik çağırır.
4. Bulduğu kararları metne katıp döndürür.

Backend'in Yargı MCP'den haberi yok — sadece Gemini'nin döndürdüğü metni alır.

Sonuç `ictihat_cache` tablosuna cache'lenir; aynı sorgu tekrar sorulursa AI'a gitmez.

---

## 5. Dilekçe oluşturma (en karmaşık akış)

Toolbar'daki **"Dilekçe Oluştur"** → tür seç (Cevap Dilekçesi, Bilirkişiye İtiraz vs.), opsiyonel **"İçtihat ekle"** kutusu, **"Oluştur"**.

**Arkada:** `POST /api/dava/{id}/dilekce` → `gemini_cli.py` → `dilekce_olustur()`

### Akış:

**Eğer "İçtihat ekle" işaretliyse 3 adım:**

1. **Hukuki özet çıkar**
   - Gemini'ye dava metni verilir → "Bu dava için Yargıtay aramayı yönlendirecek 10-15 cümle hukuki özet çıkar."
   - Sebep: Tüm dava metniyle MCP araması yapmak hem yavaş hem alakasız sonuç verir; özet daha keskin.

2. **İçtihat ara**
   - "Bu özet için 3-5 ilgili Yargıtay kararı bul (karar no, daire, tarih, tek cümle özet)."
   - Gemini Yargı MCP araçlarını otomatik kullanır.

3. **Ana dilekçeyi yaz**

**İçtihat işaretsizse direkt 3. adıma geçilir.**

### Dilekçe XML promptu — `promptlar.py` `DILEKCE_PROMPTU`

Gemini'ye **özel bir XML şeması** üretmesi söylenir:
```xml
<dilekce>
  <basliklar><mahkeme_adi>...MAHKEMESİNE</mahkeme_adi></basliklar>
  <taraflar>
    <davaci_bilgi>...</davaci_bilgi>
    <davali_bilgi>...</davali_bilgi>
    <vekil_bilgi>Av. Fatih Dişçi</vekil_bilgi>
  </taraflar>
  <konu_metin>...</konu_metin>
  <aciklamalar><madde>...</madde>...</aciklamalar>
  <hukuki_dayanak>...</hukuki_dayanak>
  <sonuc><madde>...</madde>...</sonuc>
  <imza><tarih_yer>...</tarih_yer><unvan>...</unvan></imza>
</dilekce>
```

Neden XML? — Frontend bu yapılandırılmış formatı parse edip **alanları tek tek edit etmene** izin veriyor. Düz metin olsa düzenlemek zor olurdu.

XML stringi backend'den frontend'e döner.

### Dilekçe Önizleme paneli — `DilekcePreview.jsx`

Açılan sağ panelde:
- Mahkeme başlığı, esas no, taraflar, konu, açıklamalar, hukuki dayanak, sonuç, imza — **her biri tıklanabilir/yazılabilir**.
- "+ Madde Ekle" / "× sil" butonları her listede.
- A4 görünümünde gerçek dilekçe formatı gibi.

Hiçbir AI çağrısı yok burada — sadece local edit.

### **⬇ UDF İndir** butonu

`POST /api/dava/{id}/dilekce-indir` çağrılır. Backend'de `xml_to_udf()` çalışır → `backend/udf_olustur.py`:

1. **XML parse edilir** (Gemini'nin şeması)
2. **Semantik HTML'e çevrilir** — etiketler `<strong><u>...</u></strong>`, paragraflar `<p style="text-align:justify">`, sağ-alt imza `text-align:right` vs.
3. **udf-cli subprocess çağrılır:**
   ```
   udf-cli html2udf -            ← stdin'den HTML
   ```
   stdout'tan UDF binary döner.
4. Browser'a `application/octet-stream` olarak indirilir, dosya adı `dilekce_<tür>_<tarih>.udf`.

Bu UDF dosyası UYAP'a doğrudan yüklenebilir — Java ZipOutputStream uyumlu format, udf-cli garanti ediyor.

---

## 6. Dosya bağlam seçimi (FileStrip)

Üstteki dosya şeridinde **her dosyanın yanında onay kutusu** var. İşaretlersen sadece o dosyalar Gemini'ye gönderilir (büyük davalarda gerekli — context limiti var).

İşaretlemezsen tüm dosyalar dahil edilir (max 500.000 karakter).

---

## 7. Cache mekanizmaları

Aynı işi tekrar AI'a yaptırmamak için:
- **Sohbet özeti cache** — uzun sohbet geçmişleri Gemini'ye 3-5 cümlelik özetle gider
- **İçtihat cache** (`ictihat_cache` tablosu) — aynı sorgu için 24 saat boyunca kayıtlı sonuç
- **Parse cache** — dosyalar SQLite'ta, asla 2 kez parse edilmez

---

## 8. Persistence (kalıcılık)

Sistem kapansa bile:
- `uyap.db` (SQLite) — dava, dosya metni, sohbetler, cache hep orada
- `data/sessions/<session_id>.json` — son durum dökümleri (debug için)
- Tarayıcıyı kapatıp açtığında son aktif session geri yüklenir.

---

## Bir soru sorduğunda olan zincir (örnek)

**"Bilirkişiye karşı itirazımız hangi noktalara odaklanmalı?"** yazdın. Şu olur:

1. Frontend → `POST /sohbet` (~20 ms)
2. Backend SQLite'tan dava metnini çeker (~5 ms)
3. Sohbet geçmişi formatlanır (~1 ms)
4. Prompt birleştirilir → Gemini CLI'a `subprocess.run` (~10–30 sn) ⏳
   - Gemini Google sunucusuna gider, gerekirse Yargı MCP'yi çağırır
5. Yanıt dönen metin SQLite'a yazılır (~5 ms)
6. Frontend yanıtı render eder (Markdown → HTML)

Yani **gecikmenin %99'u Gemini'nin kendisi** — backend hızlı, sadece postacı.

---

## Klasör Yapısı

```
backend/
  main.py         FastAPI uygulaması, tüm endpointler
  parser.py       PDF/TIFF/UDF/ZIP/DOCX → metin
  gemini_cli.py   Gemini subprocess wrapper (stdin yoluyla)
  udf_olustur.py  XML → HTML → udf-cli html2udf wrapper
  evrak_zeka.py   Deterministik evrak analizi (regex/anahtar kelime)
  database.py     SQLite CRUD
  promptlar.py    Sistem promptları
  requirements.txt
frontend/
  src/
    App.jsx, main.jsx, api.js, styles.css
    components/
      Sidebar.jsx, ChatPanel.jsx, FileStrip.jsx,
      IctihatPanel.jsx, DilekcePreview.jsx
start.bat
.env  (UYAP_DIZIN, DB_YOL, GEMINI_TIMEOUT)
```

---

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
POST /api/dava/{id}/dilekce    { dilekce_turu, ictihat_ekle } → XML
POST /api/dava/{id}/dilekce-indir  { xml_icerik } → UDF binary
```

---

## Geliştirme Notları

- Tüm UI Türkçe.
- `gemini -p " " --yolo --skip-trust` ile prompt stdin üzerinden verilir.
- Gemini yanıtı 5–30 sn sürebilir; UI spinner + Türkçe açıklama gösterir.
- CORS sadece `localhost:5173` için açık.
- TC kimlik regex'i parser'da merkezi — yeni format eklerken `tc_maskele()` zincirde.
- UDF üretimi `udf-cli` (Node) subprocess'ine bağlı; sistem genelinde `npm install -g udf-cli` yapılmış olmalı.
