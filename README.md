# UYAP Hukuk Asistanı

Solo avukat için yerel çalışan yapay zeka asistanı. UYAP'tan indirilen dava dosyalarını (PDF, TIFF, UDF, ZIP, DOCX) okur; Gemini üzerinden dava özeti, risk analizi, duruşma hazırlığı ve Yargıtay içtihat araştırması yapar.

**Hiçbir yere veri gönderilmez.** Gemini, bilgisayarınızda kurulu `gemini` CLI aracılığıyla çalışır. API key yoktur.

---

## Genel Akış

```
Tarayıcı (React)  →  FastAPI (8000)  →  gemini CLI  →  Gemini modeli
                          ↓
                      SQLite (uyap.db)
```

1. Dosyayı yüklersiniz → backend metne çevirir → SQLite'a yazar
2. Hangi dosyaların bağlama gireceğini siz seçersiniz (● / ○ toggle)
3. Soru sorduğunuzda veya analiz istediğinizde yalnızca seçili dosyalar Gemini'ye gider

---

## Kurulum

### Gereksinimler

| Araç | Versiyon | Not |
|---|---|---|
| Python | 3.11+ | |
| Node.js | 18+ | |
| Gemini CLI | son sürüm | `npm install -g @google/gemini-cli` |
| Tesseract OCR | isteğe bağlı | Yalnızca TIFF dosyaları için |

### Adımlar

```bash
# 1. Gemini CLI kurulumu ve giriş
npm install -g @google/gemini-cli
gemini auth login

# 2. Python bağımlılıkları
cd backend
pip install -r requirements.txt

# 3. Frontend bağımlılıkları
cd ../frontend
npm install

# 4. (İsteğe bağlı) Yargı MCP — içtihat araştırması için
# ~/.gemini/settings.json dosyasına ekleyin:
{
  "mcpServers": {
    "yargi_mcp": { "command": "uvx", "args": ["yargi-mcp"] }
  }
}

# 5. Çalıştır
# Windows:
start.bat
# Manuel:
cd backend && uvicorn main:app --reload &
cd frontend && npm run dev
```

Uygulama: **http://localhost:5173**

---

## Yapılandırma (.env)

Proje kökünde `.env` dosyası oluşturabilirsiniz:

```env
# Veritabanı yolu (varsayılan: ./backend/uyap.db)
DB_YOL=./uyap.db

# Gemini CLI zaman aşımı saniye cinsinden (varsayılan: 180)
GEMINI_TIMEOUT=180

# Gemini'ye gönderilecek maksimum karakter sayısı (varsayılan: 500000)
# Gemini 1.5/2.0 ~1M token ≈ 3-4M karakter kapasitesi var, 500k güvenli üst limit
GEMINI_MAX_METIN=500000

# UYAP dosya klasörü (opsiyonel, yedek yol)
UYAP_DIZIN=./dosyalar
```

---

## Özellikler

### Dava Yönetimi
- Dava oluşturma: mahkeme adı, dosya no, müvekkil sıfatı (Davacı / Davalı / Sanık vb.), sonraki duruşma tarihi
- Yarınki duruşmalar sol panelde kırmızı banner ile gösterilir
- Dava silme (tüm dosya ve sohbet geçmişiyle birlikte)

### Dosya Yükleme ve Bağlam Seçimi
- Desteklenen formatlar: **PDF, TIFF/TIF, UDF, ZIP, DOCX**
- TIFF dosyaları Tesseract OCR ile metne çevrilir (Türkçe dil paketi gerekir)
- UDF ve ZIP içindeki PDF'ler ve XML'ler de ayrıştırılır
- **TC kimlik numaraları otomatik maskelenir** (`[KIMLIK GIZLENDI]`)

#### Bağlam Toggle (● / ○)
Her dosyanın solundaki simgeye tıklayarak o dosyayı yapay zeka bağlamına ekleyip çıkarabilirsiniz:
- **●** (yeşil) → Bağlamda, Gemini bu dosyayı görür
- **○** (gri) → Bağlamda değil, Gemini bu dosyayı görmez
- Seçim veritabanına kaydedilir, sayfa yenilense de korunur
- Sağ üstteki `X / N bağlamda` sayacı anlık durumu gösterir
- Hiçbir dosya seçilmezse yapay zeka işlevleri hata verir

> **Neden bu özellik?** Kalabalık davalarda dekontlar, yazışmalar, tebligatlar gibi bağlam için gerekmeyen dosyalar Gemini'ye gönderilmez; yalnızca dilekçeler, kararlar, duruşma tutanakları gibi önemli evraklar seçilir. Bu hem yanıt kalitesini artırır hem de zaman kazandırır.

### Yapay Zeka İşlevleri

| İşlev | Tetikleyici | Açıklama |
|---|---|---|
| **Sohbet** | Metin yazıp Enter | Seçili dosyalar bağlamında serbest soru-cevap |
| **Dava Özeti** | Hızlı eylem butonu | Taraflar, talep, aşama, kritik meseleler, güçlü/zayıf noktalar |
| **Risk Analizi** | Hızlı eylem butonu | Güçlü/zayıf noktalar, öneriler, olası sonuç senaryoları |
| **Duruşma Hazırlığı** | Hızlı eylem butonu | Duruşmada söylenecekler, dikkat edilecekler, yanınıza alacağınız belgeler |
| **İçtihat Araştırması** | Hızlı eylem butonu veya İçtihat paneli | Yargı MCP üzerinden Yargıtay/Danıştay kararları |

