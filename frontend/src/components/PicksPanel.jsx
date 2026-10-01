import { useEffect, useState } from 'react'
import { API_URL, inr } from '../lib/api'

export default function PicksPanel({ d }) {
  const { focusCat, items: allItems, optimal, alts, bs, sp, usedArea, totalScore, anySwapped, budget, picks, setPicks, openSwap, setOpenSwap, setView3d } = d
  const [cat, setCat] = useState('all')
  useEffect(() => { setCat(focusCat || 'all') }, [focusCat])
  const cats = [...new Set(allItems.map((i) => i.category))]
  const items = cat === 'all' ? allItems : allItems.filter((i) => i.category === cat)
  return (
    <div className="stack">
      {bs && (
        <div className="card">
          <div className="meter">
            <div className="budget-top"><span><b>{inr(bs.used)}</b> of {inr(bs.budget)}</span><span className="muted">{inr(bs.left)} left</span></div>
            <div className="bar"><div style={{ width: `${Math.min(100, bs.percent_used)}%` }} /></div>
          </div>
          {sp ? (
            <div className="meter">
              <div className="budget-top"><span><b>{usedArea.toFixed(1)} m²</b> of {sp.usable_m2} m² floor space</span>
                <span className="muted">{Math.max(0, sp.usable_m2 - usedArea).toFixed(1)} m² left</span></div>
              <div className="bar"><div style={{ width: `${sp.usable_m2 > 0 ? Math.min(100, (100 * usedArea) / sp.usable_m2) : 100}%` }} /></div>
            </div>
          ) : <div className="hint">Floor-space check is off because the room size could not be estimated. Type it in the room size field.</div>}
          <div className="hint">
            Total match score {totalScore.toFixed(2)}.
            {sp && ` Room ${sp.room_w_m} × ${sp.room_l_m} m (${sp.source === 'estimated' ? 'estimated from your photo' : 'entered by you'}), ${sp.walkway_pct}% kept free for walking.`}
          </div>
          {anySwapped && <div className="hint warnText">You swapped items, so this is no longer the DP-optimal set. <button type="button" className="linkbtn" onClick={() => setPicks({})}>Reset</button></div>}
        </div>
      )}

      {cats.length > 1 && (
        <div className="chiprow" role="group" aria-label="Filter by category">
          {['all', ...cats].map((c) => <button key={c} type="button" className={`tagbtn cap ${cat === c ? 'on' : ''}`} onClick={() => setCat(c)}>{c === 'all' ? 'All' : c}</button>)}
        </div>
      )}
      {items.length === 0 ? <div className="card">Nothing fits this budget and room. Try a higher budget or a larger room size.</div> : (
        <div className="grid">
          {items.map((item) => {
            const orig = optimal.find((o) => o.category === item.category)
            const choices = [orig, ...(alts[item.category] ?? [])].filter((c) => c.item_id !== item.item_id)
            const open = openSwap === item.category
            return (
              <div key={item.category} className={`card prod ${focusCat === item.category ? 'focus' : ''}`}>
                <div className="pic">
                  <span className="pill">{item.category}</span>
                  {item.image && <img src={`${API_URL}${item.image}`} alt={item.name} />}
                </div>
                <div className="body">
                  <h3 title={item.name}>{item.name}</h3>
                  <div className="row">
                    <span className="price">{inr(item.price)}</span>
                    <div className="match">Match {Math.round(item.score * 100)}%<div className="mbar"><div style={{ width: `${item.score * 100}%` }} /></div></div>
                  </div>
                  <div className="meta">
                    {[item.width_cm && `${item.width_cm} × ${item.depth_cm}${item.height_cm ? ' × ' + item.height_cm : ''} cm`, item.material].filter(Boolean).join(' · ')}
                  </div>
                  <div className="why"><b>Why we recommend this</b>{item.explanation}</div>
                  <div className="btnrow">
                    {item.model_url && <button type="button" className="ghost" onClick={() => setView3d(item)}>View 3D</button>}
                    {choices.length > 0 && <button type="button" className="ghost" onClick={() => setOpenSwap(open ? null : item.category)}>{open ? 'Hide' : `Swap (${choices.length})`}</button>}
                  </div>
                  {open && (
                    <div className="alts">
                      {choices.map((c) => {
                        const money = d.used - item.price + c.price <= budget
                        const space = !sp || usedArea - (item.footprint_m2 || 0) + (c.footprint_m2 || 0) <= sp.usable_m2 + 1e-9
                        return (
                          <button type="button" key={c.item_id} className="alt" disabled={!(money && space)}
                                  onClick={() => { setPicks({ ...picks, [item.category]: c.item_id }); setOpenSwap(null) }}>
                            <div className="altpic">{c.image && <img src={`${API_URL}${c.image}`} alt="" />}</div>
                            <div className="altinfo">
                              <b>{c.name}{c.item_id === orig.item_id ? ' (optimal)' : ''}</b>
                              <span>{inr(c.price)} · match {Math.round(c.score * 100)}%{c.width_cm ? ` · ${c.width_cm} × ${c.depth_cm} cm` : ''}</span>
                              {!(money && space) && <span className="over">{money ? 'no floor space' : 'over budget'}</span>}
                            </div>
                          </button>
                        )
                      })}
                    </div>
                  )}
                  {item.nearby_stores?.length > 0 && (
                    <details className="stores">
                      <summary>Buy nearby ({item.nearby_stores.length})</summary>
                      {item.nearby_stores.map((st) => (
                        <a key={st.name + st.map_url} className="store" href={st.map_url} target="_blank" rel="noreferrer">
                          <span className="sname">{st.name}</span>
                          <span className="smeta">{st.distance_km != null && `${st.distance_km} km`}{st.rating != null && ` · ★ ${st.rating}`}{st.source === 'sample' && 'sample data (Google not connected)'}</span>
                          {st.address && <span className="saddr">{st.address}</span>}
                        </a>
                      ))}
                    </details>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
