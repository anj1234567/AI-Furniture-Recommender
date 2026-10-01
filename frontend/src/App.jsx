import { useState, useEffect } from 'react'
import { API_URL, inr } from './lib/api'
import ControlPanel from './components/ControlPanel'
import AnalysisPanel from './components/AnalysisPanel'
import PicksPanel from './components/PicksPanel'
import ComparePanel from './components/ComparePanel'
import RoomTab from './components/RoomTab'
import ObjectRemover from './components/ObjectRemover'
import ModelModal from './components/ModelModal'
import { Icon, StepIndicator, LoadingState, ErrorState } from './components/ui'
import './theme.css'
import './professional.css'

// Fallback lists, so the dropdowns are never empty even if /options is slow to answer.
const DEFAULT_OPTIONS = {
  styles: ['modern', 'scandinavian', 'industrial', 'bohemian', 'traditional', 'coastal', 'rustic', 'japanese', 'retro'].map((v) => ({ value: v, label: v[0].toUpperCase() + v.slice(1) })),
  room_types: [['bedroom', 'Bedroom'], ['living', 'Living room'], ['dining', 'Dining / Kitchen'], ['study', 'Study / Office'], ['kids', 'Kids room'], ['outdoor', 'Outdoor']].map(([value, label]) => ({ value, label })),
}
const cap = (t) => (t ? String(t).replace(/[_-]/g, ' ').replace(/^./, (c) => c.toUpperCase()) : '')

const TABS = [['analysis', 'Room analysis'], ['edit', 'Clear objects'], ['picks', 'Recommendations'], ['room', 'See it in your room'], ['compare', 'Algorithm comparison']]

// never show raw API errors: our own messages about the photo pass through, everything else is rephrased
function friendly(m) {
  if (m === 'Failed to fetch') return 'We could not reach the analysis service. Make sure the backend is running, then try again.'
  if (/room photo|Choose a room photo|read the photo/i.test(m)) return m
  return 'Please try again, or upload another image.'
}

