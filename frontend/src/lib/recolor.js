import * as THREE from 'three'

// Recolours a furniture model. Works on the copy of the materials that this file makes for
// each mesh (models are cached and shared, so the originals must never be changed).
//  - plain materials: the colour is simply replaced
//  - textured materials: the texture's light/dark pattern (wood grain, fabric weave, shading)
//    is kept and re-coloured with the chosen colour, done with a few lines added to the shader
// applyTint(root, null) puts the original look back.

const state = new WeakMap()   // material -> { orig, uTint, uMix, uAvg }

function textureLuminance(tex) {
  try {
    const c = document.createElement('canvas'); c.width = c.height = 16
    const ctx = c.getContext('2d', { willReadFrequently: true })
    ctx.drawImage(tex.image, 0, 0, 16, 16)
    const d = ctx.getImageData(0, 0, 16, 16).data
    let sum = 0
    for (let i = 0; i < d.length; i += 4) {
      const lin = (v) => Math.pow(v / 255, 2.2)                        // the shader sees linear light
      sum += 0.2126 * lin(d[i]) + 0.7152 * lin(d[i + 1]) + 0.0722 * lin(d[i + 2])
    }
    return Math.max(0.05, sum / 256)
  } catch { return 0.4 }
}

function prepare(mat) {
  let st = state.get(mat)
  if (st) return st
  st = { orig: mat.color ? mat.color.clone() : null, uTint: { value: new THREE.Vector3(1, 1, 1) }, uMix: { value: 0 }, uAvg: { value: 0.4 } }
  state.set(mat, st)
  if (mat.map) {
    st.uAvg.value = textureLuminance(mat.map)
    mat.onBeforeCompile = (shader) => {
      shader.uniforms.uTint = st.uTint; shader.uniforms.uMix = st.uMix; shader.uniforms.uAvg = st.uAvg
      shader.fragmentShader = 'uniform vec3 uTint;\nuniform float uMix;\nuniform float uAvg;\n' + shader.fragmentShader.replace(
        '#include <map_fragment>',
        `#include <map_fragment>
        #ifdef USE_MAP
          float lumS = dot(sampledDiffuseColor.rgb, vec3(0.2126, 0.7152, 0.0722));
          vec3 tinted = uTint * clamp(lumS / uAvg, 0.0, 1.6) * 0.9;
          diffuseColor.rgb = mix(diffuseColor.rgb, tinted, uMix);
        #endif`)
    }
    mat.customProgramCacheKey = () => 'furniture-tint'
    mat.needsUpdate = true
  }
  return st
}

export function applyTint(root, hex) {
  if (!root) return
  root.traverse((o) => {
    if (!o.isMesh || !o.material) return
    if (!o.userData.__ownMaterial) {
      o.material = Array.isArray(o.material) ? o.material.map((m) => m.clone()) : o.material.clone()
      o.userData.__ownMaterial = true
    }
    for (const m of Array.isArray(o.material) ? o.material : [o.material]) {
      const st = prepare(m)
      if (m.map) {
        if (hex) { const c = new THREE.Color(hex); st.uTint.value.set(c.r, c.g, c.b) }
        st.uMix.value = hex ? 1 : 0
      } else if (m.color) {
        if (hex) m.color.set(hex); else if (st.orig) m.color.copy(st.orig)
      }
    }
  })
}
