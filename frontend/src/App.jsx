import { useState, useEffect, useRef } from 'react'

// Talks to backend/api/main.py's /analyze and /options endpoints.
const API_URL = 'http://localhost:8000'
const inr = (n) => '₹' + Number(n).toLocaleString('en-IN')

const HOW = [
  { ic: '📷', t: 'Look', d: 'Detects furniture and dominant colours in your photo.' },
  { ic: '🔍', t: 'Find gaps', d: 'Works out which furniture your room is missing.' },
  { ic: '🧮', t: 'Optimise', d: 'Dynamic programming picks the best set within budget.' },
  { ic: '💬', t: 'Explain', d: 'Tells you why each item was chosen.' },
]

export default function App() {
  const [photo, setPhoto] = useState(null)
  const [preview, setPreview] = useState(null)
  const [imgSize, setImgSize] = useState(null)
  const [budget, setBudget] = useState('')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [style, setStyle] = useState('')
  const [roomType, setRoomType] = useState('')
  const [options, setOptions] = useState({ styles: [], room_types: [] })
  const [over, setOver] = useState(false)
  const fileRef = useRef(null)

  useEffect(() => {
    fetch(`${API_URL}/options`).then((r) => r.json()).then(setOptions).catch(() => {})
  }, [])

  function pickFile(f) {
    if (!f) return
    setPhoto(f)
    setPreview(URL.createObjectURL(f))
  }

  function changeChoice(newStyle, newRoom) {
    setStyle(newStyle)
    setRoomType(newRoom)
    if (result) runAnalysis(newStyle, newRoom)
  }

  async function runAnalysis(styleValue, roomValue) {
    if (!photo || !budget) {
      setError('Please choose a room photo and enter a budget.')
      return
    }
    setLoading(true)
    setError(null)
    const fd = new FormData()
    fd.append('photo', photo)
    fd.append('budget', budget)
    fd.append('lat', '18.5204') // Pune placeholder
    fd.append('lng', '73.8567')
    fd.append('style', styleValue)
    fd.append('room_type', roomValue)
    try {
      const res = await fetch(`${API_URL}/analyze`, { method: 'POST', body: fd })
      if (!res.ok) {
        let msg = `Request failed: ${res.status}`
        try { const j = await res.json(); if (j.detail) msg = j.detail } catch { /* keep default */ }
        throw new Error(msg)
      }
      setImgSize(null)
      setResult(await res.json())
    } catch (err) {
      setResult(null)
      setError(err.message === 'Failed to fetch'
        ? 'Cannot reach the backend. Is it running on port 8000?' : err.message)
    } finally {
      setLoading(false)
    }
  }

  const p = result?.perception
  const items = result?.recommendation.selected_items ?? []
  const bs = result?.budget_summary
  const dp = result?.comparison.dp_optimal
  const gr = result?.comparison.greedy
  const maxScore = Math.max(1, ...items.map((i) => i.score))

  return (
    <div className="app">
      <div className="header">
        <div className="logo">🛋️</div>
        <div>
          <h1>AI Furniture Recommender</h1>
          <p>Upload a room photo, set a budget, get the best-matching furniture.</p>
        </div>
      </div>

      <div className="layout">
        {/* ---------- Controls ---------- */}
        <form className="card side" onSubmit={(e) => { e.preventDefault(); runAnalysis(style, roomType) }}>
          <div className="field">
            <label>Room photo</label>
            <div
              className={`drop ${over ? 'over' : ''}`}
              onClick={() => fileRef.current.click()}
              onDragOver={(e) => { e.preventDefault(); setOver(true) }}
              onDragLeave={() => setOver(false)}
              onDrop={(e) => { e.preventDefault(); setOver(false); pickFile(e.dataTransfer.files[0]) }}
            >
              {preview && <img src={preview} alt="selected room" />}
              {photo ? photo.name : 'Click or drag a photo here'}
              <input ref={fileRef} type="file" accept="image/*" onChange={(e) => pickFile(e.target.files[0])} />
            </div>
          </div>

          <div className="field">
            <label>Total budget</label>
            <div className="money">
              <span>₹</span>
              <input className="input" type="number" min="0" value={budget}
                     onChange={(e) => setBudget(e.target.value)} placeholder="e.g. 30000" />
            </div>
            <div className="chips">
              {[10000, 25000, 40000, 75000].map((v) => (
                <button type="button" key={v} className="chip" onClick={() => setBudget(String(v))}>{inr(v)}</button>
              ))}
            </div>
          </div>

          <div className="field">
            <label>Room type</label>
            <select className="select" value={roomType} onChange={(e) => changeChoice(style, e.target.value)}>
              <option value="">Not sure</option>
              {options.room_types.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
          </div>

          <div className="field">
            <label>Preferred style</label>
            <select className="select" value={style} onChange={(e) => changeChoice(e.target.value, roomType)}>
              <option value="">Not sure (let the app decide)</option>
              {options.styles.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
            <div className="hint">Changing this after results appear re-runs the analysis.</div>
          </div>

          <button className="btn" type="submit" disabled={loading}>
            {loading ? <><span className="spin" />Analyzing…</> : 'Get recommendations'}
          </button>
          {error && <div className="error">{error}</div>}
        </form>

        {/* ---------- Results ---------- */}
        <div>
          {!result && !loading && (
            <div className="card">
              <div className="section" style={{ marginBottom: 0 }}>
                <h2>How it works</h2>
                <div className="how">
                  {HOW.map((s, i) => (
                    <div className="step" key={s.t}>
                      <div className="ic">{s.ic}</div><b>{i + 1}. {s.t}</b><span>{s.d}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {loading && !result && (<><div className="skel" /><div className="skel" /><div className="skel" /></>)}

          {result && (
            <div style={{ opacity: loading ? 0.5 : 1, transition: '.2s' }}>
              {/* 1. Found */}
              <div className="section">
                <h2><span className="num">1</span>What we found in your room</h2>
                <div className="card found">
                  <div>
                    <div className="imgwrap">
                      <img src={preview} alt="your room"
                           onLoad={(e) => setImgSize({ w: e.target.naturalWidth, h: e.target.naturalHeight })} />
                      {imgSize && p.detections.map((d, i) => {
                        const c = d.counted ? '#16a34a' : '#f59e0b'
                        const [x1, y1, x2, y2] = d.bbox
                        return (
                          <div key={i} className="bbox" style={{
                            left: `${(x1 / imgSize.w) * 100}%`, top: `${(y1 / imgSize.h) * 100}%`,
                            width: `${((x2 - x1) / imgSize.w) * 100}%`, height: `${((y2 - y1) / imgSize.h) * 100}%`,
                            border: `3px ${d.counted ? 'solid' : 'dashed'} ${c}`,
                          }}>
                            <span style={{ background: c }}>{d.label} {Math.round(d.confidence * 100)}%</span>
                          </div>
                        )
                      })}
                    </div>
                  </div>
                  <div>
                    <p className="sub">Detected furniture</p>
                    {p.detections.length === 0 && <span className="tag">none of the catalog types</span>}
                    {p.detections.map((d, i) => (
                      <span key={i} className={`tag ${d.counted ? 'ok' : 'warn'}`}
                            title={d.not_counted_reason || ''}>
                        {d.label} {Math.round(d.confidence * 100)}%
                        {d.counted ? ' ✓' : ` · ${d.not_counted_reason || 'not counted'}`}
                      </span>
                    ))}

                    <p className="sub" style={{ marginTop: 14 }}>Dominant colours</p>
                    <div className="swatches">
                      {p.dominant_colors.map((c) => (
                        <div className="sw" key={c}><div style={{ background: c }} />{c}</div>
                      ))}
                    </div>

                    <p className="sub" style={{ marginTop: 14 }}>Style</p>
                    <span className="tag miss" style={{ textTransform: 'capitalize' }}>
                      {result.style_used.source === 'user'
                        ? `${result.style_used.label} · chosen by you`
                        : p.style.label}
                    </span>
                  </div>
                </div>
                {p.image_quality?.warnings.length > 0 && (
                  <div className="notice warn">{p.image_quality.warnings.map((w) => <div key={w}>⚠ {w}</div>)}</div>
                )}
                {result.style_used.source !== 'user' && p.needs_confirmation && (
                  <div className="notice info">
                    We're not sure of your room's style. Pick one under "Preferred style" for better matches.
                  </div>
                )}
              </div>

              {/* 2. Missing */}
              <div className="section">
                <h2><span className="num">2</span>What your room is missing</h2>
                <div className="card">
                  {result.gap_analysis.upgrade_mode
                    ? 'Your room already has every catalog category, so these are upgrade suggestions.'
                    : result.gap_analysis.missing_categories.map((c) => (
                        <span key={c} className="tag miss" style={{ textTransform: 'capitalize' }}>{c}</span>
                      ))}
                </div>
              </div>

              {/* 3. Picks */}
              <div className="section">
                <h2><span className="num">3</span>Optimal picks within {inr(budget)}</h2>
                {bs && (
                  <div className="card">
                    <div className="budget-top">
                      <span><b>{inr(bs.used)}</b> of {inr(bs.budget)} used ({bs.percent_used}%)</span>
                      <span><b>{inr(bs.left)}</b> left</span>
                    </div>
                    <div className="bar"><div style={{ width: `${Math.min(100, bs.percent_used)}%` }} /></div>
                    <div className="hint">The optimizer picks the best-matching set; it doesn't try to spend the whole budget.</div>
                  </div>
                )}
                {items.length === 0 ? (
                  <div className="card" style={{ marginTop: 14 }}>No item fits this budget. Try a higher budget.</div>
                ) : (
                  <div className="grid">
                    {items.map((item) => (
                      <div key={item.item_id} className="card prod">
                        <div className="pic">
                          <span className="pill">{item.category}</span>
                          {item.image && <img src={`${API_URL}${item.image}`} alt={item.name} />}
                        </div>
                        <div className="body">
                          <h3>{item.name}</h3>
                          <div className="row">
                            <span className="price">{inr(item.price)}</span>
                            <div className="match">
                              Match {Math.round((item.score / maxScore) * 100)}%
                              <div className="mbar"><div style={{ width: `${(item.score / maxScore) * 100}%` }} /></div>
                            </div>
                          </div>
                          <div className="meta">
                            {[item.material && `${item.material}`, item.item_room_type && `for ${item.item_room_type}`]
                              .filter(Boolean).join(' · ')}
                          </div>
                          <div className="why">{item.explanation}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* 4. Comparison */}
              <div className="section">
                <h2><span className="num">4</span>DP Optimal vs Greedy</h2>
                <div className="card">
                  <div className="cmp">
                    <div className={`box ${dp.total_score >= gr.total_score ? 'win' : ''}`}>
                      <h4>DP Optimal</h4>
                      <div className="big">{dp.total_score}</div>
                      <div className="meta">total match score · {inr(dp.total_price)} · {dp.items} items</div>
                    </div>
                    <div className="box">
                      <h4>Greedy baseline</h4>
                      <div className="big">{gr.total_score}</div>
                      <div className="meta">total match score · {inr(gr.total_price)} · {gr.items} items</div>
                    </div>
                  </div>
                  <div className="verdict">
                    {dp.total_score > gr.total_score
                      ? `✅ DP found a better set (+${(dp.total_score - gr.total_score).toFixed(3)} match score).`
                      : 'Both methods found the same quality here. DP pulls ahead when the budget forces trade-offs.'}
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
