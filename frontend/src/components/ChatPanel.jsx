import React, { useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import { api } from '../api.js'
import FileStrip from './FileStrip.jsx'

const tarihBaslik = (tarih) => {
  if (!tarih) return null
  const d = new Date(tarih)
  const bugun = new Date()
  const dun = new Date(bugun - 86400000)
  if (d.toDateString() === bugun.toDateString()) return 'Bugün'
  if (d.toDateString() === dun.toDateString()) return 'Dün'
  return d.toLocaleDateString('tr-TR', { day: 'numeric', month: 'long', year: 'numeric' })
}

const saatFormat = (tarih) => {
  if (!tarih) return ''
  return new Date(tarih).toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' })
}

const DILEKCE_GRUPLARI = [
  {
    grup: "En Çok Kullanılan",
    turler: [
      "Dava Dilekçesi",
      "Cevap Dilekçesi",
      "Temyiz Dilekçesi",
      "İstinaf Dilekçesi",
      "İhtiyati Tedbir Talebi",
      "İhtiyati Haciz Talebi",
      "İcra Takibi Talebi",
    ],
  },
  {
    grup: "İtiraz & Savunma",
    turler: [
      "Yetki İtirazı",
      "Görev İtirazı",
      "Zamanaşımı İtirazı",
      "Hak Düşürücü Süre İtirazı",
      "Borca İtiraz",
      "İmzaya İtiraz",
      "Bilirkişi Raporuna İtiraz",
      "Keşif Talebine İtiraz",
      "Karşı Dava Dilekçesi",
    ],
  },
  {
    grup: "Talep & Beyan",
    turler: [
      "Talep Dilekçesi",
      "Beyan Dilekçesi",
      "Islah Dilekçesi",
      "Feragat Beyanı",
      "Kabul Beyanı",
      "Sulh Talebi",
      "Keşif Talebi",
      "Tanık Listesi",
      "Delil Listesi",
      "Belge İbraz Talebi",
      "Tensip Talebi",
      "Duruşma Erteleme Talebi",
      "Taraf Değişikliği Talebi",
    ],
  },
  {
    grup: "İcra & Takip",
    turler: [
      "İcra Takibine İtiraz",
      "Menfi Tespit Davası",
      "İstirdat Davası",
      "İcra İnkar Tazminatı Talebi",
      "Hacizin Kaldırılması Talebi",
      "İhalenin Feshi Talebi",
      "Sıra Cetveline İtiraz",
    ],
  },
  {
    grup: "Üst Yargı",
    turler: [
      "Karar Düzeltme Talebi",
      "Yargılamanın Yenilenmesi Talebi",
      "Anayasa Mahkemesi Bireysel Başvuru",
      "AİHM Başvurusu",
    ],
  },
  {
    grup: "Aile & Şahıs",
    turler: [
      "Boşanma Dava Dilekçesi",
      "Nafaka Talebi",
      "Velayet Değişikliği Talebi",
      "Babalık Davası",
      "Tanıma-Tenfiz Talebi",
    ],
  },
  {
    grup: "Ceza",
    turler: [
      "Şikâyet Dilekçesi",
      "Suç Duyurusu",
      "Müdafi Dilekçesi",
      "Tutukluluk İtirazı",
      "Tahliye Talebi",
      "CMK 141 Tazminat Talebi",
    ],
  },
  {
    grup: "İdare & Vergi",
    turler: [
      "İdari İtiraz Dilekçesi",
      "İdare Mahkemesi Dava Dilekçesi",
      "Yürütmeyi Durdurma Talebi",
      "Vergi İtiraz Dilekçesi",
      "Danıştay Temyiz Dilekçesi",
    ],
  },
]

const DILEKCE_TURLERI = DILEKCE_GRUPLARI.flatMap(g => g.turler)

export default function ChatPanel({ dava, onIctihatToggle, onToast, onDilekceOnizleme }) {
  const [sessionlar, setSessionlar] = useState([])
  const [aktifSession, setAktifSession] = useState(null)
  const [mesajlar, setMesajlar] = useState([])
  const [dosyalar, setDosyalar] = useState([])
  const [taslak, setTaslak] = useState("")
  const [bekleniyor, setBekleniyor] = useState(false)
  const [bekMesaj, setBekMesaj] = useState("")
  const [dilekceModal, setDilekceModal] = useState(false)
  const [dilekceSecim, setDilekceSecim] = useState(DILEKCE_TURLERI[0])
  const [dilekceOzelTur, setDilekceOzelTur] = useState("")
  const [dilekceEk, setDilekceEk] = useState("")
  const [dilekceIctihat, setDilekceIctihat] = useState(false)
  const listRef = useRef(null)

  // Dava değişince sessionları yükle
  useEffect(() => {
    if (!dava) return
    setSessionlar([])
    setAktifSession(null)
    setMesajlar([])
    setDosyalar([])
    yukleSessionlar(dava.id)
  }, [dava?.id])

  const yukleSessionlar = async (davaId) => {
    try {
      const [s, d] = await Promise.all([
        api.sessionlari(davaId),
        api.dosyalar(davaId),
      ])
      setDosyalar(d)
      if (s.length === 0) return
      setSessionlar(s)
      // Son sessiona git
      const son = s[s.length - 1]
      setAktifSession(son)
      await yukleMesajlar(davaId, son.id)
    } catch (err) {
      onToast(`Sessionlar yüklenemedi: ${err.message}`, 'err')
    }
  }

  const yukleMesajlar = async (davaId, sessionId) => {
    setMesajlar([])
    try {
      const g = await api.sohbetGecmisi(davaId, sessionId)
      setMesajlar(g.map(m => ({ rol: m.rol, icerik: m.icerik, tarih: m.tarih })))
    } catch (err) {
      onToast(`Mesajlar yüklenemedi: ${err.message}`, 'err')
    }
  }

  const yukleDosyalar = async () => {
    if (!dava) return
    const d = await api.dosyalar(dava.id)
    setDosyalar(d)
  }

  const sessionSec = async (session) => {
    if (aktifSession?.id === session.id || bekleniyor) return
    setAktifSession(session)
    await yukleMesajlar(dava.id, session.id)
  }

  const yeniSessionAc = async () => {
    if (bekleniyor) return
    try {
      const session = await api.yeniSession(dava.id)
      setSessionlar(s => [...s, session])
      setAktifSession(session)
      setMesajlar([])
    } catch (err) {
      onToast(`Yeni konuşma açılamadı: ${err.message}`, 'err')
    }
  }

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: 'smooth' })
  }, [mesajlar, bekleniyor])

  const gonder = async () => {
    const soru = taslak.trim()
    if (!soru || bekleniyor || !aktifSession) return
    const simdi = new Date().toISOString()
    setMesajlar(m => [...m, { rol: 'user', icerik: soru, tarih: simdi }])
    setTaslak("")
    setBekleniyor(true)
    setBekMesaj("Gemini yanıtlıyor...")
    try {
      const { yanit } = await api.sohbet(dava.id, soru, aktifSession.id)
      setMesajlar(m => [...m, { rol: 'assistant', icerik: yanit, tarih: new Date().toISOString() }])
    } catch (err) {
      onToast(`Hata: ${err.message}`, 'err')
      setMesajlar(m => m.slice(0, -1))
    } finally {
      setBekleniyor(false)
    }
  }

  const hizliEylem = async (tur) => {
    if (bekleniyor || !aktifSession) return
    const baslik = {
      ozet: 'Dava özeti',
      risk: 'Risk analizi',
      durusma: 'Duruşma hazırlığı',
      ictihat: 'İçtihat araştırması',
      belgeler: 'Belge analizi',
      kronoloji: 'Dava kronolojisi',
    }[tur]

    let tarih = null
    if (tur === 'durusma') {
      tarih = dava.sonraki_durusma || prompt("Duruşma tarihi (YYYY-MM-DD):")
      if (!tarih) return
    }

    const simdi = new Date().toISOString()
    setMesajlar(m => [...m, { rol: 'user', icerik: `[${baslik} istendi]`, tarih: simdi }])
    setBekleniyor(true)
    setBekMesaj(tur === 'ictihat'
      ? "Yargıtay kararları araştırılıyor (30sn'ye kadar sürebilir)..."
      : `${baslik} hazırlanıyor...`)
    try {
      let yanit
      if (tur === 'ozet') yanit = (await api.ozet(dava.id, aktifSession.id)).yanit
      else if (tur === 'risk') yanit = (await api.risk(dava.id, aktifSession.id)).yanit
      else if (tur === 'durusma') yanit = (await api.durusma(dava.id, tarih, aktifSession.id)).yanit
      else if (tur === 'ictihat') yanit = (await api.ictihat(dava.id, null, aktifSession.id)).yanit
      else if (tur === 'belgeler') yanit = (await api.evrakAnalizleri(dava.id)).markdown
      else if (tur === 'kronoloji') yanit = (await api.kronoloji(dava.id)).markdown
      setMesajlar(m => [...m, { rol: 'assistant', icerik: yanit, tarih: new Date().toISOString(), ictihat: tur === 'ictihat' }])
    } catch (err) {
      onToast(`Hata: ${err.message}`, 'err')
      setMesajlar(m => m.slice(0, -1))
    } finally {
      setBekleniyor(false)
    }
  }

  const dilekceOlustur = async () => {
    if (bekleniyor || !aktifSession) return
    const tur = dilekceOzelTur.trim() || dilekceSecim
    setDilekceModal(false)
    setDilekceOzelTur("")
    const simdi = new Date().toISOString()
    setMesajlar(m => [...m, { rol: 'user', icerik: `[Dilekçe oluşturuluyor — ${tur}]`, tarih: simdi }])
    setBekleniyor(true)
    setBekMesaj(dilekceIctihat
      ? `İçtihat araştırılıyor → ${tur} dilekçesi yazılıyor (2–4 dk sürebilir)...`
      : `${tur} dilekçesi yazılıyor...`)
    try {
      const { xml, dilekce_turu } = await api.dilekce(dava.id, tur, dilekceEk, aktifSession.id, dilekceIctihat)
      setMesajlar(m => [...m, {
        rol: 'assistant',
        icerik: `**${dilekce_turu}** dilekçesi oluşturuldu. Sağ panelden önizleyip düzenleyebilirsiniz.`,
        tarih: new Date().toISOString(),
      }])
      onDilekceOnizleme?.({ xml, dilekce_turu })
    } catch (err) {
      onToast(`Dilekçe hatası: ${err.message}`, 'err')
      setMesajlar(m => m.slice(0, -1))
    } finally {
      setBekleniyor(false)
      setDilekceEk("")
    }
  }

  const tusBasildi = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      gonder()
    }
  }

  return (
    <main className="main">
      <div className="main-header">
        <div className="main-title">
          <h2>{dava.mahkeme}</h2>
          <div className="main-title-sub">
            Dosya No: {dava.konu}
            {dava.sonraki_durusma && ` · Duruşma: ${dava.sonraki_durusma}`}
          </div>
        </div>
        <button className="btn ghost sm" onClick={onIctihatToggle}>İçtihat</button>
      </div>

      {/* Session sekmeleri */}
      <div className="session-bar">
        {sessionlar.map(s => (
          <button
            key={s.id}
            className={`session-tab${aktifSession?.id === s.id ? ' aktif' : ''}`}
            onClick={() => sessionSec(s)}
            title={s.baslik}
          >
            {s.baslik}
          </button>
        ))}
        <button className="session-yeni" onClick={yeniSessionAc} title="Yeni konuşma">
          + Yeni
        </button>
      </div>

      <div className="quick-bar">
        <button className="chip" onClick={() => hizliEylem('durusma')}>📅 Duruşma Hazırlığı</button>
        <button className="chip" onClick={() => hizliEylem('ozet')}>📝 Dava Özeti</button>
        <button className="chip" onClick={() => hizliEylem('risk')}>⚠️ Risk Analizi</button>
        <button className="chip" onClick={() => hizliEylem('ictihat')}>⚖️ İçtihat Araştır</button>
        <button className="chip" onClick={() => hizliEylem('belgeler')}>🧾 Belge Analizi</button>
        <button className="chip" onClick={() => hizliEylem('kronoloji')}>🗓️ Kronoloji</button>
        <button className="chip chip-gold" onClick={() => setDilekceModal(true)} disabled={bekleniyor || !aktifSession}>📄 Dilekçe Oluştur</button>
      </div>

      {dilekceModal && (
        <div className="modal-overlay" onClick={e => e.target === e.currentTarget && setDilekceModal(false)}>
          <div className="modal">
            <div className="modal-header">
              <h3>Dilekçe Oluştur</h3>
              <button className="modal-kapat" onClick={() => setDilekceModal(false)}>✕</button>
            </div>
            <div className="modal-body">
              <label className="modal-label">Dilekçe Türü</label>
              <select
                className="modal-select"
                value={dilekceSecim}
                onChange={e => { setDilekceSecim(e.target.value); setDilekceOzelTur("") }}
              >
                {DILEKCE_GRUPLARI.map(g => (
                  <optgroup key={g.grup} label={g.grup}>
                    {g.turler.map(t => <option key={t} value={t}>{t}</option>)}
                  </optgroup>
                ))}
              </select>

              <label className="modal-label" style={{ marginTop: 14 }}>
                Listede Yoksa Yaz
                <span className="modal-label-sub"> — seçimi geçersiz kılar</span>
              </label>
              <input
                className="modal-input"
                type="text"
                placeholder="örn. Yetki Belgesi, Vekaletname Bildirimi..."
                value={dilekceOzelTur}
                onChange={e => setDilekceOzelTur(e.target.value)}
              />

              <label className="modal-label" style={{ marginTop: 14 }}>
                Ek Talimat
                <span className="modal-label-sub"> — Gemini'ye özel yönlendirme</span>
              </label>
              <textarea
                className="modal-textarea"
                placeholder={`Dilekçeye özellikle eklemesini / vurgulamasını istediğiniz şeyleri yazın.\nörn: "Manevi tazminat talebini öne çıkar", "Faiz başlangıç tarihini kaza tarihinden hesapla", "Karşı vekalet ücreti talep et"`}
                value={dilekceEk}
                onChange={e => setDilekceEk(e.target.value)}
                rows={3}
              />

              <label className="modal-check" style={{ marginTop: 12 }}>
                <input
                  type="checkbox"
                  checked={dilekceIctihat}
                  onChange={e => setDilekceIctihat(e.target.checked)}
                />
                <span>Yargı MCP ile içtihat araştırıp dilekçeye ekle</span>
              </label>

              <div className="modal-hint">
                <strong style={{color:'var(--gold)'}}>Hızlı mod:</strong> Dava dosyasından doğrudan dilekçe yazar.<br/>
                <strong style={{color:'var(--gold)'}}>İçtihatlı mod:</strong> Önce kısa hukuki özet çıkarır, Yargıtay/Danıştay kararları arar, sonra dilekçeyi yazar.<br/>
                <span style={{color:'var(--muted)'}}>İçtihatlı mod 2–4 dakika sürebilir.</span>
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn ghost sm" onClick={() => setDilekceModal(false)}>İptal</button>
              <button className="btn sm gold" onClick={dilekceOlustur}>Oluştur ve Önizle</button>
            </div>
          </div>
        </div>
      )}

      <FileStrip davaId={dava.id} dosyalar={dosyalar} onYenile={yukleDosyalar} onToast={onToast} />

      <div className="chat-list" ref={listRef}>
        {mesajlar.length === 0 && !bekleniyor && (
          <div style={{ color: 'var(--muted)', textAlign: 'center', padding: 40 }}>
            {dosyalar.length === 0
              ? 'Önce dava dosyalarını yükleyin, sonra soru sorabilirsiniz.'
              : 'Hazır. Davanız hakkında soru sorabilir veya yukarıdaki hızlı eylemlerden birini seçebilirsiniz.'}
          </div>
        )}
        {mesajlar.map((m, i) => {
          const onceki = mesajlar[i - 1]
          const tarihDegisti = m.tarih && (
            !onceki?.tarih ||
            new Date(m.tarih).toDateString() !== new Date(onceki.tarih).toDateString()
          )
          return (
            <React.Fragment key={i}>
              {tarihDegisti && (
                <div className="date-sep">{tarihBaslik(m.tarih)}</div>
              )}
              <div className={`msg ${m.rol === 'user' ? 'user' : 'assistant'} ${m.ictihat ? 'ictihat' : ''}`}>
                {m.rol === 'user'
                  ? <div style={{ whiteSpace: 'pre-wrap' }}>{m.icerik}</div>
                  : <ReactMarkdown>{m.icerik}</ReactMarkdown>}
                {m.tarih && <div className="msg-time">{saatFormat(m.tarih)}</div>}
              </div>
            </React.Fragment>
          )
        })}
        {bekleniyor && (
          <div className="loading-msg">
            <span className="spinner" />
            <span>{bekMesaj}</span>
          </div>
        )}
      </div>

      <div className="composer">
        <textarea
          value={taslak}
          onChange={e => setTaslak(e.target.value)}
          onKeyDown={tusBasildi}
          placeholder="Davanızla ilgili bir soru yazın... (Enter = gönder, Shift+Enter = yeni satır)"
          disabled={bekleniyor || !aktifSession}
        />
        <div className="composer-actions">
          <span className="composer-hint">
            {dosyalar.length === 0 ? 'Dosya yüklemediniz — yanıtlar sınırlı olacak' : ''}
          </span>
          <button className="btn sm" onClick={gonder} disabled={bekleniyor || !taslak.trim() || !aktifSession}>
            Gönder
          </button>
        </div>
      </div>
    </main>
  )
}