Tüm yanıtlar **Türkçe** ve Markdown formatında gelir. Müvekkil sıfatı (Davacı/Davalı vb.) ayarlandıysa Gemini otomatik olarak o tarafın lehine analiz yapar.

### İçtihat Araştırması
Sağ üstteki **İçtihat** butonu ile yan panel açılır. İki mod:
- **Otomatik:** Dava dosyasından temel hukuki konuları çıkarır, Yargı MCP ile ilgili kararları arar
- **Manuel:** Arama kutusuna kendi sorgunuzu yazarsınız (`örn. kira tazminatı emsal Yargıtay kararları`)

Yargı MCP kurulu değilse içtihat araştırması çalışmaz ama diğer özellikler etkilenmez.

---

## Veritabanı Yapısı

SQLite (`uyap.db`) — tüm veri yerel:

```
davalar
  id, mahkeme, konu, taraf, durum, sonraki_durusma, olusturma_tarihi

dosyalar
  id, dava_id, dosya_adi, format, metin (parse edilmiş), meta, yukleme_tarihi, baglamda

sohbet_gecmisi
  id, dava_id, rol (user/assistant), icerik, tarih

ictihat_cache
  id, dava_id, sorgu, sonuc, tarih
```

---

## API Endpoint'leri

```
GET  /api/sistem/durum              Gemini CLI ve Yargı MCP durumu
GET  /api/davalar                   Tüm davaları listele
POST /api/dava                      Yeni dava oluştur
GET  /api/dava/{id}                 Dava detayı
PATCH /api/dava/{id}                Dava güncelle
DELETE /api/dava/{id}               Dava sil
GET  /api/yarinki-durusmalar        Yarın duruşması olan davalar

POST /api/dava/{id}/dosya           Dosya yükle ve parse et
GET  /api/dava/{id}/dosyalar        Dava dosyalarını listele
DELETE /api/dosya/{dosya_id}        Dosya sil
PATCH /api/dosya/{dosya_id}/baglamda  Bağlam seçimini güncelle { "baglamda": 0 | 1 }

POST /api/dava/{id}/sohbet          { "soru": "..." } → { "yanit": "..." }
GET  /api/dava/{id}/sohbet          Sohbet geçmişi
POST /api/dava/{id}/durusma         { "tarih": "YYYY-MM-DD" } → hazırlık notu
GET  /api/dava/{id}/ozet            Dava özeti
GET  /api/dava/{id}/risk            Risk analizi
POST /api/dava/{id}/ictihat         { "sorgu": "..." | null } → içtihat araştırması
```

---

## Teknik Notlar

### Gemini Entegrasyonu
Gemini, `subprocess` ile `gemini -p " " --yolo --skip-trust` komutu çalıştırılarak ve gerçek prompt stdin üzerinden iletilerek kullanılır. Bu yaklaşımla:
- API key gerekmez — Google AI Pro üyeliği yeterli
- Komut satırı argüman uzunluk sınırı aşılmaz (büyük dava dosyaları için kritik)
- `asyncio.to_thread` ile asenkron çalışır, FastAPI bloklanmaz

### Bağlam Cache'i
Seçili dosyaların metni her istekte DB'den yeniden birleştirilmez. Seçili dosya ID'lerinin `frozenset`'i değişmediği sürece önceki birleşik metin belleğe önbelleklenir. Cache şu durumlarda otomatik temizlenir:
- Yeni dosya yüklendiğinde
- Dosya silindiğinde
- Bağlam toggle değiştiğinde

### Güvenlik
- TC kimlik numaraları (`[1-9][0-9]{10}`) parse aşamasında maskelenir
- `dava_guncelle()` SQL injection'a karşı kolon adı whitelist'i kullanır
- CORS yalnızca `localhost:5173` için açık

---

## Klasör Yapısı

```
uyapje/
├── backend/
│   ├── main.py          FastAPI — tüm endpoint'ler, in-memory cache
│   ├── database.py      SQLite CRUD katmanı
│   ├── gemini_cli.py    Gemini subprocess wrapper
│   ├── parser.py        PDF/TIFF/UDF/ZIP/DOCX → düz metin
│   ├── promptlar.py     Sistem ve görev promptları
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── App.jsx
│       ├── api.js
│       ├── styles.css
│       └── components/
│           ├── Sidebar.jsx       Dava listesi ve yeni dava formu
│           ├── ChatPanel.jsx     Ana sohbet ekranı ve hızlı eylemler
│           ├── FileStrip.jsx     Dosya yükleme ve bağlam seçimi
│           └── IctihatPanel.jsx  İçtihat araştırma paneli
├── start.bat
├── .env
└── README.md
```

---

## Sık Karşılaşılan Sorunlar

**"Gemini CLI bulunamadı"**
→ `npm install -g @google/gemini-cli` çalıştırın, sonra `gemini auth login`

**"Bağlama eklenmiş dosya yok"**
→ Dosya şeridindeki ○ simgesine tıklayarak en az bir dosyayı seçin (● yapın)

**TIFF dosyası boş metin**
→ Tesseract kurulu değil. `apt install tesseract-ocr tesseract-ocr-tur` (Linux) veya Tesseract Windows installer

**Gemini çok yavaş / zaman aşımı**
→ `.env` dosyasına `GEMINI_TIMEOUT=300` ekleyin. Çok büyük dosyalarda `GEMINI_MAX_METIN=200000` ile limiti düşürebilirsiniz.

**"İçtihat araştırması çalışmıyor"**
→ Yargı MCP kurulumu gerekli. `~/.gemini/settings.json` dosyasını kontrol edin.
