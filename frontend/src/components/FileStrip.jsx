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

  const sil = async (id) => {
    await api.dosyaSil(id)
    onYenile()
  }

  return (
    <div className="file-strip">
      <button className="btn ghost sm" onClick={() => inpRef.current?.click()} disabled={yukleniyor}>
        {yukleniyor ? '⏳ Yükleniyor...' : '+ Dosya Ekle'}
      </button>
      <input ref={inpRef} type="file" multiple hidden
        accept=".pdf,.tiff,.tif,.udf,.zip,.docx"
        onChange={yukle} />
      {dosyalar.map(d => (
        <span key={d.id} className="file-pill">
          📄 {d.dosya_adi}
          <span className="x" onClick={() => sil(d.id)}>✕</span>
        </span>
      ))}
      {dosyalar.length === 0 && !yukleniyor && (
        <span style={{ color: 'var(--muted)', fontSize: 12, alignSelf: 'center' }}>
          PDF, TIFF, UDF, ZIP veya DOCX yükleyin
        </span>
      )}
    </div>
  )
}
