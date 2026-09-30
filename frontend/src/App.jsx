import { useState, useEffect } from 'react'
import { API_URL, inr } from './lib/api'
import ControlPanel from './components/ControlPanel'
import AnalysisPanel from './components/AnalysisPanel'
import PicksPanel from './components/PicksPanel'
import ComparePanel from './components/ComparePanel'
import RoomTab from './components/RoomTab'
import ModelModal from './components/ModelModal'

const TABS = [['picks', 'Picks'], ['room', 'See it in your room'], ['analysis', 'Room analysis'], ['compare', 'DP vs Greedy']]

export default function App() {
  const [photo, setPhoto] = useState(null)
  const [preview, setPreview] = useState(null)
  const [budget, setBudget] = useState('')
  const [style, setStyle] = useState('')
  const [roomType, setRoomType] = useState('')
  const [roomW, setRoomW] = useState('')
  const [roomL, setRoomL] = useState('')
  const [roomAuto, setRoomAuto] = useState(false)
  const [options, setOptions] = useState({ styles: [], room_types: [] })
  const [coords, setCoords] = useState({ lat: 18.5204, lng: 73.8567 })
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [picks, setPicks] = useState({})
  const [openSwap, setOpenSwap] = useState(null)
  const [view3d, setView3d] = useState(null)
  const [tab, setTab] = useState('picks')

  useEffect(() => {
    fetch(`${API_URL}/options`).then((r) => r.json()).then(setOptions).catch(() => {})
    navigator.geolocation?.getCurrentPosition((pos) => setCoords({ lat: pos.coords.latitude, lng: pos.coords.longitude }), () => {}, { timeout: 8000 })
  }, [])

  function pickFile(file) {
    if (!file) return
    setPhoto(file); setPreview(URL.createObjectURL(file))
    if (roomAuto) { setRoomW(''); setRoomL(''); setRoomAuto(false) }
  }
  function changeChoice(s, r) { setStyle(s); setRoomType(r); if (result) runAnalysis(s, r) }

  async function runAnalysis(s = style, r = roomType) {
    if (!photo || !budget) { setError('Choose a room photo and enter a budget.'); return }
    setLoading(true); setError(null)
    const fd = new FormData()
    fd.append('photo', photo); fd.append('budget', budget)
    fd.append('lat', String(coords.lat)); fd.append('lng', String(coords.lng))
    fd.append('style', s); fd.append('room_type', r)
    if (roomW && roomL && !roomAuto) { fd.append('room_width_m', roomW); fd.append('room_length_m', roomL) }
    try {
      const res = await fetch(`${API_URL}/analyze`, { method: 'POST', body: fd })
      if (!res.ok) {
        let msg = `Request failed: ${res.status}`
        try { const j = await res.json(); if (j.detail) msg = j.detail } catch { /* keep default */ }
        throw new Error(msg)
      }
      const data = await res.json()
      if (data.space?.source === 'estimated') { setRoomW(String(data.space.room_w_m)); setRoomL(String(data.space.room_l_m)); setRoomAuto(true) }
      setPicks({}); setOpenSwap(null); setResult(data)
    } catch (err) {
      setResult(null)
      setError(err.message === 'Failed to fetch' ? 'Cannot reach the backend. Is it running on port 8000?' : err.message)
    } finally { setLoading(false) }
  }

  // the optimizer's pick per category, unless the user swapped it
  const optimal = result?.recommendation.selected_items ?? []
  const alts = result?.recommendation.alternatives ?? {}
  const items = optimal.map((o) => {
    const id = picks[o.category]
    if (!id || id === o.item_id) return o
    const a = (alts[o.category] ?? []).find((x) => x.item_id === id)
    return a ? { ...a, nearby_stores: o.nearby_stores } : o
  })
  const used = items.reduce((t, i) => t + i.price, 0)
  const sp = result?.space
  const bs = result ? { budget: Number(budget), used, left: Number(budget) - used, percent_used: budget > 0 ? Math.round((100 * used) / budget) : 0 } : null
  const picksData = {
    items, optimal, alts, bs, sp, used, budget: Number(budget), picks, setPicks, openSwap, setOpenSwap, setView3d,
    usedArea: items.reduce((t, i) => t + (i.footprint_m2 || 0), 0),
    totalScore: items.reduce((t, i) => t + i.score, 0),
    anySwapped: items.some((i, k) => i.item_id !== optimal[k].item_id),
  }
  const form = { photo, preview, budget, setBudget, style, roomType, roomW, roomL, setRoomW, setRoomL, roomAuto, setRoomAuto, pickFile, changeChoice }

  return (
    <div className="app">
      <header className="header">
        <h1>AI Furniture Recommender</h1>
        <p>Upload a room photo and a budget. See the best-fitting furniture inside your room.</p>
      </header>
      <div className="layout">
        <ControlPanel f={form} options={options} loading={loading} error={error} onSubmit={() => runAnalysis()} />
        <main>
          {!result && !loading && (
            <div className="card empty"><h2>Start with a photo</h2>
              <p>We find the furniture and colours in your room, work out what is missing, choose the set that fits your budget and floor space, and show it to you in 3D.</p></div>
          )}
          {loading && !result && <><div className="skel" /><div className="skel" /></>}
          {result && (
            <div style={{ opacity: loading ? 0.5 : 1, transition: '.2s' }}>
              <nav className="tabs" role="tablist">
                {TABS.map(([k, label]) => <button key={k} type="button" role="tab" aria-selected={tab === k} className={tab === k ? 'on' : ''} onClick={() => setTab(k)}>{label}</button>)}
              </nav>
              {tab === 'picks' && (
                <>
                  <div className="cta">
                    <span>{items.length} pieces for {inr(used)}. See how they look in your room.</span>
                    <button type="button" className="btn small" onClick={() => setTab('room')}>Open 3D room</button>
                  </div>
                  <PicksPanel d={picksData} />
                </>
              )}
              {tab === 'room' && <RoomTab items={items} result={result} preview={preview} apiUrl={API_URL} />}
              {tab === 'analysis' && <AnalysisPanel result={result} preview={preview} />}
              {tab === 'compare' && <ComparePanel result={result} />}
            </div>
          )}
        </main>
      </div>
      {view3d && <ModelModal item={view3d} onClose={() => setView3d(null)} />}
    </div>
  )
}
