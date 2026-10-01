// Builds a triangle mesh of the real room from the depth grid. Pure maths, no three.js,
// so it can be tested on its own (gridMesh.test.mjs).
//
// Camera coordinates as in three.js: x right, y up, camera looks down -z.
// For a grid cell (col i, row j) with depth z metres:
//   x = (2u - 1) * tanH * z,  y = (1 - 2v) * tanV * z,  position z = -z      (u = i/(w-1), v = j/(h-1))
// Triangles that stretch across a depth jump (the edge of a chair against the wall behind it)
// or that are seen almost edge-on are dropped, so the mesh has holes there instead of "curtains".

export function decodeDepth(b64, n) {
  const bin = atob(b64), out = new Float32Array(n)
  for (let i = 0; i < n; i++) out[i] = (bin.charCodeAt(2 * i) | (bin.charCodeAt(2 * i + 1) << 8)) / 100
  return out
}

export function buildGridMesh(depth, gw, gh, tanH, tanV, opts = {}) {
  const { maxRatio = 1.3, minFacing = 0.05, floor = null } = opts    // floor: {u:[x,y,z], h} = plane to snap flat areas onto
  const pos = new Float32Array(gw * gh * 3), uv = new Float32Array(gw * gh * 2)
  for (let j = 0; j < gh; j++) {
    for (let i = 0; i < gw; i++) {
      const k = j * gw + i, u = i / (gw - 1), v = j / (gh - 1), z = depth[k]
      let x = (2 * u - 1) * tanH * z, y = (1 - 2 * v) * tanV * z, zz = -z
      if (floor) {
        const dist = x * floor.u[0] + y * floor.u[1] + zz * floor.u[2] + floor.h     // signed height above the floor plane
        if (Math.abs(dist) < (floor.snap ?? 0.07)) { x -= floor.u[0] * dist; y -= floor.u[1] * dist; zz -= floor.u[2] * dist }
      }
      pos[3 * k] = x; pos[3 * k + 1] = y; pos[3 * k + 2] = zz
      uv[2 * k] = u; uv[2 * k + 1] = 1 - v
    }
  }
  const idx = []
  const tri = (a, b, c) => {
    const za = depth[a], zb = depth[b], zc = depth[c]
    const mx = Math.max(za, zb, zc), mn = Math.min(za, zb, zc)
    if (mn <= 0 || mx / mn > maxRatio) return
    // how face-on is the triangle to the camera? |n . view| / |n| with the view ray from the camera to the centroid
    const ax = pos[3 * b] - pos[3 * a], ay = pos[3 * b + 1] - pos[3 * a + 1], az = pos[3 * b + 2] - pos[3 * a + 2]
    const bx = pos[3 * c] - pos[3 * a], by = pos[3 * c + 1] - pos[3 * a + 1], bz = pos[3 * c + 2] - pos[3 * a + 2]
    const nx = ay * bz - az * by, ny = az * bx - ax * bz, nz = ax * by - ay * bx
    const nl = Math.hypot(nx, ny, nz); if (nl < 1e-12) return
    const cx = (pos[3 * a] + pos[3 * b] + pos[3 * c]) / 3, cy = (pos[3 * a + 1] + pos[3 * b + 1] + pos[3 * c + 1]) / 3, cz = (pos[3 * a + 2] + pos[3 * b + 2] + pos[3 * c + 2]) / 3
    const cl = Math.hypot(cx, cy, cz)
    if (Math.abs(nx * cx + ny * cy + nz * cz) / (nl * cl) < minFacing) return
    idx.push(a, b, c)
  }
  for (let j = 0; j < gh - 1; j++) {
    for (let i = 0; i < gw - 1; i++) {
      const a = j * gw + i, b = a + 1, c = a + gw, d = c + 1
      tri(a, c, b); tri(b, c, d)
    }
  }
  return { positions: pos, uvs: uv, indices: new Uint32Array(idx) }
}
