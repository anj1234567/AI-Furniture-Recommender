import { useState } from 'react'
import { ImageViewer, Icon } from './ui'

const CAT = { couch: 'sofa' }   // detector label -> catalog category (other labels map to themselves)

export default function AnalysisPanel({ result, preview, onOpenCategory }) {
  const p = result.perception
  const dets = p.detections.map((d, i) => ({ ...d, id: i }))
  const [show, setShow] = useState(true)
  const [sel, setSel] = useState(null)
  const cur = sel != null ? dets[sel] : null
  const cat = cur ? (CAT[cur.label] || cur.label) : null
  const recs = cat ? result.recommendation.selected_items.filter((i) => String(i.category).toLowerCase() === cat) : []
  const missing = result.gap_analysis.missing_categories
  return (
    <div className="split">
      <div className="card pad">
        <div className="head">
          <div><h2>Detected objects</h2><p className="muted">Click a box or an item to see what we suggest for it.</p></div>
          <label className="switch"><input type="checkbox" checked={show} onChange={(e) => setShow(e.target.checked)} /><span>Show detected objects</span></label>
        </div>
        <ImageViewer src={preview} alt="Your room with detected furniture" boxes={dets} showBoxes={show} activeId={sel} onSelect={setSel} />
        {p.image_quality?.warnings.length > 0 && <div className="notice warn">{p.image_quality.warnings.join(' ')}</div>}
      </div>
      <aside className="stack">
        <div className="card pad">
          <h3>Found in your room</h3>
          {dets.length === 0 ? <p className="muted">No furniture was detected.</p> : (
            <ul className="objlist">
              {dets.map((d) => (
                <li key={d.id}><button type="button" className={sel === d.id ? 'on' : ''} onClick={() => setSel(d.id)}>
                  <Icon n="check" size={14} /><span className="cap">{d.label}</span><b>{Math.round(d.confidence * 100)}%</b>
                </button></li>
              ))}
            </ul>
          )}
          {cur && (
            <div className="objdetail">
              <b className="cap">{cur.label}</b> detected with {Math.round(cur.confidence * 100)}% confidence.
              {recs.length > 0
                ? <><p>We recommend <b>{recs[0].name}</b>{recs.length > 1 ? ` and ${recs.length - 1} more` : ''} in this category.</p>
                    <button type="button" className="btn small" onClick={() => onOpenCategory(cat)}>View {cat} recommendations <Icon n="arrow" size={15} /></button></>
                : <p>Your room already has this, so we are not recommending another one.</p>}
            </div>
          )}
        </div>
        <div className="card pad">
          <h3>Still needed</h3>
          {result.gap_analysis.upgrade_mode ? <p className="muted">Your room has everything it needs, so these are upgrades.</p>
            : missing.length === 0 ? <p className="muted">Nothing is missing.</p>
            : <div className="chiprow">{missing.map((c) => <button type="button" key={c} className="tagbtn cap" onClick={() => onOpenCategory(String(c).toLowerCase())}>{c}</button>)}</div>}
          <h3 style={{ marginTop: 18 }}>Room colours</h3>
          <div className="swatches">{p.dominant_colors.map((c) => <div className="sw" key={c} title={c}><div style={{ background: c }} />{c}</div>)}</div>
        </div>
        <div className="card pad">
          <h3>Room measurements</h3>
          <div className="facts">
            <div><b>{result.space ? `${result.space.room_w_m} × ${result.space.room_l_m} m` : '—'}</b><span>width × length{result.space?.source === 'estimated' ? ' (estimate)' : ''}</span></div>
            <div><b>{result.space ? `${result.space.usable_m2} m²` : '—'}</b><span>free floor space</span></div>
            <div><b>{result.scene?.ceiling_height_m ? `${result.scene.ceiling_height_m} m` : '—'}</b><span>ceiling height</span></div>
          </div>
        </div>
      </aside>
    </div>
  )
}
