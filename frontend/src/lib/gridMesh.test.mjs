import assert from 'node:assert'
import { buildGridMesh, decodeDepth } from './gridMesh.js'
// base64 decode (same layout the backend writes: little-endian uint16 centimetres)
const b64 = Buffer.from(new Uint8Array(new Uint16Array([300, 450, 65]).buffer)).toString('base64')
globalThis.atob ??= (s) => Buffer.from(s, 'base64').toString('binary')
const dd = decodeDepth(b64, 3); assert.deepStrictEqual([...dd].map((v) => +v.toFixed(2)), [3, 4.5, 0.65])

const gw = 40, gh = 30, tanV = Math.tan((60 * Math.PI) / 360), tanH = tanV * (4 / 3)
// 1) flat wall 4 m away: every cell kept, corners land at +/- tanH*4
let d = new Float32Array(gw * gh).fill(4)
let m = buildGridMesh(d, gw, gh, tanH, tanV)
assert.strictEqual(m.indices.length, (gw - 1) * (gh - 1) * 2 * 3, 'flat wall keeps all triangles')
assert(Math.abs(m.positions[0] + tanH * 4) < 1e-5 && Math.abs(m.positions[2] + 4) < 1e-5)
// 2) a chair 1.5 m in front of a 4 m wall: triangles across its edge are dropped, others stay
d = new Float32Array(gw * gh).fill(4)
for (let j = 10; j < 20; j++) for (let i = 15; i < 25; i++) d[j * gw + i] = 2.5
m = buildGridMesh(d, gw, gh, tanH, tanV)
const total = (gw - 1) * (gh - 1) * 2 * 3
assert(m.indices.length < total && m.indices.length > total * 0.9, `holes only along the edge: ${m.indices.length}/${total}`)
// no kept triangle mixes 2.5 m and 4 m depths
for (let t = 0; t < m.indices.length; t += 3) {
  const z = [0, 1, 2].map((q) => d[m.indices[t + q]]); assert(Math.max(...z) / Math.min(...z) <= 1.3)
}
// 3) floor snapping: a slightly bumpy floor 1.5 m below the camera becomes flat
const u = [0, 1, 0], H = 1.5
d = new Float32Array(gw * gh)
for (let j = 0; j < gh; j++) for (let i = 0; i < gw; i++) {
  const v = j / (gh - 1); const y = (1 - 2 * v) * tanV                       // ray slope; floor hit at z = H / -y (only below horizon)
  d[j * gw + i] = y < -0.05 ? (H / -y) * (1 + 0.01 * ((i * 7 + j * 3) % 5 - 2)) : 6
}
m = buildGridMesh(d, gw, gh, tanH, tanV, { floor: { u, h: H, snap: 0.08 } })
let flat = 0, near = 0
for (let k = 0; k < gw * gh; k++) { const y = m.positions[3 * k + 1]; if (Math.abs(y + H) < 0.09) { near++; if (Math.abs(y + H) < 1e-6) flat++ } }
console.log('floor vertices near plane:', near, 'snapped exactly flat:', flat)
assert(flat > 0 && flat >= near * 0.95)
console.log('gridMesh ok, triangles kept with chair:', m.indices.length)
