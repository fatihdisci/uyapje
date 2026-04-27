import React, { useEffect, useState } from 'react'
import Sidebar from './components/Sidebar.jsx'
import ChatPanel from './components/ChatPanel.jsx'
import IctihatPanel from './components/IctihatPanel.jsx'
import { api } from './api.js'

export default function App() {
  const [davalar, setDavalar] = useState([])
  const [aktifDava, setAktifDava] = useState(null)
  const [yarinki, setYarinki] = useState([])
  const [sistem, setSistem] = useState(null)
  const [ictihatAcik, setIctihatAcik] = useState(false)
  const [toastlar, setToastlar] = useState([])

  const toast = (mesaj, tip = 'info') => {
    const id = Date.now() + Math.random()
    setToastlar(t => [...t, { id, mesaj, tip }])
    setTimeout(() => setToastlar(t => t.filter(x => x.id !== id)), 5000)
  }

  const yukleSistem = async () => {
    try {
      const s = await api.sistemDurum()
      setSistem(s)
      if (!s.gemini_kurulu) {
        toast("Gemini CLI kurulu değil — terminalde: npm install -g @google/gemini-cli && gemini auth login", 'warn')
      } else if (!s.gemini_hazir) {
        toast("Gemini CLI auth gerekli — terminalde: gemini auth login", 'warn')
      }
      if (!s.yargi_mcp_aktif) {
        toast("Yargı MCP kurulu değil — içtihat araştırması çalışmaz", 'info')
      }
    } catch (err) {
      console.error("Sistem durum hatası:", err)
    }
  }

  const yukleDavalar = async () => {
    try {
      const [d, y] = await Promise.all([
        api.davalar(), api.yarinkiDurusmalar()
      ])
      setDavalar(d)
      setYarinki(y)
    } catch (err) {
      toast(`Backend bağlantı hatası: ${err.message}`, 'err')
    }
  }

  useEffect(() => { 
    yukleDavalar()
    yukleSistem()
  }, [])

  const yeniDava = async (d) => {
    try {
      const { id } = await api.davaOlustur(d)
      await yukleDavalar()
      setAktifDava({ id, ...d })
      toast(`Dosya eklendi (#${id})`, 'info')
    } catch (err) {
      toast(`Hata: ${err.message}`, 'err')
    }
  }

  const davaSil = async (id) => {
    if (!window.confirm(`Dava #${id} tamamen silinecek, emin misiniz?`)) return
    try {
      await api.davaSil(id)
      if (aktifDava?.id === id) setAktifDava(null)
      await yukleDavalar()
      toast(`Dava silindi (#${id})`, 'info')
    } catch (err) {
      toast(`Silme hatası: ${err.message}`, 'err')
    }
  }

  return (
    <div className={`app ${ictihatAcik && aktifDava ? 'with-ictihat' : ''}`}>
      <Sidebar
        davalar={davalar}
        aktifDava={aktifDava}
        secim={setAktifDava}
        yarinki={yarinki}
        sistem={sistem}
        onYeniDava={yeniDava}
        onYenile={yukleDavalar}
        onDavaSil={davaSil}
      />

      {aktifDava ? (
        <ChatPanel
          dava={aktifDava}
          onIctihatToggle={() => setIctihatAcik(v => !v)}
          onToast={toast}
        />
      ) : (
        <main className="main">
          <div className="empty">
            <div>
              <h3>UYAP Hukuk Asistanı</h3>
              <p>Sol panelden bir dava seçin veya yeni dava oluşturun.</p>
            </div>
          </div>
        </main>
      )}

      {ictihatAcik && aktifDava && (
        <IctihatPanel dava={aktifDava} onKapat={() => setIctihatAcik(false)} onToast={toast} />
      )}

      <div className="toast-wrap">
        {toastlar.map(t => (
          <div key={t.id} className={`toast ${t.tip}`}>{t.mesaj}</div>
        ))}
      </div>
    </div>
  )
}
