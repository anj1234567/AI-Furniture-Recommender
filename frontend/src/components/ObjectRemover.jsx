import { useEffect, useRef, useState } from 'react'
import { API_URL } from '../lib/api'
import { BeforeAfter } from './ui'

const MAX_MASK = 1600      // painted mask is kept at most this many pixels on its long side

// "Clear the room": pick detected objects and/or paint over anything else, then the backend
// fills the area in (AI inpainting) and the whole room is analysed again on the cleaned photo.
export default function ObjectRemover({ result, preview, photo, origPreview, edited, info, onCleaned, onRestore, busy }) {
  const dets = result.perception.detections
  const [sel, setSel] = useState([])
  const [brush, setBrush] = useState(false)
  const [size, setSize] = useState(36)
  const [working, setWorking] = useState(false)
  const [err, setErr] = useState(null)
  const [nat, setNat] = useState(null)
  const [hasPaint, setHasPaint] = useState(false)
  const cv = useRef(null), drawing = useRef(false), last = useRef(null)

  const clearPaint = () => { const c = cv.current; if (c) c.getContext('2d').clearRect(0, 0, c.width, c.height); setHasPaint(false) }
  useEffect(() => { setSel([]); setErr(null); clearPaint() }, [preview])   // eslint-disable-line react-hooks/exhaustive-deps

  const onImg = (e) => {
    const w = e.target.naturalWidth, h = e.target.naturalHeight, s = Math.min(1, MAX_MASK / Math.max(w, h))
    setNat({ w, h })
    const c = cv.current; c.width = Math.round(w * s); c.height = Math.round(h * s)
  }
  const at = (e) => {
    const c = cv.current, r = c.getBoundingClientRect()
    return [((e.clientX - r.left) * c.width) / r.width, ((e.clientY - r.top) * c.height) / r.height]
  }
  const stroke = (from, to) => {
    const c = cv.current, ctx = c.getContext('2d'), r = c.getBoundingClientRect()
    ctx.strokeStyle = 'rgba(239,68,68,.6)'; ctx.fillStyle = 'rgba(239,68,68,.6)'; ctx.lineCap = 'round'; ctx.lineJoin = 'round'
    ctx.lineWidth = (size * c.width) / r.width
    ctx.beginPath(); ctx.moveTo(...from); ctx.lineTo(...to); ctx.stroke()
  }
  const down = (e) => { if (!brush) return; drawing.current = true; last.current = at(e); stroke(last.current, last.current); setHasPaint(true); e.currentTarget.setPointerCapture?.(e.pointerId) }
  const move = (e) => { if (!drawing.current) return; const p = at(e); stroke(last.current, p); last.current = p }
  const up = () => { drawing.current = false }

  const maskBlob = () => new Promise((resolve) => {
    const c = cv.current, d = c.getContext('2d').getImageData(0, 0, c.width, c.height)
    const out = new ImageData(c.width, c.height)
    for (let i = 0; i < c.width * c.height; i++) { const v = d.data[4 * i + 3] > 20 ? 255 : 0; out.data[4 * i] = out.data[4 * i + 1] = out.data[4 * i + 2] = v; out.data[4 * i + 3] = 255 }
    const oc = document.createElement('canvas'); oc.width = c.width; oc.height = c.height
    oc.getContext('2d').putImageData(out, 0, 0); oc.toBlob(resolve, 'image/png')
  })

  const toggle = (i) => setSel((s) => (s.includes(i) ? s.filter((x) => x !== i) : [...s, i]))
  const canRun = (sel.length > 0 || hasPaint) && !working && !busy

  async function run() {
    setWorking(true); setErr(null)
    try {
      const fd = new FormData()
      fd.append('photo', photo)
      fd.append('boxes', JSON.stringify(sel.map((i) => dets[i].bbox)))
      if (hasPaint) fd.append('mask', await maskBlob(), 'mask.png')
      const res = await fetch(`${API_URL}/inpaint`, { method: 'POST', body: fd })
      if (!res.ok) {
        let msg = `Request failed: ${res.status}`
        try { const j = await res.json(); if (j.detail) msg = j.detail } catch { /* keep default */ }
        throw new Error(msg)
      }
      const method = res.headers.get('X-Inpaint-Method')
      const blob = await res.blob()
      onCleaned(new File([blob], `room_clean_${Date.now()}.jpg`, { type: 'image/jpeg' }), method)
    } catch (e) {
      setErr(e.message === 'Failed to fetch' ? 'Cannot reach the backend. Is it running on port 8000?' : e.message)
    } finally { setWorking(false) }
  }

  return (
    <div className="stack">
      <div className="card">
        <b>Clear your room</b>
        <div className="hint" style={{ marginTop: 2 }}>
          Click a detected object, or switch on the brush and paint over anything else (clothes, boxes, a mattress). We fill the space in
          and analyse the room again, so a removed bed is recommended again and the 3D views show the empty floor.
        </div>
      </div>

      <div className="card">
        <div className="rm-stage" style={nat ? { aspectRatio: `${nat.w} / ${nat.h}` } : undefined}>
          <img src={preview} alt="your room" onLoad={onImg} draggable="false" />
          {nat && !brush && dets.map((d, i) => {
            const [x1, y1, x2, y2] = d.bbox, on = sel.includes(i)
            return (
              <button key={i} type="button" className={`rm-box ${on ? 'on' : ''}`} aria-pressed={on} onClick={() => toggle(i)}
                      style={{ left: `${(x1 / nat.w) * 100}%`, top: `${(y1 / nat.h) * 100}%`, width: `${((x2 - x1) / nat.w) * 100}%`, height: `${((y2 - y1) / nat.h) * 100}%` }}>
                <span>{on ? '✕ ' : ''}{d.label} {Math.round(d.confidence * 100)}%</span>
              </button>
            )
          })}
          <canvas ref={cv} className={`rm-canvas ${brush ? 'live' : ''}`} onPointerDown={down} onPointerMove={move} onPointerUp={up} onPointerCancel={up} />
          {(working || busy) && <div className="rm-busy"><span className="spin" />{working ? 'Removing objects…' : 'Analysing the new photo…'}</div>}
        </div>

        <div className="rm-tools">
          <div className="btnrow">
            <button type="button" className={`chip ${brush ? 'on' : ''}`} onClick={() => setBrush((b) => !b)}>{brush ? 'Brush on' : 'Brush off'}</button>
            {brush && <label className="rm-size">Size {size}
              <input type="range" min="10" max="120" value={size} onChange={(e) => setSize(Number(e.target.value))} /></label>}
            {hasPaint && <button type="button" className="ghost" onClick={clearPaint}>Clear painting</button>}
            {sel.length > 0 && <button type="button" className="ghost" onClick={() => setSel([])}>Unselect ({sel.length})</button>}
          </div>
          <div className="btnrow">
            <button type="button" className="btn small" disabled={!canRun} onClick={run}>Remove selected</button>
            {edited && <button type="button" className="ghost" disabled={working || busy} onClick={onRestore}>Restore original photo</button>}
          </div>
        </div>
        {dets.length === 0 && !hasPaint && <div className="hint">No furniture was detected, so turn on the brush and paint over what you want removed.</div>}
        {err && <div className="error">{err}</div>}
        {info && (
          <div className={`notice ${info === 'opencv' ? 'warn' : 'info'}`}>
            {info === 'lama'
              ? 'Filled in with LaMa, an AI inpainting model.'
              : 'Filled in with the basic OpenCV method, which is blurry on big objects. The LaMa model (about 200 MB) downloads on first use; check the backend terminal for a message if it did not.'}
          </div>
        )}
      </div>

      {edited && origPreview && (
        <div className="card">
          <div className="sub">Before and after</div>
          <BeforeAfter before={origPreview} after={preview} />
        </div>
      )}
    </div>
  )
}
