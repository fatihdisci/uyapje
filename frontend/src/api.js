const API = "http://localhost:8000/api"

async function istek(yol, opts = {}) {
  const res = await fetch(API + yol, {
    headers: { "Content-Type": "application/json", ...(opts.headers || {}) },
    ...opts,
  })
  if (!res.ok) {
    let mesaj = `Hata ${res.status}`
    try { const j = await res.json(); mesaj = j.detail || mesaj } catch {}
    throw new Error(mesaj)
  }
  return res.json()
}

export const api = {
  sistemDurum: () => istek("/sistem/durum"),
  davalar: () => istek("/davalar"),
  davaOlustur: (d) => istek("/dava", { method: "POST", body: JSON.stringify(d) }),
  davaGetir: (id) => istek(`/dava/${id}`),
  davaSil: (id) => istek(`/dava/${id}`, { method: "DELETE" }),
  davaGuncelle: (id, d) => istek(`/dava/${id}`, { method: "PATCH", body: JSON.stringify(d) }),
  yarinkiDurusmalar: () => istek("/yarinki-durusmalar"),
  dosyalar: (id) => istek(`/dava/${id}/dosyalar`),
  dosyaYukle: async (id, file) => {
    const fd = new FormData(); fd.append("file", file)
    const r = await fetch(`${API}/dava/${id}/dosya`, { method: "POST", body: fd })
    if (!r.ok) {
      let m = `Hata ${r.status}`; try { m = (await r.json()).detail || m } catch {}
      throw new Error(m)
    }
    return r.json()
  },
  dosyaSil: (dosyaId) => istek(`/dosya/${dosyaId}`, { method: "DELETE" }),
  dosyaBaglamda: (dosyaId, baglamda) => istek(`/dosya/${dosyaId}/baglamda`, { method: "PATCH", body: JSON.stringify({ baglamda }) }),
  sessionlari: (id) => istek(`/dava/${id}/sessionlar`),
  yeniSession: (id) => istek(`/dava/${id}/session`, { method: "POST" }),
  sohbetGecmisi: (id, sessionId) => istek(`/dava/${id}/sohbet?session_id=${sessionId}`),
  sohbet: (id, soru, sessionId) => istek(`/dava/${id}/sohbet`, { method: "POST", body: JSON.stringify({ soru, session_id: sessionId }) }),
  durusma: (id, tarih, sessionId) => istek(`/dava/${id}/durusma`, { method: "POST", body: JSON.stringify({ tarih, session_id: sessionId }) }),
  ozet: (id, sessionId) => istek(`/dava/${id}/ozet?session_id=${sessionId}`),
  risk: (id, sessionId) => istek(`/dava/${id}/risk?session_id=${sessionId}`),
  ictihat: (id, sorgu, sessionId) => istek(`/dava/${id}/ictihat`, { method: "POST", body: JSON.stringify({ sorgu, session_id: sessionId }) }),
}
