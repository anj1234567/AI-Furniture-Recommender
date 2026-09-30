import { layoutRoom } from './layout.js'
const mk = (c, w, d) => ({ category: c, width_cm: w, depth_cm: d })
const items = [mk('bed', 160, 200), mk('sofa', 190, 90), mk('table', 120, 80), mk('chair', 50, 50)]
let bad = 0
for (const [W, L] of [[3, 4], [4, 5], [5.5, 4.2], [2.6, 3], [6, 7]]) {
  const { placed, allFit } = layoutRoom(items, W, L)
  const ps = Object.values(placed)
  const inside = ps.every((p) => Math.abs(p.x) + p.w / 2 <= W / 2 + 1e-6 && Math.abs(p.z) + p.d / 2 <= L / 2 + 1e-6)
  let clash = 0
  for (let i = 0; i < ps.length; i++) for (let j = i + 1; j < ps.length; j++)
    if (Math.abs(ps[i].x - ps[j].x) < (ps[i].w + ps[j].w) / 2 && Math.abs(ps[i].z - ps[j].z) < (ps[i].d + ps[j].d) / 2) clash++
  console.log(`${W}x${L}: inside=${inside} allFit=${allFit} overlapping_pairs=${clash}`)
  if (!inside || (allFit && clash)) bad++
}
console.log(bad ? 'FAIL' : 'OK')
process.exit(bad ? 1 : 0)
