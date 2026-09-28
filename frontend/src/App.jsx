import { useState } from 'react'

// Track C owns this file. Talks to backend/api/main.py's /analyze endpoint.

const API_URL = 'http://localhost:8000'

const box = { padding: '1rem', background: '#f5f5f5', borderRadius: 8, marginBottom: '1rem' }

export default function App() {
  const [photo, setPhoto] = useState(null)
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
      if (!res.ok) throw new Error(`Request failed: ${res.status}`)
      setResult(await res.json())
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const p = result?.perception
  const items = result?.recommendation.selected_items ?? []

  return (
    <div style={{ maxWidth: 720, margin: '2rem auto', fontFamily: 'sans-serif' }}>
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
            <strong>Detected furniture:</strong>{' '}
            {p.detections.length === 0
              ? 'none of the catalog furniture types'
              : p.detections.map((d) => {
                  const low = d.confidence < result.gap_analysis.min_confidence
                  return `${d.label} (${Math.round(d.confidence * 100)}%${low ? ', low confidence, not counted' : ''})`
                }).join(', ')}
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
            <ul>
              {items.map((item) => (
                <li key={item.item_id} style={{ marginBottom: '1rem' }}>
                  <strong>{item.name}</strong> — ₹{item.price} (match score {item.score})
                  <p style={{ margin: '4px 0' }}>{item.explanation}</p>
                </li>
              ))}
            </ul>
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
