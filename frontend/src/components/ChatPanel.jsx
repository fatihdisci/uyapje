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

export default function ChatPanel({ dava, onIctihatToggle, onToast }) {
  const [sessionlar, setSessionlar] = useState([])
  const [aktifSession, setAktifSession] = useState(null)
  const [mesajlar, setMesajlar] = useState([])
  const [dosyalar, setDosyalar] = useState([])
  const [taslak, setTaslak] = useState("")
  const [bekleniyor, setBekleniyor] = useState(false)
  const [bekMesaj, setBekMesaj] = useState("")
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
    const baslik = { ozet: 'Dava özeti', risk: 'Risk analizi', durusma: 'Duruşma hazırlığı', ictihat: 'İçtihat araştırması' }[tur]

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
      setMesajlar(m => [...m, { rol: 'assistant', icerik: yanit, tarih: new Date().toISOString(), ictihat: tur === 'ictihat' }])
    } catch (err) {
      onToast(`Hata: ${err.message}`, 'err')
      setMesajlar(m => m.slice(0, -1))
    } finally {
      setBekleniyor(false)
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
      </div>

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
            {dosyalar.length > 0 ? `${dosyalar.filter(d => d.baglamda).length} / ${dosyalar.length} dosya bağlamda` : 'Dosya yüklemediniz — yanıtlar sınırlı olacak'}
          </span>
          <button className="btn sm" onClick={gonder} disabled={bekleniyor || !taslak.trim() || !aktifSession}>
            Gönder
          </button>
        </div>
      </div>
    </main>
  )
}
