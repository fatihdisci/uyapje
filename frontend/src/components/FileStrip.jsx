import React, { useRef, useState } from 'react'
import { api } from '../api.js'

const FORMAT_ICON = { pdf: '📕', tiff: '🖼', tif: '🖼', udf: '📋', zip: '🗜', docx: '📝' }

export default function FileStrip({ davaId, dosyalar, onYenile, onToast }) {
  const inpRef = useRef(null)
  const [yukleniyor, setYukleniyor] = useState(false)
  const [silIslemi, setSilIslemi] = useState(null)

  const yukle = async (e) => {
    const files = [...(e.target.files || [])]
    if (!files.length) return
    setYukleniyor(true)
    for (const f of files) {
      try {
        await api.dosyaYukle(davaId, f)
        onToast(`"${f.name}" yüklendi`, 'info')
      } catch (err) {
        onToast(`"${f.name}" yüklenemedi: ${err.message}`, 'err')
      }
    }
    setYukleniyor(false)
    e.target.value = ""
    onYenile()
  }

  const toggle = async (id, mevcutBaglamda) => {
    try {
      await api.dosyaBaglamda(id, mevcutBaglamda ? 0 : 1)
      onYenile()
    } catch (err) {
      onToast(`Bağlam değiştirilemedi: ${err.message}`, 'err')
    }
  }

  const hepsiniSec = async (sec) => {
    try {
      await Promise.all(
        dosyalar
          .filter(d => !!d.baglamda !== sec)
          .map(d => api.dosyaBaglamda(d.id, sec ? 1 : 0))
      )
      onYenile()
    } catch (err) {
      onToast(`İşlem başarısız: ${err.message}`, 'err')
    }
  }

  const sil = async (id, ad) => {
    setSilIslemi(id)
    try {
      await api.dosyaSil(id)
      onYenile()
    } catch (err) {
      onToast(`"${ad}" silinemedi: ${err.message}`, 'err')
    } finally {
      setSilIslemi(null)
    }
  }

  const baglamdaKi = dosyalar.filter(d => d.baglamda).length
  const hepsiSecili = dosyalar.length > 0 && baglamdaKi === dosyalar.length
  const hicbiri = baglamdaKi === 0

  return (
    <div className="file-panel">
      <div className="file-panel-header">
        <div className="file-panel-title">
          <span>Evraklar</span>
          {dosyalar.length > 0 && (
            <span className={`baglamda-badge ${hepsiSecili ? 'tam' : baglamdaKi > 0 ? 'kismi' : 'bos'}`}>
              {baglamdaKi}/{dosyalar.length} bağlamda
            </span>
          )}
        </div>
        <div className="file-panel-actions">
          {dosyalar.length > 0 && (
            <>
              <button
                className="mini-btn"
                onClick={() => hepsiniSec(!hepsiSecili)}
                title={hepsiSecili ? 'Seçimi kaldır' : 'Hepsini seç'}
              >
                {hepsiSecili ? '☐ Kaldır' : '☑ Hepsini Seç'}
              </button>
              {!hicbiri && !hepsiSecili && (
                <button className="mini-btn warn" onClick={() => hepsiniSec(false)}>
                  ☐ Temizle
                </button>
              )}
            </>
          )}
          <button className="mini-btn primary" onClick={() => inpRef.current?.click()} disabled={yukleniyor}>
            {yukleniyor ? '⏳' : '+ Ekle'}
          </button>
          <input ref={inpRef} type="file" multiple hidden
            accept=".pdf,.tiff,.tif,.udf,.zip,.docx"
            onChange={yukle} />
        </div>
      </div>

      {dosyalar.length === 0 ? (
        <div className="file-panel-empty">
          PDF, TIFF, UDF, ZIP veya DOCX yükleyin
        </div>
      ) : (
        <div className="file-list">
          {dosyalar.map(d => {
            const icon = FORMAT_ICON[d.format?.toLowerCase()] || '📄'
            const secili = !!d.baglamda
            return (
              <div
                key={d.id}
                className={`file-row ${secili ? 'secili' : ''}`}
                onClick={() => toggle(d.id, d.baglamda)}
                title={secili ? 'Bağlamdan çıkarmak için tıkla' : 'Bağlama eklemek için tıkla'}
              >
                <span className={`file-checkbox ${secili ? 'checked' : ''}`}>
                  {secili ? '✓' : ''}
                </span>
                <span className="file-icon">{icon}</span>
                <span className="file-name">{d.dosya_adi}</span>
                <button
                  className="file-sil"
                  onClick={e => { e.stopPropagation(); sil(d.id, d.dosya_adi) }}
                  disabled={silIslemi === d.id}
                  title="Dosyayı sil"
                >
                  {silIslemi === d.id ? '…' : '✕'}
                </button>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
