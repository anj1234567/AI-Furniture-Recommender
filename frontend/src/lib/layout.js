// Puts the recommended furniture on the floor of the room. Pure maths, no
// three.js, so it can be tested on its own (see layout.test.mjs).
// Room: x = width (left/right), z = length (back wall is z = -L/2). Units: metres.

const DEFAULT_CM = { bed: [160, 200], sofa: [200, 90], table: [120, 80], chair: [50, 50] }
const GAP = 0.08          // wall clearance and minimum gap between pieces
const ORDER = ['bed', 'sofa', 'table', 'chair']

export function footprint(item) {
  const [dw, dd] = DEFAULT_CM[item.category] ?? [80, 80]
  return { w: (item.width_cm || dw) / 100, d: (item.depth_cm || dd) / 100 }
}

// size on the floor after rotation (90 degrees swaps width and depth)
const rotated = (f, rotY) => (Math.abs(Math.sin(rotY)) > 0.5 ? { w: f.d, d: f.w } : f)

function overlaps(a, b) {
  return Math.abs(a.x - b.x) < (a.w + b.w) / 2 + GAP && Math.abs(a.z - b.z) < (a.d + b.d) / 2 + GAP
}

export function layoutRoom(items, W, L) {
  const placed = {}      // category -> {x, z, rotY, w, d, ok}
  const list = []
  const clampX = (x, w) => Math.min(W / 2 - w / 2 - GAP, Math.max(-W / 2 + w / 2 + GAP, x))
  const clampZ = (z, d) => Math.min(L / 2 - d / 2 - GAP, Math.max(-L / 2 + d / 2 + GAP, z))
  const free = (p) => !list.some((q) => overlaps(p, q))

  // try the preferred spot first, then spots further and further away
  function search(pref, rotY, f) {
    const r = rotated(f, rotY)
    const at = (x, z) => ({ x: clampX(x, r.w), z: clampZ(z, r.d), rotY, w: r.w, d: r.d })
    const best = at(pref.x, pref.z)
    if (free(best)) return { ...best, ok: true }
    const cands = []
    for (let x = -W / 2; x <= W / 2; x += 0.2)
      for (let z = -L / 2; z <= L / 2; z += 0.2) cands.push(at(x, z))
    cands.sort((a, b) => Math.hypot(a.x - pref.x, a.z - pref.z) - Math.hypot(b.x - pref.x, b.z - pref.z))
    const hit = cands.find(free)
    return hit ? { ...hit, ok: true } : { ...best, ok: false }
  }

  const sorted = [...items].sort((a, b) => ORDER.indexOf(a.category) - ORDER.indexOf(b.category))
  for (const item of sorted) {
    const f = footprint(item)
    let pref, rotY = 0
    if (item.category === 'bed') {                 // head against the back wall
      pref = { x: -W * 0.15, z: -L / 2 + f.d / 2 + GAP }
    } else if (item.category === 'sofa') {         // against the right wall, facing the room
      rotY = -Math.PI / 2
      pref = { x: W / 2 - f.d / 2 - GAP, z: L * 0.1 }
    } else if (item.category === 'table') {
      pref = { x: 0, z: L * 0.15 }
    } else {                                       // chair: pulled up to the table
      const t = placed.table
      rotY = Math.PI
      pref = t ? { x: t.x, z: t.z + t.d / 2 + f.d / 2 + GAP } : { x: 0, z: L * 0.3 }
    }
    const p = search(pref, rotY, f)
    placed[item.category] = p
    list.push(p)
  }
  return { placed, allFit: Object.values(placed).every((p) => p.ok) }
}
