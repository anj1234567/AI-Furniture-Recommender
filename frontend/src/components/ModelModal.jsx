import { API_URL } from '../lib/api'

export default function ModelModal({ item, onClose }) {
  return (
    <div className="modal" onClick={onClose}>
      <div className="modalbox" onClick={(e) => e.stopPropagation()}>
        <div className="modalhead"><b>{item.name}</b><button type="button" className="linkbtn" onClick={onClose}>Close</button></div>
        <model-viewer src={`${API_URL}${item.model_url}`} alt={item.name}
                      {...{ 'camera-controls': true, 'auto-rotate': true, 'shadow-intensity': '1' }}
                      style={{ width: '100%', height: '420px', background: '#eef1f0', borderRadius: 10 }} />
        <div className="hint">Drag to rotate, scroll to zoom. Real product size: {item.width_cm} × {item.depth_cm}{item.height_cm ? ` × ${item.height_cm}` : ''} cm. The first load can take a few seconds.</div>
      </div>
    </div>
  )
}
