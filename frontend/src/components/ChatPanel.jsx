import React, { useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import { api } from '../api.js'
import FileStrip from './FileStrip.jsx'

export default function ChatPanel({ dava, onIctihatToggle, onToast }) {
  const [mesajlar, setMesajlar] = useState([])
  const [dosyalar, setDosyalar] = useState([])
  const [taslak, setTaslak] = useState("")
  const [bekleniyor, setBekleniyor] = useState(false)
  const [bekMesaj, setBekMesaj] = useState("")
  const listRef = useRef(null)

  const yukleDurumu = async () => {
    if (!dava) return
    const [g, d] = await Promise.all([
      api.sohbetGecmisi(dava.id),
      api.dosyalar(dava.id),
    ])
    setMesajlar(g.map(m => ({ rol: m.rol, icerik: m.icerik })))
    setDosyalar(d)
  }

  useEffect(() => { yukleDurumu() }, [dava?.id])

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: 'smooth' })
  }, [mesajlar, bekleniyor])

  const gonder = async () => {
    const soru = taslak.trim()
    if (!soru || bekleniyor) return
    setMesajlar(m => [...m, { rol: 'user', icerik: soru }])
    setTaslak("")
    setBekleniyor(true)
    setBekMesaj("Gemini yanıtlıyor...")
    try {
      const { yanit } = await api.sohbet(dava.id, soru)
      setMesajlar(m => [...m, { rol: 'assistant', icerik: yanit }])
    } catch (err) {
      onToast(`Hata: ${err.message}`, 'err')
    } finally {
      setBekleniyor(false)
    }
  }

  const hizliEylem = async (tur) => {
    if (bekleniyor) return
    const baslik = { ozet: 'Dava özeti', risk: 'Risk analizi', durusma: 'Duruşma hazırlığı', ictihat: 'İçtihat araştırması' }[tur]

    let tarih = null
    if (tur === 'durusma') {
      tarih = dava.sonraki_durusma || prompt("Duruşma tarihi (YYYY-MM-DD):")
      if (!tarih) return
    }

    setMesajlar(m => [...m, { rol: 'user', icerik: `[${baslik} istendi]` }])
    setBekleniyor(true)
    setBekMesaj(tur === 'ictihat'
      ? "Yargıtay kararları araştırılıyor (30sn'ye kadar sürebilir)..."
      : `${baslik} hazırlanıyor...`)
    try {
      let yanit
      if (tur === 'ozet') yanit = (await api.ozet(dava.id)).yanit
      else if (tur === 'risk') yanit = (await api.risk(dava.id)).yanit
      else if (tur === 'durusma') yanit = (await api.durusma(dava.id, tarih)).yanit
      else if (tur === 'ictihat') yanit = (await api.ictihat(dava.id, null)).yanit
      setMesajlar(m => [...m, { rol: 'assistant', icerik: yanit, ictihat: tur === 'ictihat' }])
    } catch (err) {
      onToast(`Hata: ${err.message}`, 'err')
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

      <div className="quick-bar">
        <button className="chip" onClick={() => hizliEylem('durusma')}>📅 Duruşma Hazırlığı</button>
        <button className="chip" onClick={() => hizliEylem('ozet')}>📝 Dava Özeti</button>
        <button className="chip" onClick={() => hizliEylem('risk')}>⚠️ Risk Analizi</button>
        <button className="chip" onClick={() => hizliEylem('ictihat')}>⚖️ İçtihat Araştır</button>
      </div>

      <FileStrip davaId={dava.id} dosyalar={dosyalar} onYenile={yukleDurumu} onToast={onToast} />

      <div className="chat-list" ref={listRef}>
        {mesajlar.length === 0 && !bekleniyor && (
          <div style={{ color: 'var(--muted)', textAlign: 'center', padding: 40 }}>
            {dosyalar.length === 0
              ? 'Önce dava dosyalarını yükleyin, sonra soru sorabilirsiniz.'
              : 'Hazır. Davanız hakkında soru sorabilir veya yukarıdaki hızlı eylemlerden birini seçebilirsiniz.'}
          </div>
        )}
        {mesajlar.map((m, i) => (
          <div key={i} className={`msg ${m.rol === 'user' ? 'user' : 'assistant'} ${m.ictihat ? 'ictihat' : ''}`}>
            {m.rol === 'user'
              ? <div style={{ whiteSpace: 'pre-wrap' }}>{m.icerik}</div>
              : <ReactMarkdown>{m.icerik}</ReactMarkdown>}
          </div>
        ))}
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
          disabled={bekleniyor}
        />
        <div className="composer-actions">
          <span className="composer-hint">
            {dosyalar.length > 0 ? `${dosyalar.length} dosya bağlam olarak kullanılıyor` : 'Dosya yüklemediniz — yanıtlar sınırlı olacak'}
          </span>
          <button className="btn sm" onClick={gonder} disabled={bekleniyor || !taslak.trim()}>
            Gönder
          </button>
        </div>
      </div>
    </main>
  )
}
