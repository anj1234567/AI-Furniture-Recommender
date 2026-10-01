import { useRef } from 'react'
import { Icon } from './ui'

const PRESETS = [10000, 25000, 40000, 75000]
const inr0 = (n) => '₹' + n.toLocaleString('en-IN')

// dropdown lists can come as plain strings or {value,label} objects; accept both
function roomChoices(list) {
  return (list || [])
    .map((o) => (typeof o === 'string' ? { v: o, l: o } : { v: o.value ?? o.id ?? o.key ?? '', l: o.label ?? o.name ?? o.value ?? '' }))
    .filter((o) => o.v && !/^(any|none|not sure)$/i.test(o.l))
}

export default function ControlPanel({ f, options, loading, error, onSubmit }) {
  const fileRef = useRef(null)
  const rooms = roomChoices(options.room_types)
  const styles = roomChoices(options.styles)
  const typed = f.roomW && f.roomL
  return (
    <aside className="card side">
      <div className="field">
        <label>1. Room photo</label>
        <div className="drop" onClick={() => fileRef.current?.click()}
             onDragOver={(e) => e.preventDefault()}
             onDrop={(e) => { e.preventDefault(); f.pickFile(e.dataTransfer.files?.[0]) }}>
          {f.preview ? <><img src={f.preview} alt="Your room" /><div className="fname">{f.photo?.name}</div><span className="linkbtn">Change image</span></>
            : <div className="dz"><Icon n="upload" size={26} /><b>Upload your room</b><span>or drag and drop your image here</span><small>JPG / PNG / WEBP</small></div>}
          <input id="photo-input" ref={fileRef} type="file" accept="image/*" onChange={(e) => f.pickFile(e.target.files?.[0])} />
        </div>
      </div>

      <div className="field">
        <label htmlFor="budget">2. Budget</label>
        <div className="money"><span>₹</span>
          <input id="budget" className="input" type="number" min="0" inputMode="numeric" value={f.budget} onChange={(e) => f.setBudget(e.target.value)} placeholder="e.g. 25000" /></div>
        <div className="chips">{PRESETS.map((p) => <button key={p} type="button" className="chip" onClick={() => f.setBudget(String(p))}>{inr0(p)}</button>)}</div>
      </div>

      <div className="field">
        <label htmlFor="rt">3. Which room is this?</label>
        <select id="rt" className="select cap" value={f.roomType} onChange={(e) => f.changeRoomType(e.target.value)}>
          <option value="">Not sure</option>
          {rooms.map((o) => <option key={o.v} value={o.v}>{o.l}</option>)}
        </select>
        <div className="hint">{!f.roomType ? 'We will work out the room type from your photo. ' : ''}We only suggest furniture that belongs in this room.</div>
      </div>

      <div className="field">
        <label htmlFor="st">4. Style <span className="muted">(optional)</span></label>
        <select id="st" className="select cap" value={f.style} onChange={(e) => f.changeStyle(e.target.value)}>
          <option value="">Not sure (any style)</option>
          {styles.map((o) => <option key={o.v} value={o.v}>{o.l}</option>)}
        </select>
        <div className="hint">{f.style ? `We only suggest ${f.style} furniture.` : 'No style chosen, so we suggest the best match from every style.'}</div>
      </div>

      <div className="field">
        <label>5. Room size in metres <span className="muted">(optional)</span></label>
        <div className="two">
          <input className="input" type="number" min="0" step="0.1" placeholder={f.est ? String(f.est.w) : 'Width'} value={f.roomW} onChange={(e) => f.setRoomW(e.target.value)} />
          <input className="input" type="number" min="0" step="0.1" placeholder={f.est ? String(f.est.l) : 'Length'} value={f.roomL} onChange={(e) => f.setRoomL(e.target.value)} />
        </div>
        <div className="hint">
          {typed ? 'We use exactly this size.'
            : f.est ? <>Estimated from your photo: {f.est.w} × {f.est.l} m. Type your real size for an exact fit. <button type="button" className="linkbtn" onClick={() => { f.setRoomW(String(f.est.w)); f.setRoomL(String(f.est.l)) }}>Use estimate</button></>
            : 'Leave empty and we estimate it from the photo.'}
        </div>
      </div>

      <button type="button" className="btn" disabled={loading} onClick={onSubmit}>
        {loading ? <><span className="spin" />Analysing…</> : 'Get recommendations'}
      </button>
      {error && <div className="error" role="alert">{error}</div>}
    </aside>
  )
}
