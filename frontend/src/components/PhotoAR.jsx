import { useEffect, useRef, useState } from 'react'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { loadModel } from '../lib/models'
import { footprint } from '../lib/layout'
import { floorFrame } from '../lib/floorFrame'
import { applyTint } from '../lib/recolor'
import { buildGridMesh, decodeDepth } from '../lib/gridMesh'

// One scene, two ways to look at it:
//  - fixed:  a transparent 3D canvas laid over the photo (furniture "in your photo")
//  - orbit:  th  e photo becomes a real 3D mesh of the room (built from the depth map), so you
//            can look around, and real objects hide furniture that stands behind them.
export default function PhotoAR({ items, camera: cam, mesh, roomLength, photoUrl, apiUrl, colors = {}, orbit = false }) {
  const host = useRef(null), imgRef = useRef(null), T = useRef({})
  const [h, setH] = useState(cam.cam_height_m)
  const [tilt, setTilt] = useState(0)
  const [grid, setGrid] = useState(false)
  const [sel, setSel] = useState(0)
  const [loaded, setLoaded] = useState({ n: 0, failed: 0 })
  const [meshReady, setMeshReady] = useState(0)
  const colorsRef = useRef(colors); colorsRef.current = colors
  const orbitOn = orbit && !!mesh

  useEffect(() => { setH(cam.cam_height_m); setTilt(0) }, [cam])

  // ---- setup once: transparent WebGL canvas (over the photo, or the whole view in orbit mode) ----
  useEffect(() => {
    const el = host.current
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, preserveDrawingBuffer: true })
    renderer.setClearColor(0x000000, 0)
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    renderer.shadowMap.enabled = true
    renderer.shadowMap.type = THREE.PCFSoftShadowMap
    el.appendChild(renderer.domElement)
    const scene = new THREE.Scene()
    const camera = new THREE.PerspectiveCamera(cam.fov_v_deg, cam.aspect, 0.05, 100)   // same lens as the photo
    scene.add(new THREE.HemisphereLight('#ffffff', '#7a7a7a', 1.0))
    const frame = new THREE.Group(); scene.add(frame)
    const sun = new THREE.DirectionalLight('#ffffff', 1.6)
    sun.position.set(1.5, 5, 1); sun.castShadow = true; sun.shadow.mapSize.set(2048, 2048)
    Object.assign(sun.shadow.camera, { left: -7, right: 7, top: 7, bottom: -7, near: 0.5, far: 15 })
    frame.add(sun, sun.target)
    const catcher = new THREE.Mesh(new THREE.PlaneGeometry(40, 40),
      new THREE.ShadowMaterial({ opacity: 0.4, polygonOffset: true, polygonOffsetFactor: -2, polygonOffsetUnits: -2 }))
    catcher.rotation.x = -Math.PI / 2; catcher.receiveShadow = true; frame.add(catcher)
    const gridHelper = new THREE.GridHelper(12, 24, 0xffffff, 0xffffff)
    gridHelper.material.transparent = true; gridHelper.material.opacity = 0.45; gridHelper.visible = false
    frame.add(gridHelper)
    const stuff = new THREE.Group(); frame.add(stuff)

    const resize = () => { renderer.setSize(el.clientWidth, el.clientHeight) }
    const ro = new ResizeObserver(resize); ro.observe(el); resize()
    let raf
    const loop = () => { raf = requestAnimationFrame(loop); T.current.controls?.update(); renderer.render(scene, camera) }
    loop()
    T.current = { renderer, scene, camera, controls: null, frame, stuff, gridHelper, nodes: [], prevH: null, orbit: false, photoMesh: null }
    return () => { cancelAnimationFrame(raf); ro.disconnect(); T.current.controls?.dispose(); renderer.dispose(); el.removeChild(renderer.domElement) }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cam.fov_v_deg, cam.aspect])

  // ---- the photo as a 3D mesh (depth map + photo texture) ----
  useEffect(() => {
    const t = T.current
    if (t.photoMesh) { t.scene.remove(t.photoMesh); t.photoMesh.geometry.dispose(); t.photoMesh.material.map?.dispose(); t.photoMesh.material.dispose(); t.photoMesh = null }
    if (!mesh) return undefined
    let cancelled = false
    const img = new Image()
    img.onload = () => {
      if (cancelled) return
      // draw through a canvas: an <img> is already rotated by its EXIF tag (like the photo the
      // backend analysed), and the canvas keeps the texture within a size every GPU accepts
      const sc = Math.min(1, 2048 / Math.max(img.naturalWidth, img.naturalHeight))
      const cvs = document.createElement('canvas'); cvs.width = Math.round(img.naturalWidth * sc); cvs.height = Math.round(img.naturalHeight * sc)
      cvs.getContext('2d').drawImage(img, 0, 0, cvs.width, cvs.height)
      const tex = new THREE.CanvasTexture(cvs)
      tex.colorSpace = THREE.SRGBColorSpace
      const tanV = Math.tan(THREE.MathUtils.degToRad(cam.fov_v_deg) / 2), tanH = tanV * cam.aspect
      const depth = decodeDepth(mesh.depth_cm_b64, mesh.w * mesh.h)
      const floor = cam.floor_source === 'depth' ? { u: cam.up, h: cam.cam_height_m, snap: 0.07 } : null   // flatten the floor so furniture stands on it
      const g = buildGridMesh(depth, mesh.w, mesh.h, tanH, tanV, { floor })
      const geo = new THREE.BufferGeometry()
      geo.setAttribute('position', new THREE.BufferAttribute(g.positions, 3))
      geo.setAttribute('uv', new THREE.BufferAttribute(g.uvs, 2))
      geo.setIndex(new THREE.BufferAttribute(g.indices, 1))
      const m = new THREE.Mesh(geo, new THREE.MeshBasicMaterial({ map: tex, side: THREE.DoubleSide, polygonOffset: true, polygonOffsetFactor: 1, polygonOffsetUnits: 1 }))
      m.visible = !!T.current.orbit
      T.current.scene.add(m); T.current.photoMesh = m; T.current.meshDepth = mesh.median_m
      setMeshReady((n) => n + 1)
    }
    img.src = photoUrl
    return () => { cancelled = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mesh, photoUrl, cam.fov_v_deg, cam.aspect])

  // ---- switch between the fixed view and the orbit view ----
  // OrbitControls reads camera.up only once when it is created, so a fresh one is made each time
  // we (re)enter the orbit view. Its limits are set around wherever the photo's own viewpoint is.
  const goHome = () => {
    const t = T.current; if (!t.camera) return
    t.controls?.dispose(); t.controls = null
    t.camera.position.set(0, 0, 0); t.camera.quaternion.identity()
    if (!t.orbit) { t.camera.up.set(0, 1, 0); return }
    const { u } = floorFrame(cam.up, h, tilt)
    const D = Math.min(8, Math.max(2, t.meshDepth ?? 3.5))
    t.camera.up.copy(u)
    const c = new OrbitControls(t.camera, t.renderer.domElement)
    c.enableDamping = true; c.enablePan = false; c.rotateSpeed = 0.6
    c.target.set(0, 0, -D); c.update()
    const az = c.getAzimuthalAngle(), po = c.getPolarAngle()
    Object.assign(c, {
      minAzimuthAngle: az - 1.0, maxAzimuthAngle: az + 1.0,
      minPolarAngle: Math.max(0.15, po - 0.6), maxPolarAngle: Math.min(Math.PI - 0.3, po + 0.25),
      minDistance: D * 0.3, maxDistance: D * 1.4,
    })
    c.update()
    t.controls = c
  }
  useEffect(() => {
    const t = T.current; if (!t.camera) return
    t.orbit = orbitOn
    if (t.photoMesh) t.photoMesh.visible = orbitOn
    t.renderer.setClearColor(orbitOn ? 0x0b1110 : 0x000000, orbitOn ? 1 : 0)
    goHome()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [orbitOn, meshReady, cam.fov_v_deg, cam.aspect])

  // ---- move the floor when height / tilt change (keep pieces at the same spot in the picture) ----
  useEffect(() => {
    const t = T.current
    const { q, origin } = floorFrame(cam.up, h, tilt)
    t.frame.position.copy(origin); t.frame.quaternion.copy(q)
    if (t.prevH && t.prevH !== h) t.nodes.forEach((n) => { n.outer.position.x *= h / t.prevH; n.outer.position.z *= h / t.prevH })
    t.prevH = h
  }, [h, tilt, cam])

  useEffect(() => { T.current.gridHelper.visible = grid }, [grid])

  // ---- (re)build the furniture when the chosen items change ----
  const key = items.map((i) => i.item_id).join(',')
  useEffect(() => {
    const t = T.current
    let cancelled = false
    t.stuff.clear(); t.nodes = []
    setLoaded({ n: 0, failed: 0 }); setSel(0)
    t.frame.updateMatrixWorld(true)

    // placement is always judged from the photo's own viewpoint, even if the user is orbiting right now
    const viewCam = new THREE.PerspectiveCamera(cam.fov_v_deg, cam.aspect, 0.05, 100)
    viewCam.updateMatrixWorld(true)

    // first floor distance whose base is comfortably inside the picture
    const tanH = Math.tan(THREE.MathUtils.degToRad(cam.fov_v_deg) / 2) * cam.aspect
    const inView = (a, b) => {
      const p = t.frame.localToWorld(new THREE.Vector3(a, 0, -b)).project(viewCam)
      return p.z < 1 && p.y > -0.55 && Math.abs(p.x) < 0.85
    }
    let b0 = 1.5
    while (b0 < 8 && !inView(0, b0)) b0 += 0.25
    const maxB = Math.max(b0 + 1, Math.min(9, (roomLength || 6) * 0.9))

    // choose a floor spot for each piece: inside the picture, clear of the others, close to a preferred spot
    const taken = []
    const spotFor = (item, k) => {
      const f = footprint(item)
      const prefB = Math.min(b0 + 1.0 * k, maxB), prefA = (k % 2 ? 1 : -1) * 0.22 * prefB * tanH
      const visible = (a, b) => [-1, 0, 1].every((s) => {
        const p = t.frame.localToWorld(new THREE.Vector3(a + (s * f.w) / 2, 0, -b)).project(viewCam)
        return p.z < 1 && p.y > -0.6 && Math.abs(p.x) < 0.92
      })
      const cands = []
      for (let b = b0; b <= maxB + 1.5; b += 0.25)
        for (let a = -b * tanH; a <= b * tanH; a += 0.25) cands.push({ a, b })
      cands.sort((x, y) => Math.hypot(x.a - prefA, (x.b - prefB) * 1.5) - Math.hypot(y.a - prefA, (y.b - prefB) * 1.5))
      const ok = cands.find(({ a, b }) => visible(a, b) &&
        !taken.some((q) => Math.abs(q.a - a) < (q.w + f.w) / 2 + 0.1 && Math.abs(q.b - b) < (q.d + f.d) / 2 + 0.1))
      const spot = ok ?? { a: prefA, b: prefB }
      taken.push({ ...spot, w: f.w, d: f.d })
      return spot
    }

    items.forEach((item, k) => {
      const { a, b } = spotFor(item, k)
      const outer = new THREE.Group(), inner = new THREE.Group()
      outer.position.set(a, 0, -b); outer.add(inner)
      const hh = (item.height_cm || 80) / 100
      const box = new THREE.Mesh(new THREE.BoxGeometry((item.width_cm || 80) / 100, hh, (item.depth_cm || 80) / 100),
        new THREE.MeshStandardMaterial({ color: item.color_hex || '#9aa5a1', transparent: true, opacity: 0.5 }))
      box.position.y = hh / 2; inner.add(box)
      applyTint(inner, colorsRef.current[item.category])
      t.stuff.add(outer); t.nodes.push({ item, outer, inner })
      if (!item.model_url) { setLoaded((s) => ({ ...s, n: s.n + 1 })); return }
      loadModel(`${apiUrl}${item.model_url}`).then((obj) => {
        if (cancelled) return
        let bb = new THREE.Box3().setFromObject(obj), size = bb.getSize(new THREE.Vector3())
        if ((item.height_cm || 0) > 0 && size.y > 0) obj.scale.setScalar((item.height_cm / 100) / size.y)   // real product height
        bb = new THREE.Box3().setFromObject(obj)
        const c = bb.getCenter(new THREE.Vector3())
        obj.position.set(-c.x, -bb.min.y, -c.z)
        obj.traverse((m) => { if (m.isMesh) { m.castShadow = true } })
        inner.remove(box); inner.add(obj)
        applyTint(inner, colorsRef.current[item.category])
        setLoaded((s) => ({ ...s, n: s.n + 1 }))
      }).catch(() => { if (!cancelled) setLoaded((s) => ({ n: s.n + 1, failed: s.failed + 1 })) })
    })

    // ---- pick and drag pieces along the floor ----
    const dom = t.renderer.domElement, ray = new THREE.Raycaster(), ndc = new THREE.Vector2()
    let drag = null, grab = new THREE.Vector3()
    const setRay = (e) => {
      const r = dom.getBoundingClientRect()
      ndc.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1)
      ray.setFromCamera(ndc, t.camera)
    }
    const floorHit = () => {
      t.frame.updateMatrixWorld(true)
      const normal = new THREE.Vector3(0, 1, 0).transformDirection(t.frame.matrixWorld)   // floor plane in world space
      const pl = new THREE.Plane().setFromNormalAndCoplanarPoint(normal, t.frame.getWorldPosition(new THREE.Vector3())), pt = new THREE.Vector3()
      return ray.ray.intersectPlane(pl, pt) ? t.frame.worldToLocal(pt) : null
    }
    const nodeOf = (o) => { while (o && !t.nodes.some((n) => n.outer === o)) o = o.parent; return o }
    const down = (e) => {
      setRay(e)
      const hit = ray.intersectObjects(t.nodes.map((n) => n.outer), true)[0]
      if (!hit) return
      e.stopImmediatePropagation()                                   // do not start orbiting when grabbing furniture
      if (t.controls) t.controls.enabled = false
      drag = nodeOf(hit.object); setSel(t.nodes.findIndex((n) => n.outer === drag))
      const p = floorHit(); if (p) grab.copy(p).sub(drag.position)
      dom.setPointerCapture?.(e.pointerId); dom.style.cursor = 'grabbing'
    }
    const move = (e) => {
      setRay(e)
      if (!drag) { dom.style.cursor = ray.intersectObjects(t.nodes.map((n) => n.outer), true).length ? 'grab' : 'default'; return }
      const p = floorHit(); if (!p) return
      const nx = p.x - grab.x, nz = p.z - grab.z
      if (nz < -0.3) { drag.position.x = nx; drag.position.z = nz }     // keep it in front of the camera
    }
    const up = () => { if (drag) { drag = null; if (t.controls) t.controls.enabled = true }; dom.style.cursor = 'default' }
    dom.addEventListener('pointerdown', down, true); dom.addEventListener('pointermove', move)
    window.addEventListener('pointerup', up)
    return () => {
      cancelled = true
      dom.removeEventListener('pointerdown', down, true); dom.removeEventListener('pointermove', move); window.removeEventListener('pointerup', up)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, cam.fov_v_deg, cam.aspect])

  // ---- the user recoloured a piece ----
  useEffect(() => {
    T.current.nodes?.forEach((n) => applyTint(n.inner, colors[n.item.category]))
  }, [colors, key, loaded.n])

  const turn = (deg) => { const n = T.current.nodes[sel]; if (n) n.inner.rotation.y += THREE.MathUtils.degToRad(deg) }
  const save = () => {
    const t = T.current, img = imgRef.current
    const wasGrid = t.gridHelper.visible; t.gridHelper.visible = false
    t.renderer.render(t.scene, t.camera)
    let url
    if (t.orbit) {
      url = t.renderer.domElement.toDataURL('image/png')
    } else {
      const out = document.createElement('canvas'); out.width = img.naturalWidth; out.height = img.naturalHeight
      const ctx = out.getContext('2d'); ctx.drawImage(img, 0, 0)
      ctx.drawImage(t.renderer.domElement, 0, 0, out.width, out.height)
      url = out.toDataURL('image/png')
    }
    t.gridHelper.visible = wasGrid
    const a = document.createElement('a'); a.href = url; a.download = 'my-room-with-furniture.png'; a.click()
  }

  const fromDepth = cam.floor_source === 'depth'
  return (
    <div className="ar">
      {orbit && !mesh && (
        <div className="notice warn" style={{ marginTop: 0, marginBottom: 10 }}>
          The 3D room needs the depth model, which did not run for this photo, so the fixed view is shown instead.
        </div>
      )}
      <div className={`notice ${orbitOn || fromDepth ? 'info' : 'warn'}`} style={{ marginTop: 0, marginBottom: 10 }}>
        {orbitOn
          ? 'Your room rebuilt in 3D from the photo. Drag to look around (about 55° each way), scroll to zoom. You only see what the camera saw, and real objects hide furniture placed behind them.'
          : fromDepth
            ? `Floor found in your photo (fit quality ${Math.round((cam.inlier_ratio || 0) * 100)}%). Camera height about ${cam.cam_height_m} m${cam.ceiling_height_m ? `, ceiling about ${cam.ceiling_height_m} m` : ''}.`
            : 'The floor could not be found in this photo, so a level camera at 1.4 m is assumed. Use the sliders below until the furniture sits on the floor.'}
      </div>
      <div className="ar-wrap" style={{ aspectRatio: cam.aspect, maxWidth: `calc(70vh * ${cam.aspect})` }}>
        <img ref={imgRef} src={photoUrl} alt="your room" className="ar-photo" style={{ visibility: orbitOn ? 'hidden' : 'visible' }} />
        <div ref={host} className="ar-canvas" />
        {loaded.n < items.length && <div className="room3d-load">Loading 3D models {loaded.n}/{items.length}. The first time can take a minute.</div>}
      </div>
      {loaded.failed > 0 && <div className="notice warn">{loaded.failed} model(s) could not load, so a box of the real size is shown.</div>}

      <div className="card ar-tools">
        <div className="btnrow">
          {items.map((it, i) => (
            <button key={it.item_id} type="button" className={`chip ${sel === i ? 'on' : ''}`} onClick={() => setSel(i)}>{it.category}</button>
          ))}
          <button type="button" className="ghost" onClick={() => turn(-15)}>Turn left</button>
          <button type="button" className="ghost" onClick={() => turn(15)}>Turn right</button>
          <button type="button" className="ghost" onClick={() => turn(90)}>Turn 90°</button>
          {orbitOn && <button type="button" className="ghost" onClick={goHome}>Reset view</button>}
          <button type="button" className="ghost" onClick={save}>Save picture</button>
        </div>
        <div className="sliders">
          <label>Camera height {h.toFixed(2)} m
            <input type="range" min="0.8" max="2.4" step="0.05" value={h} onChange={(e) => setH(Number(e.target.value))} /></label>
          <label>Floor tilt {tilt}°
            <input type="range" min="-20" max="20" step="1" value={tilt} onChange={(e) => setTilt(Number(e.target.value))} /></label>
          <label className="check"><input type="checkbox" checked={grid} onChange={(e) => setGrid(e.target.checked)} /> Show floor grid</label>
        </div>
        <div className="hint">
          Drag a piece along the floor to move it. Furniture looks too small? Lower the camera height. Too big? Raise it.
          {orbitOn ? ' Furniture keeps its place when you switch between the views.' : ' Real objects in the photo cannot hide the furniture here; open “Room in 3D” for that.'}
        </div>
      </div>
    </div>
  )
}