export default function App() {
  const [photo, setPhoto] = useState(null)
  const [preview, setPreview] = useState(null)
  const [budget, setBudget] = useState('')
  const [roomType, setRoomType] = useState('')
  const [style, setStyle] = useState('')
  const [roomW, setRoomW] = useState('')
  const [roomL, setRoomL] = useState('')
  const [est, setEst] = useState(null)   // size estimated from the photo; never written into the size fields
  const [options, setOptions] = useState(DEFAULT_OPTIONS)
  const [coords, setCoords] = useState({ lat: 18.5204, lng: 73.8567 })
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [picks, setPicks] = useState({})
  const [openSwap, setOpenSwap] = useState(null)
  const [view3d, setView3d] = useState(null)
  const [tab, setTab] = useState('analysis')
  const [origPhoto, setOrigPhoto] = useState(null)
  const [origPreview, setOrigPreview] = useState(null)
  const [cleanInfo, setCleanInfo] = useState(null)
  const [colors, setColors] = useState({})
  const [focusCat, setFocusCat] = useState(null)

  useEffect(() => {
    let alive = true, tries = 0
    const load = () => fetch(`${API_URL}/options`).then((r) => r.json()).then((o) => {
      if (alive && o?.styles?.length && o?.room_types?.length) setOptions(o)
    }).catch(() => { if (alive && ++tries < 6) setTimeout(load, 2000) })   // backend may still be starting
    load()
    navigator.geolocation?.getCurrentPosition((pos) => setCoords({ lat: pos.coords.latitude, lng: pos.coords.longitude }), () => {}, { timeout: 8000 })
    return () => { alive = false }
  }, [])

  function pickFile(file) {
    if (!file) return
    const url = URL.createObjectURL(file)
    setPhoto(file); setPreview(url); setOrigPhoto(file); setOrigPreview(url); setCleanInfo(null); setColors({})
    setEst(null)
  }
  function changeRoomType(r) { setRoomType(r); if (result) runAnalysis(r, photo, false, style) }
  function changeStyle(v) { setStyle(v); if (result) runAnalysis(roomType, photo, false, v) }

  async function runAnalysis(r = roomType, file = photo, goToStart = true, st = style) {
    if (!file || !budget) { setError('Choose a room photo and enter a budget.'); return }
    setLoading(true); setError(null)
    const fd = new FormData()
    fd.append('photo', file); fd.append('budget', budget)
    fd.append('lat', String(coords.lat)); fd.append('lng', String(coords.lng))
    fd.append('style', st); fd.append('room_type', r)   // empty style = detect it from the photo
    // send the size only if the user typed one (exactly what they typed)
    if (Number(roomW) > 0 && Number(roomL) > 0) {
      fd.append('room_width_m', roomW)
      fd.append('room_length_m', roomL)
    }
    try {
      const res = await fetch(`${API_URL}/analyze`, { method: 'POST', body: fd })
      if (!res.ok) {
        let msg = `Request failed: ${res.status}`
        try { const j = await res.json(); if (j.detail) msg = j.detail } catch { /* keep default */ }
        throw new Error(msg)
      }
      const data = await res.json()
      setEst(data.space?.source === 'estimated' ? { w: data.space.room_w_m, l: data.space.room_l_m } : null)
      setPicks({}); setOpenSwap(null); setResult(data)
      if (goToStart) setTab('analysis')
    } catch (err) {
      setResult(null)
      setError(friendly(err.message))
    } finally { setLoading(false) }
  }

  function startOver() {
    setPhoto(null); setPreview(null); setOrigPhoto(null); setOrigPreview(null); setResult(null); setError(null)
    setColors({}); setPicks({}); setFocusCat(null); setRoomW(''); setRoomL(''); setEst(null); setTab('analysis')
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }
  function openCategory(c) { setFocusCat(c); setTab('picks'); window.scrollTo({ top: 0, behavior: 'smooth' }) }

  // a cleaned photo (objects removed) replaces the current one and the room is analysed again
  function applyCleaned(file, method) {
    setPhoto(file); setPreview(URL.createObjectURL(file)); setCleanInfo(method); setColors({})
    runAnalysis(roomType, file, false)
  }
  function restoreOriginal() {
    setPhoto(origPhoto); setPreview(origPreview); setCleanInfo(null); setColors({})
    runAnalysis(roomType, origPhoto, false)
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
    focusCat, items, optimal, alts, bs, sp, used, budget: Number(budget), picks, setPicks, openSwap, setOpenSwap, setView3d,
    usedArea: items.reduce((t, i) => t + (i.footprint_m2 || 0), 0),
    totalScore: items.reduce((t, i) => t + i.score, 0),
    anySwapped: items.some((i, k) => i.item_id !== optimal[k].item_id),
  }
  const step = !photo ? 1 : loading ? 2 : !result ? 1 : tab === 'room' || tab === 'compare' ? 5 : tab === 'picks' ? 4 : 3
  const form = { photo, preview, budget, setBudget, roomType, style, roomW, roomL, setRoomW, setRoomL, est, pickFile, changeRoomType, changeStyle }

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand"><span className="logo"><Icon n="home" size={18} /></span><div><b>AI Furniture Recommender</b><small>Interior design assistant</small></div></div>
        {(photo || result) && <button type="button" className="ghost" onClick={startOver}>Start over</button>}
      </header>
      <StepIndicator step={step} />
      {!result && !loading && !photo && (
        <section className="hero">
          <h1>Turn your room into a personalized furniture plan with AI.</h1>
          <p>Upload your room, we detect what is already there, then recommend furniture that fits your style, budget and floor space, and show it in your room.</p>
          <ol className="flow"><li>Upload your room</li><li>AI detects furniture</li><li>Get recommendations</li><li>Visualize your space</li></ol>
          <button type="button" className="btn" onClick={() => document.getElementById('photo-input')?.click()}>Analyze my room <Icon n="arrow" size={16} /></button>
        </section>
      )}
      <div className="layout">
        <ControlPanel f={form} options={options} loading={loading} error={null} onSubmit={() => runAnalysis()} />
        <main>
          {error && !loading && <ErrorState message={error} onRetry={() => runAnalysis()} />}
          {!result && !loading && !error && (
            <div className="card empty"><h2>{photo ? 'Ready to analyze' : 'No room image yet'}</h2>
              <p>{photo ? 'Enter your budget and press Get recommendations.' : 'Upload a room image to start your AI analysis.'}</p></div>
          )}
          {loading && !result && <LoadingState />}
          {result && (
            <div className="results" style={{ opacity: loading ? 0.5 : 1 }}>
              <div className="summary">
                <span className="chip-s">Room: <b>{result.room_kind?.kind ? cap(result.room_kind.kind) : 'Any'}</b></span>
                <span className="chip-s">Style: <b>{result.style_used?.source === 'user' ? cap(result.style_used.label) : 'Any'}</b></span>
                {sp && <span className="chip-s">Size: <b>{sp.room_w_m} × {sp.room_l_m} m</b>{sp.source === 'user' ? '' : ' (est.)'}</span>}
              </div>
              <div className="kpis">
                <div className="kpi"><span>Detected objects</span><b>{result.perception.detections.length}</b></div>
                <div className="kpi"><span>Recommendations</span><b>{items.length}</b></div>
                <div className="kpi"><span>Average match</span><b>{items.length ? Math.round((100 * picksData.totalScore) / items.length) : 0}%</b></div>
                <div className="kpi"><span>Budget used</span><b>{inr(used)}</b><small>{bs.percent_used}% of {inr(bs.budget)}</small><i style={{ width: Math.min(100, bs.percent_used) + '%' }} /></div>
              </div>
              {result.style_filter && (
                <div className="notice info">Showing only <b>{cap(result.style_filter.style)}</b> furniture.
                  {result.style_filter.fallback_categories?.length > 0 && ` Our catalog has no ${cap(result.style_filter.style)} ${result.style_filter.fallback_categories.join(', ')}, so those show the closest options.`}</div>
              )}
              <nav className="tabs" role="tablist">
                {TABS.map(([k, label]) => <button key={k} type="button" role="tab" aria-selected={tab === k} className={tab === k ? 'on' : ''} onClick={() => setTab(k)}>{label}</button>)}
              </nav>
              <div className="panel" key={tab}>
                {tab === 'picks' && (
                  <>
                    <div className="cta"><span>{items.length} pieces for {inr(used)}. See how they look in your room.</span>
                      <button type="button" className="btn small" onClick={() => setTab('room')}>See it in your room <Icon n="arrow" size={15} /></button></div>
                    <PicksPanel d={picksData} />
                  </>
                )}
                {tab === 'room' && <RoomTab items={items} result={result} preview={preview} apiUrl={API_URL} colors={colors} setColors={setColors} />}
                {tab === 'edit' && <ObjectRemover result={result} preview={preview} photo={photo} origPreview={origPreview} edited={photo !== origPhoto}
                                                   info={cleanInfo} busy={loading} onCleaned={applyCleaned} onRestore={restoreOriginal} />}
                {tab === 'analysis' && <AnalysisPanel result={result} preview={preview} onOpenCategory={openCategory} />}
                {tab === 'compare' && <ComparePanel result={result} />}
              </div>
            </div>
          )}
        </main>
      </div>
      {view3d && <ModelModal item={view3d} onClose={() => setView3d(null)} />}
      <footer className="footer">AI-Powered Interior Design &amp; Furniture Recommendation Platform · Group 36</footer>
    </div>
  )
}
