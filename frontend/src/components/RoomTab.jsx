import { useState } from 'react'
import PhotoAR from './PhotoAR'
import Room3D from './Room3D'
import ColorPanel from './ColorPanel'

// Two views only: your photo with the furniture placed in it, and a clean floor plan.
export default function RoomTab({ items, result, preview, apiUrl, colors, setColors }) {
  const [mode, setMode] = useState('photo')
  const sp = result.space
  const palette = result.perception.dominant_colors
  return (
    <div className="stack">
      <div className="seg">
        <button type="button" className={mode === 'photo' ? 'on' : ''} onClick={() => setMode('photo')}>In your photo</button>
        <button type="button" className={mode === 'plan' ? 'on' : ''} onClick={() => setMode('plan')}>Floor plan (3D)</button>
      </div>
      {mode === 'photo' && (
        <PhotoAR items={items} camera={result.scene} mesh={null} roomLength={sp?.room_l_m}
                 photoUrl={preview} apiUrl={apiUrl} colors={colors} orbit={false} />
      )}
      {mode === 'plan' && (
        <>
          <Room3D items={items} palette={palette} apiUrl={apiUrl} colors={colors}
                  room={{ w: sp?.room_w_m ?? 4, l: sp?.room_l_m ?? 4 }} />
          {sp
            ? <div className="notice info">Floor plan of a {sp.room_w_m} × {sp.room_l_m} m room{sp.source === 'user' ? ' (the size you typed)' : ' (estimated from your photo; type the real size for an exact plan)'}.</div>
            : <div className="notice info">Room size unknown, so a 4 × 4 m room is shown. Type the real size in the form on the left.</div>}
        </>
      )}
      <ColorPanel items={items} palette={palette} colors={colors} setColors={setColors} />
    </div>
  )
}
