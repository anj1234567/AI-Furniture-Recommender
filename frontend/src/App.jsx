import { useState } from 'react'

// Track C owns this file. Talks to backend/api/main.py's /analyze endpoint.
// Works end-to-end right now against the backend's mocked layers.

const API_URL = 'http://localhost:8000'

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
    // Placeholder coords — swap for navigator.geolocation once that's wired up
    formData.append('lat', '19.0760')
    formData.append('lng', '72.8777')

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

  return (
    <div style={{ maxWidth: 640, margin: '2rem auto', fontFamily: 'sans-serif' }}>
      <h1>AI Furniture Recommender</h1>

      <form onSubmit={handleSubmit}>
        <div>
          <label>Room photo: </label>
          <input type="file" accept="image/*" onChange={(e) => setPhoto(e.target.files[0])} />
        </div>
        <div style={{ marginTop: '0.5rem' }}>
          <label>Total budget: </label>
          <input type="number" value={budget} onChange={(e) => setBudget(e.target.value)} />
        </div>
        <button type="submit" disabled={loading} style={{ marginTop: '1rem' }}>
          {loading ? 'Analyzing…' : 'Get recommendations'}
        </button>
      </form>

      {error && <p style={{ color: 'red' }}>{error}</p>}

      {result && (
        <div style={{ marginTop: '2rem' }}>
          <h2>Detected style: {result.perception.style.label}</h2>
          <h3>Recommended items (total: {result.recommendation.total_price})</h3>
          <ul>
            {result.recommendation.selected_items.map((item) => (
              <li key={item.item_id} style={{ marginBottom: '1rem' }}>
                <strong>{item.category}</strong> — ₹{item.price}
                <p>{item.explanation}</p>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
