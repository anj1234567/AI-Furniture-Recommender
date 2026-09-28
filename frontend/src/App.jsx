import { useState } from 'react'

// Track C owns this file. Talks to backend/api/main.py's /analyze endpoint.

const API_URL = 'http://localhost:8000'

const box = { padding: '1rem', background: '#f5f5f5', borderRadius: 8, marginBottom: '1rem' }

export default function App() {
  const [photo, setPhoto] = useState(null)
  const [preview, setPreview] = useState(null)
  const [imgSize, setImgSize] = useState(null)
  const [budget, setBudget] = useState('')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  async function handleSubmit(e) {
    e.preventDefault()
    if (!photo || !budget) return
    setLoading(true)
    setError(null)

    const formData = new FormData()
    formData.append('photo', photo)
    formData.append('budget', budget)
    formData.append('lat', '18.5204') // Pune placeholder
    formData.append('lng', '73.8567')

    try {
      const res = await fetch(`${API_URL}/analyze`, { method: 'POST', body: formData })
      if (!res.ok) {
        let msg = `Request failed: ${res.status}`
        try { const j = await res.json(); if (j.detail) msg = j.detail } catch { /* keep default */ }
        throw new Error(msg)
      }
      setPreview(URL.createObjectURL(photo))
      setImgSize(null)
      setResult(await res.json())
    } catch (err) {
      setResult(null)
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const p = result?.perception
  const items = result?.recommendation.selected_items ?? []
  const minConf = result?.gap_analysis.min_confidence ?? 0.6

  return (
    <div style={{ maxWidth: 760, margin: '2rem auto', fontFamily: 'sans-serif' }}>
      <h1>AI Furniture Recommender</h1>

      <form onSubmit={handleSubmit}>
        <div>
          <label>Room photo: </label>
          <input type="file" accept="image/*" onChange={(e) => setPhoto(e.target.files[0])} />
        </div>
        <div style={{ marginTop: '0.5rem' }}>
          <label>Total budget (₹): </label>
          <input type="number" value={budget} onChange={(e) => setBudget(e.target.value)} />
        </div>
        <button type="submit" disabled={loading} style={{ marginTop: '1rem' }}>
          {loading ? 'Analyzing…' : 'Get recommendations'}
        </button>
      </form>

      {error && <p style={{ color: 'red' }}>{error}</p>}

      {result && (
        <div style={{ marginTop: '2rem' }}>
          <h2>1. What we found in your room</h2>
          <div style={box}>
            {/* Uploaded photo with detection boxes drawn on it */}
            <div style={{ position: 'relative', display: 'inline-block', maxWidth: '100%' }}>
              <img
                src={preview}
                alt="your room"
                onLoad={(e) => setImgSize({ w: e.target.naturalWidth, h: e.target.naturalHeight })}
                style={{ maxWidth: '100%', maxHeight: 340, display: 'block', borderRadius: 6 }}
              />
              {imgSize &&
                p.detections.map((d, i) => {
                  const low = !d.counted
                  const [x1, y1, x2, y2] = d.bbox
                  return (
                    <div
                      key={i}
                      style={{
                        position: 'absolute',
                        left: `${(x1 / imgSize.w) * 100}%`,
                        top: `${(y1 / imgSize.h) * 100}%`,
                        width: `${((x2 - x1) / imgSize.w) * 100}%`,
                        height: `${((y2 - y1) / imgSize.h) * 100}%`,
                        border: `3px ${low ? 'dashed #f59e0b' : 'solid #16a34a'}`,
                        boxSizing: 'border-box',
                      }}
                    >
                      <span style={{ background: low ? '#f59e0b' : '#16a34a', color: '#fff', fontSize: 12, padding: '1px 5px' }}>
                        {d.label} {Math.round(d.confidence * 100)}%
                      </span>
                    </div>
                  )
                })}
            </div>

            {p.image_quality?.warnings.length > 0 && (
              <div style={{ marginTop: '0.75rem', padding: '0.5rem 0.75rem', background: '#fef3c7', borderRadius: 6, fontSize: 14 }}>
                {p.image_quality.warnings.map((w) => <div key={w}>⚠ {w}</div>)}
              </div>
            )}
            <div style={{ marginTop: '0.75rem' }}>
              <strong>Detected furniture:</strong>{' '}
              {p.detections.length === 0
                ? 'none of the catalog furniture types'
                : p.detections
                    .map((d) => `${d.label} (${Math.round(d.confidence * 100)}%${d.counted ? '' : `, ${d.not_counted_reason || 'not counted'}, not counted`})`)
                    .join(', ')}
            </div>
            <div style={{ marginTop: '0.75rem' }}>
              <strong>Dominant colours:</strong>
              <div style={{ display: 'flex', gap: 8, marginTop: 6 }}>
                {p.dominant_colors.map((c) => (
                  <div key={c} style={{ textAlign: 'center', fontSize: 12 }}>
                    <div style={{ width: 48, height: 48, background: c, border: '1px solid #ccc', borderRadius: 6 }} />
                    {c}
                  </div>
                ))}
              </div>
            </div>
            <div style={{ marginTop: '0.75rem' }}>
              <strong>Style:</strong> {p.style.label}
              {p.needs_confirmation && ' (style model not trained yet — needs user confirmation)'}
            </div>
          </div>

          <h2>2. What your room is missing</h2>
          <div style={box}>
            {result.gap_analysis.upgrade_mode
              ? 'Your room already has every catalog category, so these are upgrade suggestions.'
              : `Missing: ${result.gap_analysis.missing_categories.join(', ')}`}
          </div>

          <h2>3. Optimal picks within ₹{budget}</h2>
          {items.length === 0 ? (
            <p>No item fits this budget. Try a higher budget.</p>
          ) : (
            items.map((item) => (
              <div key={item.item_id} style={{ ...box, display: 'flex', gap: '1rem', alignItems: 'center' }}>
                {item.image && (
                  <img src={`${API_URL}${item.image}`} alt={item.name} width={120} height={120}
                       style={{ objectFit: 'cover', borderRadius: 6, background: '#fff' }} />
                )}
                <div>
                  <strong>{item.name}</strong> — ₹{item.price} (match score {item.score})
                  <p style={{ margin: '4px 0 0' }}>{item.explanation}</p>
                </div>
              </div>
            ))
          )}

          <h2>4. DP Optimal vs Greedy</h2>
          <div style={{ ...box, display: 'flex', gap: '3rem' }}>
            <div>
              <strong>DP Optimal</strong><br />
              Cost: ₹{result.comparison.dp_optimal.total_price} ({result.comparison.dp_optimal.items} items)<br />
              Total match score: {result.comparison.dp_optimal.total_score}
            </div>
            <div>
              <strong>Greedy baseline</strong><br />
              Cost: ₹{result.comparison.greedy.total_price} ({result.comparison.greedy.items} items)<br />
              Total match score: {result.comparison.greedy.total_score}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
