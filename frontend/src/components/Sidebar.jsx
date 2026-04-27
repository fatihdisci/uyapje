import React, { useState } from 'react'

export default function Sidebar({ davalar, aktifDava, secim, yarinki, sistem, onYeniDava, onYenile, onDavaSil }) {
  const [yeniAcik, setYeniAcik] = useState(false)
  const [form, setForm] = useState({ mahkeme: "", konu: "", taraf: "", sonraki_durusma: "" })

  const kaydet = async () => {
    if (!form.mahkeme || !form.konu) return
    const d = { ...form }
    if (!d.sonraki_durusma) d.sonraki_durusma = null
    await onYeniDava(d)
    setForm({ mahkeme: "", konu: "", taraf: "", sonraki_durusma: "" })
    setYeniAcik(false)
  }

  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <div className="brand">
          <div className="brand-logo">⚖</div>
          <div>
            <div className="brand-name">UYAP AI</div>
            <div className="brand-sub">Hukuk Asistanı</div>
          </div>
        </div>
      </div>

      {yarinki && yarinki.length > 0 && (
        <div className="alarm-banner">
          <span className="live-dot" />
          <span>Yarın {yarinki.length} duruşmanız var</span>
        </div>
      )}

      <div className="dava-list">
        {davalar.length === 0 && (
          <div style={{ color: 'var(--muted)', fontSize: 12, padding: 12, textAlign: 'center' }}>
            Henüz dava yok
          </div>
        )}
        {davalar.map(d => (
          <div
            key={d.id}
            className={`dava-card ${aktifDava?.id === d.id ? 'active' : ''}`}
            onClick={() => secim(d)}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div className="dava-card-no">#{d.id}</div>
              <span className="x-btn" title="Davayı sil" onClick={(e) => { e.stopPropagation(); onDavaSil(d.id); }}>✕</span>
            </div>
            <div className="dava-card-mahkeme">{d.mahkeme}</div>
            <div className="dava-card-konu">{d.konu}</div>
            <div className="dava-card-meta">
              <span className={`badge ${d.durum === 'Aktif' ? 'aktif' : ''}`}>{d.durum}</span>
              {d.sonraki_durusma && (
                <span className="dava-tarih">📅 {d.sonraki_durusma}</span>
              )}
            </div>
          </div>
        ))}
      </div>

      <div className="sidebar-actions">
        <button className="btn" onClick={() => setYeniAcik(true)}>+ Yeni Dava</button>
      </div>

      <div className="system-status">
        <div className="status-row">
          <span className={`status-dot ${sistem?.gemini_hazir ? 'ok' : 'warn'}`} />
          <span>Gemini CLI {sistem?.gemini_hazir ? '✓' : '— kurulu değil'}</span>
        </div>
        <div className="status-row">
          <span className={`status-dot ${sistem?.yargi_mcp_aktif ? 'ok' : 'warn'}`} />
          <span>Yargı MCP {sistem?.yargi_mcp_aktif ? '✓' : '— pasif'}</span>
        </div>
      </div>

      {yeniAcik && (
        <div className="modal-overlay" onClick={() => setYeniAcik(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <h3>Yeni Dava</h3>
            <div className="field">
              <label>Mahkeme</label>
              <input value={form.mahkeme} onChange={e => setForm({...form, mahkeme: e.target.value})}
                placeholder="örn. İstanbul 5. Asliye Hukuk Mahkemesi" />
            </div>
            <div className="field">
              <label>Konu</label>
              <input value={form.konu} onChange={e => setForm({...form, konu: e.target.value})}
                placeholder="örn. Kira tazminatı" />
            </div>
            <div className="field">
              <label>Taraflar</label>
              <input value={form.taraf} onChange={e => setForm({...form, taraf: e.target.value})}
                placeholder="örn. Ahmet Yılmaz / Mehmet Demir" />
            </div>
            <div className="field">
              <label>Sonraki Duruşma</label>
              <input type="date" value={form.sonraki_durusma}
                onChange={e => setForm({...form, sonraki_durusma: e.target.value})} />
            </div>
            <div className="modal-actions">
              <button className="btn ghost sm" onClick={() => setYeniAcik(false)}>İptal</button>
              <button className="btn sm" onClick={kaydet}>Kaydet</button>
            </div>
          </div>
        </div>
      )}
    </aside>
  )
}
