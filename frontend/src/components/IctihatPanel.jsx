import React, { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import { api } from '../api.js'

export default function IctihatPanel({ dava, onKapat, onToast }) {
  const [sorgu, setSorgu] = useState("")
  const [sonuc, setSonuc] = useState("")
  const [bekleniyor, setBekleniyor] = useState(false)

  const ara = async () => {
    if (!sorgu.trim() || bekleniyor) return
    setBekleniyor(true)
    setSonuc("")
    try {
      const { yanit } = await api.ictihat(dava.id, sorgu.trim())
      setSonuc(yanit)
    } catch (err) {
      onToast(`İçtihat hatası: ${err.message}`, 'err')
    } finally {
      setBekleniyor(false)
    }
  }

  return (
    <aside className="ictihat-panel">
      <header>
        <h3>İçtihat Araştırma</h3>
        <button className="btn ghost sm" onClick={onKapat}>✕</button>
      </header>
      <div className="ictihat-search">
        <input
          value={sorgu}
          onChange={e => setSorgu(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && ara()}
          placeholder="örn. kira tazminatı emsal Yargıtay kararları"
        />
        <button className="btn sm" onClick={ara} disabled={bekleniyor}>Ara</button>
      </div>
      <div className="ictihat-result">
        {bekleniyor && (
          <div className="loading-msg">
            <span className="spinner" />
            <span>Yargıtay araştırılıyor...</span>
          </div>
        )}
        {!bekleniyor && !sonuc && (
          <div style={{ color: 'var(--muted)', fontSize: 12 }}>
            Yargı MCP tool'ları üzerinden Yargıtay, Danıştay, AYM ve emsal kararları araştırılır.
            Yanıt 10-30 saniye sürebilir.
          </div>
        )}
        {sonuc && <ReactMarkdown>{sonuc}</ReactMarkdown>}
      </div>
    </aside>
  )
}
