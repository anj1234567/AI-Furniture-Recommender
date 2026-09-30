import * as THREE from 'three'

// Where is the floor, in the camera's own coordinates? `up` is the floor normal (from the
// depth model), h the camera height above the floor, tilt a manual correction in degrees.
// Everything (floor, shadows, furniture) lives in one group placed on that plane, so a piece
// at floor position (a, b) [b = metres straight ahead] lines up with the photo's perspective.
export function floorFrame(up, h, tiltDeg) {
  const u = new THREE.Vector3(...up).normalize()
  u.applyAxisAngle(new THREE.Vector3(1, 0, 0), THREE.MathUtils.degToRad(tiltDeg))
  const f0 = new THREE.Vector3(0, 0, -1)
  const f = f0.clone().sub(u.clone().multiplyScalar(f0.dot(u))).normalize()   // camera direction, flattened onto the floor
  const r = new THREE.Vector3().crossVectors(f, u).normalize()
  const q = new THREE.Quaternion().setFromRotationMatrix(new THREE.Matrix4().makeBasis(r, u, f.clone().negate()))
  return { u, q, origin: u.clone().multiplyScalar(-h) }    // origin = the floor point straight below the camera
}
