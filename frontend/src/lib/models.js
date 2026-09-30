import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'

// Each 3D model is downloaded once per page load, then cloned for every use.
const cache = new Map()
export function loadModel(url) {
  if (!cache.has(url)) {
    cache.set(url, new GLTFLoader().loadAsync(url).then((g) => g.scene).catch((e) => { cache.delete(url); throw e }))
  }
  return cache.get(url).then((scene) => scene.clone(true))
}
