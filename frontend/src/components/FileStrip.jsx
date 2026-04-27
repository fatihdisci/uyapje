import React, { useRef, useState } from 'react'
import { api } from '../api.js'

export default function FileStrip({ davaId, dosyalar, onYenile, onToast }) {
  const inpRef = useRef(null)
  const [yukleniyor, setYukleniyor] = useState(false)

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

  const sil = async (id, ad) => {
    if (!window.confirm(`"${ad}" dosyasını silmek istediğinize emin misiniz?`)) return
    try {
      await api.dosyaSil(id)
      onYenile()
    } catch (err) {
      onToast(`"${ad}" silinemedi: ${err.message}`, 'err')
    }
  }

  const baglamdaKi = dosyalar.filter(d => d.baglamda).length

  return (
    <div className="file-strip">
      <button className="btn ghost sm" onClick={() => inpRef.current?.click()} disabled={yukleniyor}>
        {yukleniyor ? '⏳ Yükleniyor...' : '+ Dosya Ekle'}
      </button>
      <input ref={inpRef} type="file" multiple hidden
        accept=".pdf,.tiff,.tif,.udf,.zip,.docx"
        onChange={yukle} />

      {dosyalar.map(d => (
        <span
          key={d.id}
          className={`file-pill ${d.baglamda ? 'baglamda-aktif' : 'baglamda-pasif'}`}
          title={d.baglamda ? 'Bağlamda — tıkla çıkarmak için' : 'Bağlamda değil — tıkla eklemek için'}
        >
          <span className="baglamda-toggle" onClick={() => toggle(d.id, d.baglamda)}>
            {d.baglamda ? '●' : '○'}
          </span>
          📄 {d.dosya_adi}
          <span className="x" onClick={(e) => { e.stopPropagation(); sil(d.id, d.dosya_adi) }}>✕</span>
        </span>
      ))}

      {dosyalar.length === 0 && !yukleniyor && (
        <span style={{ color: 'var(--muted)', fontSize: 12, alignSelf: 'center' }}>
          PDF, TIFF, UDF, ZIP veya DOCX yükleyin
        </span>
      )}

      {dosyalar.length > 0 && (
        <span className="baglamda-sayac" style={{
          marginLeft: 'auto', fontSize: 11, color: baglamdaKi > 0 ? 'var(--green)' : 'var(--red)',
          alignSelf: 'center', whiteSpace: 'nowrap', flexShrink: 0
        }}>
          {baglamdaKi} / {dosyalar.length} bağlamda
        </span>
      )}
    </div>
  )
}
