import { useState } from 'react'
import PhotoAR from './PhotoAR'
import Room3D from './Room3D'

export default function RoomTab({ items, result, preview, apiUrl }) {
  const [mode, setMode] = useState('photo')
  const sp = result.space
  return (
    <div>
      <div className="seg">
        <button type="button" className={mode === 'photo' ? 'on' : ''} onClick={() => setMode('photo')}>In your photo</button>
        <button type="button" className={mode === 'plan' ? 'on' : ''} onClick={() => setMode('plan')}>Floor plan (3D)</button>
      </div>
      {mode === 'photo' && (
        <PhotoAR items={items} camera={result.scene} roomLength={sp?.room_l_m} photoUrl={preview} apiUrl={apiUrl} />
      )}
      {mode === 'plan' && (
        <>
          <Room3D items={items} palette={result.perception.dominant_colors} photoUrl={preview} apiUrl={apiUrl}
                  room={{ w: sp?.room_w_m ?? 4, l: sp?.room_l_m ?? 4 }} />
          {!sp && <div className="notice info">Room size unknown, so a 4 × 4 m room is shown. Type the real size under More options.</div>}
        </>
      )}
    </div>
  )
}
