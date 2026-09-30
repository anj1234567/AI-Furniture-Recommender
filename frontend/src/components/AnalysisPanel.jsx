import { useState } from 'react'

export default function AnalysisPanel({ result, preview }) {
  const [img, setImg] = useState(null)
  const p = result.perception
  return (
    <div className="stack">
      <div className="card found">
        <div className="imgwrap">
          <img src={preview} alt="your room" onLoad={(e) => setImg({ w: e.target.naturalWidth, h: e.target.naturalHeight })} />
          {img && p.detections.map((d, i) => {
            const c = d.counted ? '#0f766e' : '#d97706'
            const [x1, y1, x2, y2] = d.bbox
            return (
              <div key={i} className="bbox" style={{
                left: `${(x1 / img.w) * 100}%`, top: `${(y1 / img.h) * 100}%`,
                width: `${((x2 - x1) / img.w) * 100}%`, height: `${((y2 - y1) / img.h) * 100}%`,
                border: `3px ${d.counted ? 'solid' : 'dashed'} ${c}`,
              }}><span style={{ background: c }}>{d.label} {Math.round(d.confidence * 100)}%</span></div>
            )
          })}
        </div>
        <div>
          <p className="sub">Furniture already in the room</p>
          {p.detections.length === 0 && <span className="tag">none found</span>}
          {p.detections.map((d, i) => (
            <span key={i} className={`tag ${d.counted ? 'ok' : 'warn'}`} title={d.not_counted_reason || ''}>
              {d.label} {Math.round(d.confidence * 100)}%{d.counted ? '' : ` · ${d.not_counted_reason || 'not counted'}`}
            </span>
          ))}
          <p className="sub gap">Colours</p>
          <div className="swatches">
            {p.dominant_colors.map((c) => <div className="sw" key={c}><div style={{ background: c }} />{c}</div>)}
          </div>
          <p className="sub gap">Style</p>
          <span className="tag miss cap">
            {result.style_used.source === 'user' ? `${result.style_used.label} (your choice)` : p.style.label}
          </span>
          <p className="sub gap">Missing from the room</p>
          {result.gap_analysis.upgrade_mode
            ? <span className="hint">Every catalog category is already present, so these are upgrades.</span>
            : result.gap_analysis.missing_categories.map((c) => <span key={c} className="tag miss cap">{c}</span>)}
        </div>
      </div>
      <div className="card">
        <p className="sub">Measured from your photo</p>
        <div className="facts">
          <div><b>{result.space ? `${result.space.room_w_m} × ${result.space.room_l_m} m` : 'unknown'}</b><span>room width × length{result.space?.source === 'estimated' ? ' (estimate)' : ''}</span></div>
          <div><b>{result.scene?.ceiling_height_m ? `${result.scene.ceiling_height_m} m` : 'not visible'}</b><span>ceiling height</span></div>
          <div><b>{result.scene?.cam_height_m} m</b><span>camera height ({result.scene?.floor_source === 'depth' ? 'measured' : 'assumed'})</span></div>
          <div><b>{result.space ? `${result.space.usable_m2} m²` : 'unknown'}</b><span>free floor space</span></div>
          <div><b>{p.detector}</b><span>furniture detector</span></div>
        </div>
      </div>
      {p.image_quality?.warnings.length > 0 && (
        <div className="notice warn">{p.image_quality.warnings.map((w) => <div key={w}>{w}</div>)}</div>
      )}
      {result.style_used.source !== 'user' && p.needs_confirmation && (
        <div className="notice info">We can't tell your room's style yet. Choose one under More options for better matches.</div>
      )}
    </div>
  )
}
