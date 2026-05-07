import React, { useState, useRef, useCallback } from 'react'
import { api } from '../api.js'

/* ── XML ayrıştırıcı ─────────────────────────────────────────────────────── */

function xmlGetir(xml, tag, fallback = '') {
  const re = new RegExp(`<${tag}[^>]*>([\\s\\S]*?)</${tag}>`, 'i')
  const m = xml.match(re)
  return m ? m[1].trim() : fallback
}

function xmlMaddeler(xml, parentTag) {
  const parent = xmlGetir(xml, parentTag, '')
  if (!parent) return []
  const maddeler = []
  const re = /<madde[^>]*>([\s\S]*?)<\/madde>/gi
  let m
  while ((m = re.exec(parent)) !== null) {
    maddeler.push(m[1].trim())
  }
  return maddeler
}

function xmlParse(xml) {
  // Clean markdown fences
  let temiz = xml.trim()
  temiz = temiz.replace(/^```xml\s*/i, '').replace(/^```\s*/i, '').replace(/\s*```$/, '').trim()

  return {
    mahkeme_adi: xmlGetir(temiz, 'mahkeme_adi', ''),
    esas_no: xmlGetir(temiz, 'esas_no', ''),
    tarih: xmlGetir(temiz, 'tarih', ''),
    konu_metin: xmlGetir(temiz, 'konu_metin', '') || xmlGetir(temiz, 'konu', ''),
    davaci_etiketi: xmlGetir(temiz, 'davaci_etiketi', 'DAVACI (MÜVEKKİL)'),
    davaci_bilgi: xmlGetir(temiz, 'davaci_bilgi', ''),
    davali_etiketi: xmlGetir(temiz, 'davali_etiketi', 'DAVALI'),
    davali_bilgi: xmlGetir(temiz, 'davali_bilgi', ''),
    vekil_bilgi: xmlGetir(temiz, 'vekil_bilgi', 'Av. Fatih Dişçi'),
    aciklamalar: xmlMaddeler(temiz, 'aciklamalar'),
    hukuki_dayanak: xmlGetir(temiz, 'hukuki_dayanak', ''),
    sonuc: xmlMaddeler(temiz, 'sonuc'),
    saygi: xmlGetir(temiz, 'saygi', 'Saygılarımla,'),
    imza_tarih: xmlGetir(temiz, 'tarih_yer', ''),
    imza_unvan: xmlGetir(temiz, 'unvan', 'Av. Fatih Dişçi'),
  }
}

/* ── XML escape & yapıyı tekrar XML'e çevir ──────────────────────────────── */

function xmlEscape(str) {
  if (!str) return ''
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&apos;')
}

function veriToXml(v) {
  const e = xmlEscape
  const maddelerXml = (arr) => arr.map((m, i) => `    <madde no="${i + 1}">${e(m)}</madde>`).join('\n')
  return `<?xml version="1.0" encoding="UTF-8"?>
<dilekce>
  <mahkeme>${e(v.mahkeme_adi)}</mahkeme>
  <esas_no>${e(v.esas_no)}</esas_no>
  <tarih>${e(v.tarih)}</tarih>
  <basliklar>
    <mahkeme_adi>${e(v.mahkeme_adi)}</mahkeme_adi>
  </basliklar>
  <taraflar>
    <davaci_etiketi>${e(v.davaci_etiketi)}</davaci_etiketi>
    <davaci_bilgi>${e(v.davaci_bilgi)}</davaci_bilgi>
    <davali_etiketi>${e(v.davali_etiketi)}</davali_etiketi>
    <davali_bilgi>${e(v.davali_bilgi)}</davali_bilgi>
    <vekil_bilgi>${e(v.vekil_bilgi)}</vekil_bilgi>
  </taraflar>
  <konu_metin>${e(v.konu_metin)}</konu_metin>
  <aciklamalar>
${maddelerXml(v.aciklamalar)}
  </aciklamalar>
  <hukuki_dayanak>${e(v.hukuki_dayanak)}</hukuki_dayanak>
  <sonuc>
${maddelerXml(v.sonuc)}
  </sonuc>
  <saygi>${e(v.saygi)}</saygi>
  <imza>
    <tarih_yer>${e(v.imza_tarih)}</tarih_yer>
    <unvan>${e(v.imza_unvan)}</unvan>
  </imza>
</dilekce>`
}

/* ── Düzenlenebilir alan ─────────────────────────────────────────────────── */

function Editable({ value, onChange, tag: Tag = 'span', className = '', style = {}, multiline = false }) {
  const ref = useRef(null)

  const onBlur = () => {
    if (!ref.current) return
    const yeni = multiline ? ref.current.innerText : ref.current.innerText.replace(/\n/g, ' ')
    if (yeni !== value) onChange(yeni)
  }

  const onKeyDown = (e) => {
    if (!multiline && e.key === 'Enter') {
      e.preventDefault()
      ref.current?.blur()
    }
  }

  return (
    <Tag
      ref={ref}
      className={`editable ${className}`}
      contentEditable
      suppressContentEditableWarning
      onBlur={onBlur}
      onKeyDown={onKeyDown}
      style={style}
    >{value}</Tag>
  )
}

/* ── Ana bileşen ─────────────────────────────────────────────────────────── */

export default function DilekcePreview({ davaId, xmlStr, dilekceTuru, onKapat, onToast }) {
  const [veri, setVeri] = useState(() => xmlParse(xmlStr))
  const [indiriliyor, setIndiriliyor] = useState(false)

  const guncelle = useCallback((alan, deger) => {
    setVeri(v => ({ ...v, [alan]: deger }))
  }, [])

  const maddeGuncelle = useCallback((alan, idx, deger) => {
    setVeri(v => {
      const yeni = [...v[alan]]
      yeni[idx] = deger
      return { ...v, [alan]: yeni }
    })
  }, [])

  const maddeEkle = useCallback((alan) => {
    setVeri(v => ({ ...v, [alan]: [...v[alan], ''] }))
  }, [])

  const maddeSil = useCallback((alan, idx) => {
    setVeri(v => ({ ...v, [alan]: v[alan].filter((_, i) => i !== idx) }))
  }, [])

  const indir = async () => {
    setIndiriliyor(true)
    try {
      const xmlSon = veriToXml(veri)
      const { blob, dosyaAdi } = await api.dilekceIndir(davaId, xmlSon, dilekceTuru)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = dosyaAdi
      a.click()
      URL.revokeObjectURL(url)
      onToast?.(`${dilekceTuru} dilekçesi indirildi: ${dosyaAdi}`, 'info')
    } catch (err) {
      onToast?.(`İndirme hatası: ${err.message}`, 'err')
    } finally {
      setIndiriliyor(false)
    }
  }

  return (
    <aside className="dilekce-panel">
      <div className="dilekce-toolbar">
        <h3>📄 Dilekçe Önizleme</h3>
        <span className="dilekce-toolbar-sub">{dilekceTuru}</span>
        <div className="dilekce-toolbar-actions">
          <button className="btn sm gold" onClick={indir} disabled={indiriliyor}>
            {indiriliyor ? '⏳ İndiriliyor...' : '⬇ UDF İndir'}
          </button>
          <button className="btn ghost sm" onClick={onKapat}>✕</button>
        </div>
      </div>

      <div className="dilekce-scroll">
        <div className="dilekce-a4">
          {/* Mahkeme Başlığı */}
          <div className="d-center d-bold">
            <Editable value={veri.mahkeme_adi} onChange={v => guncelle('mahkeme_adi', v)} tag="div" />
          </div>

          <div className="d-spacer" />

          {/* Esas No */}
          {veri.esas_no && (
            <div className="d-row">
              <span className="d-label">ESAS NO</span>
              <span className="d-sep">:</span>
              <Editable value={veri.esas_no} onChange={v => guncelle('esas_no', v)} />
            </div>
          )}

          <div className="d-spacer" />

          {/* Taraflar */}
          <div className="d-row">
            <Editable value={veri.davaci_etiketi} onChange={v => guncelle('davaci_etiketi', v)} className="d-label" />
            <span className="d-sep">:</span>
            <Editable value={veri.davaci_bilgi} onChange={v => guncelle('davaci_bilgi', v)} />
          </div>
          <div className="d-row">
            <span className="d-label">VEKİLİ</span>
            <span className="d-sep">:</span>
            <Editable value={veri.vekil_bilgi} onChange={v => guncelle('vekil_bilgi', v)} />
          </div>

          <div className="d-spacer-sm" />

          <div className="d-row">
            <Editable value={veri.davali_etiketi} onChange={v => guncelle('davali_etiketi', v)} className="d-label" />
            <span className="d-sep">:</span>
            <Editable value={veri.davali_bilgi} onChange={v => guncelle('davali_bilgi', v)} />
          </div>

          <div className="d-spacer" />

          {/* Konu */}
          <div className="d-row">
            <span className="d-label">KONU</span>
            <span className="d-sep">:</span>
            <Editable value={veri.konu_metin} onChange={v => guncelle('konu_metin', v)} />
          </div>

          <div className="d-spacer" />

          {/* Açıklamalar */}
          <div className="d-section-title">AÇIKLAMALAR :</div>
          <div className="d-spacer-sm" />
          {veri.aciklamalar.map((m, i) => (
            <div key={i} className="d-madde">
              <span className="d-madde-no">{i + 1}-</span>
              <Editable
                value={m}
                onChange={v => maddeGuncelle('aciklamalar', i, v)}
                tag="div"
                className="d-madde-icerik"
                multiline
              />
              <button className="d-madde-sil" onClick={() => maddeSil('aciklamalar', i)} title="Madde sil">×</button>
            </div>
          ))}
          <button className="d-madde-ekle" onClick={() => maddeEkle('aciklamalar')}>+ Madde Ekle</button>

          <div className="d-spacer" />

          {/* Hukuki Dayanak */}
          <div className="d-section-title">HUKUKİ DAYANAK :</div>
          <Editable
            value={veri.hukuki_dayanak}
            onChange={v => guncelle('hukuki_dayanak', v)}
            tag="div"
            className="d-text-block"
            multiline
          />

          <div className="d-spacer" />

          {/* Sonuç ve Talep */}
          <div className="d-section-title">SONUÇ VE TALEP :</div>
          <div className="d-spacer-sm" />
          {veri.sonuc.map((m, i) => (
            <div key={i} className="d-madde">
              <span className="d-madde-no">{i + 1}-</span>
              <Editable
                value={m}
                onChange={v => maddeGuncelle('sonuc', i, v)}
                tag="div"
                className="d-madde-icerik"
                multiline
              />
              <button className="d-madde-sil" onClick={() => maddeSil('sonuc', i)} title="Madde sil">×</button>
            </div>
          ))}
          <button className="d-madde-ekle" onClick={() => maddeEkle('sonuc')}>+ Madde Ekle</button>

          <div className="d-spacer" />

          {/* İmza */}
          <div className="d-right">
            <Editable value={veri.saygi} onChange={v => guncelle('saygi', v)} tag="div" />
            <Editable value={veri.imza_tarih} onChange={v => guncelle('imza_tarih', v)} tag="div" />
            <Editable value={veri.imza_unvan} onChange={v => guncelle('imza_unvan', v)} tag="div" className="d-bold" />
          </div>
        </div>
      </div>
    </aside>
  )
}
