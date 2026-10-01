import { autoAssign, harmony, suggestColors } from '../lib/colors'

// Recolour each piece. Suggestions come from the room's own palette (see lib/colors.js),
// and the original product colour is rated against the room so a clash is visible.
export default function ColorPanel({ items, palette, colors, setColors }) {
  const suggestions = suggestColors(palette)
  const set = (cat, hex) => setColors({ ...colors, [cat]: hex })
  const clear = (cat) => { const c = { ...colors }; delete c[cat]; setColors(c) }
  const changed = Object.keys(colors).length > 0
  return (
    <div className="card colorpanel">
      <div className="cp-head">
        <div>
          <b>Colours</b>
          <div className="hint" style={{ marginTop: 2 }}>Pick a colour from your room’s palette, or any colour you like. The 3D views update straight away.</div>
        </div>
        <div className="btnrow">
          <button type="button" className="btn small" onClick={() => setColors(autoAssign(items.map((i) => i.category), palette))}>Match my room</button>
          {changed && <button type="button" className="ghost" onClick={() => setColors({})}>Original colours</button>}
        </div>
      </div>
      <div className="cp-room">
        <span className="muted">Your room:</span>
        {palette.map((c) => <span key={c} className="dot" style={{ background: c }} title={c} />)}
      </div>
      {items.map((it) => {
        const cur = colors[it.category]
        const orig = harmony(it.color_hex, palette)
        const now = cur ? harmony(cur, palette) : orig
        return (
          <div key={it.category} className="cp-row">
            <div className="cp-name">
              <span className="cap"><b>{it.category}</b></span>
              <span className="muted" title={it.name}>{it.name?.length > 34 ? it.name.slice(0, 33) + '…' : it.name}</span>
              <span className={`fit ${now.score == null ? '' : now.score >= 0.7 ? 'good' : now.score >= 0.5 ? 'mid' : 'bad'}`}>
                {now.score == null ? 'original colour unknown' : `${Math.round(now.score * 100)}% fit · ${now.label}`}
              </span>
            </div>
            <div className="cp-swatches" role="group" aria-label={`Colour for ${it.category}`}>
              <button type="button" className={`swatch orig ${!cur ? 'on' : ''}`} style={{ background: it.color_hex || '#ccc' }}
                      title={`Original${it.color_hex ? ' ' + it.color_hex : ''}`} onClick={() => clear(it.category)}><span>orig</span></button>
              {suggestions.map((s) => (
                <button key={s.key} type="button" className={`swatch ${cur === s.hex ? 'on' : ''}`} style={{ background: s.hex }}
                        title={`${s.label} · ${Math.round(s.score * 100)}% fit`} aria-label={s.label} onClick={() => set(it.category, s.hex)} />
              ))}
              <label className="swatch custom" title="Any colour">
                <input type="color" value={cur || it.color_hex || '#888888'} onChange={(e) => set(it.category, e.target.value)} />
                <span>+</span>
              </label>
            </div>
          </div>
        )
      })}
      <div className="hint">Recolouring keeps the model’s shading and texture pattern. It is a visual preview, and the shop may sell other colours.</div>
    </div>
  )
}
