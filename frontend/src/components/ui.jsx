import { useRef, useState } from 'react'

// One small icon set (24px outline, 2px stroke) so every icon looks the same.
const P = {
  upload: 'M12 16V4m0 0L7 9m5-5 5 5M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3',
  check: 'M5 12.5l4.5 4.5L19 7.5',
  plus: 'M12 5v14M5 12h14', minus: 'M5 12h14',
  reset: 'M4 12a8 8 0 1 0 3-6.2M4 4v4h4',
  full: 'M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5',
  eye: 'M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12zm10 3a3 3 0 1 0 0-6 3 3 0 0 0 0 6z',
  arrow: 'M5 12h14m-5-5 5 5-5 5', home: 'M4 11l8-7 8 7v8a1 1 0 0 1-1 1h-4v-6H9v6H5a1 1 0 0 1-1-1z',
  alert: 'M12 8v5m0 3.5v.01M10.3 3.9 2.6 17.5A2 2 0 0 0 4.3 20.5h15.4a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z',
}
export const Icon = ({ n, size = 18 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={P[n]} /></svg>
)

export const STEPS = ['Upload room', 'Analyze', 'Detect objects', 'Recommendations', 'Visualize']

// The step comes from the real app state (set in App.jsx), never from a timer.
export function StepIndicator({ step }) {
  return (
    <div className="steps" aria-label={`Step ${step} of ${STEPS.length}: ${STEPS[step - 1]}`}>
      <div className="steps-label">Step {step} of {STEPS.length} <span>·</span> {STEPS[step - 1]}</div>
      <ol>{STEPS.map((t, i) => <li key={t} className={i + 1 < step ? 'done' : i + 1 === step ? 'now' : ''}><i>{i + 1 < step ? <Icon n="check" size={12} /> : i + 1}</i><span>{t}</span></li>)}</ol>
    </div>
  )
}

// Large image with zoom, fullscreen and (optional) clickable detection boxes.
export function ImageViewer({ src, alt, boxes = [], showBoxes = true, activeId, onSelect }) {
  const [z, setZ] = useState(1), [nat, setNat] = useState(null), box = useRef(null)
  const full = () => (document.fullscreenElement ? document.exitFullscreen() : box.current?.requestFullscreen?.())
  return (
    <div className="viewer" ref={box}>
      <div className="viewer-bar" role="toolbar" aria-label="Image controls">
        <button type="button" aria-label="Zoom in" onClick={() => setZ((v) => Math.min(3, +(v + 0.25).toFixed(2)))}><Icon n="plus" /></button>
        <button type="button" aria-label="Zoom out" onClick={() => setZ((v) => Math.max(1, +(v - 0.25).toFixed(2)))}><Icon n="minus" /></button>
        <button type="button" aria-label="Reset zoom" onClick={() => setZ(1)}><Icon n="reset" /></button>
        <button type="button" aria-label="Fullscreen" onClick={full}><Icon n="full" /></button>
      </div>
      <div className="viewer-scroll"><div className="viewer-stage" style={{ width: `${z * 100}%` }}>
        <img src={src} alt={alt} onLoad={(e) => setNat({ w: e.target.naturalWidth, h: e.target.naturalHeight })} draggable="false" />
        {nat && showBoxes && boxes.map((b) => {
          const [x1, y1, x2, y2] = b.bbox
          return (
            <button key={b.id} type="button" className={`dbox ${activeId === b.id ? 'on' : ''}`} onClick={() => onSelect?.(b.id)}
                    aria-pressed={activeId === b.id} aria-label={`${b.label}, ${Math.round(b.confidence * 100)}% confidence`}
                    style={{ left: `${(x1 / nat.w) * 100}%`, top: `${(y1 / nat.h) * 100}%`, width: `${((x2 - x1) / nat.w) * 100}%`, height: `${((y2 - y1) / nat.h) * 100}%` }}>
              <span>{b.label} · {Math.round(b.confidence * 100)}%</span>
            </button>
          )
        })}
      </div></div>
    </div>
  )
}

// Drag the handle to compare two real photos (original vs cleaned).
export function BeforeAfter({ before, after, labels = ['Original', 'Cleaned'] }) {
  const [p, setP] = useState(50)
  return (
    <div className="ba2">
      <img src={after} alt={labels[1]} draggable="false" />
      <div className="ba2-top" style={{ clipPath: `inset(0 ${100 - p}% 0 0)` }}><img src={before} alt={labels[0]} draggable="false" /></div>
      <span className="ba2-tag l">{labels[0]}</span><span className="ba2-tag r">{labels[1]}</span>
      <div className="ba2-line" style={{ left: `${p}%` }}><i /></div>
      <input type="range" min="0" max="100" value={p} onChange={(e) => setP(+e.target.value)} aria-label="Compare original and cleaned room" />
    </div>
  )
}

// Honest loading state: the backend answers in one request, so we show what is running (no fake ticks).
export function LoadingState() {
  return (
    <div className="stack">
      <div className="card loading">
        <div className="pulse" aria-hidden="true" />
        <div><h2>Analyzing your room…</h2>
          <p>Reading the photo, detecting furniture and colours, measuring the room, and matching furniture to your budget. This usually takes a few seconds.</p></div>
      </div>
      <div className="grid">{[0, 1, 2].map((k) => <div key={k} className="card skel"><div className="sk pic" /><div className="sk line" /><div className="sk line short" /></div>)}</div>
    </div>
  )
}

export function ErrorState({ message, onRetry }) {
  return (
    <div className="card errorstate" role="alert">
      <Icon n="alert" size={26} />
      <h2>Something went wrong while analyzing your image.</h2>
      <p>{message}</p>
      <button type="button" className="btn small" onClick={onRetry}>Try again</button>
    </div>
  )
}
