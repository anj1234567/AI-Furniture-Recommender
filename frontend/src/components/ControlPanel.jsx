import { useRef, useState } from 'react'
import { inr } from '../lib/api'

export default function ControlPanel({ f, options, loading, error, onSubmit }) {
  const fileRef = useRef(null)
  const [over, setOver] = useState(false)
  return (
    <form className="card side" onSubmit={(e) => { e.preventDefault(); onSubmit() }}>
      <div className="field">
        <label>Room photo</label>
        <div className={`drop ${over ? 'over' : ''}`} onClick={() => fileRef.current.click()}
             onDragOver={(e) => { e.preventDefault(); setOver(true) }} onDragLeave={() => setOver(false)}
             onDrop={(e) => { e.preventDefault(); setOver(false); f.pickFile(e.dataTransfer.files[0]) }}>
          {f.preview && <img src={f.preview} alt="selected room" />}
          {f.photo ? f.photo.name : 'Click or drag a photo here'}
          <input ref={fileRef} type="file" accept="image/*" onChange={(e) => f.pickFile(e.target.files[0])} />
        </div>
      </div>

      <div className="field">
        <label>Budget</label>
        <div className="money">
          <span>₹</span>
          <input className="input" type="number" min="0" value={f.budget}
                 onChange={(e) => f.setBudget(e.target.value)} placeholder="e.g. 40000" />
        </div>
        <div className="chips">
          {[10000, 25000, 40000, 75000].map((v) => (
            <button type="button" key={v} className="chip" onClick={() => f.setBudget(String(v))}>{inr(v)}</button>
          ))}
        </div>
      </div>

      <details className="more">
        <summary>More options</summary>
        <div className="field">
          <label>Room type</label>
          <select className="select" value={f.roomType} onChange={(e) => f.changeChoice(f.style, e.target.value)}>
            <option value="">Not sure</option>
            {options.room_types.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </div>
        <div className="field">
          <label>Preferred style</label>
          <select className="select" value={f.style} onChange={(e) => f.changeChoice(e.target.value, f.roomType)}>
            <option value="">Not sure</option>
            {options.styles.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </div>
        <div className="field">
          <label>Room size in metres</label>
          <div className="two">
            <input className="input" type="number" min="1" step="0.1" value={f.roomW} placeholder="Width"
                   onChange={(e) => { f.setRoomW(e.target.value); f.setRoomAuto(false) }} />
            <input className="input" type="number" min="1" step="0.1" value={f.roomL} placeholder="Length"
                   onChange={(e) => { f.setRoomL(e.target.value); f.setRoomAuto(false) }} />
          </div>
          <div className="hint">
            {f.roomAuto ? 'Estimated from your photo. Type the real size and run again if it looks wrong.'
                        : 'Leave empty and we estimate it from your photo.'}
          </div>
        </div>
      </details>

      <button className="btn" type="submit" disabled={loading}>
        {loading ? <><span className="spin" />Analysing…</> : 'Get recommendations'}
      </button>
      {error && <div className="error">{error}</div>}
    </form>
  )
}
