import { useEffect, useRef, useState } from 'react'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { layoutRoom } from '../lib/layout'
import { loadModel } from '../lib/models'
import { applyTint } from '../lib/recolor'

const WALL_H = 2.7
const lum = (hex) => { const c = new THREE.Color(hex); return 0.2126 * c.r + 0.7152 * c.g + 0.0722 * c.b }

// Wall = lightest colour found in the photo, floor = a mid-dark one.
function roomColours(palette) {
  const s = [...(palette?.length ? palette : ['#e8e4dc', '#8a7358'])].sort((a, b) => lum(b) - lum(a))
  return { wall: s[0], floor: s[Math.min(s.length - 1, Math.floor(s.length * 0.7))] }
}

export default function Room3D({ items, room, palette, photoUrl, apiUrl, colors = {} }) {
  const mount = useRef(null)
  const three = useRef({})            // renderer, camera, controls, content group
  const [resetKey, setResetKey] = useState(0)
  const [status, setStatus] = useState({ loaded: 0, total: 0, failed: 0 })
  const [layoutInfo, setLayoutInfo] = useState({ allFit: true })
  const colorsRef = useRef(colors); colorsRef.current = colors

  // ---- one-time setup: renderer, camera, lights, controls, render loop ----
  useEffect(() => {
    const el = mount.current
    const renderer = new THREE.WebGLRenderer({ antialias: true })
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    renderer.shadowMap.enabled = true
    el.appendChild(renderer.domElement)
    const scene = new THREE.Scene()
    scene.background = new THREE.Color('#dfe5e3')
    const camera = new THREE.PerspectiveCamera(50, 1, 0.1, 100)
    const controls = new OrbitControls(camera, renderer.domElement)
    controls.enableDamping = true
    controls.maxPolarAngle = Math.PI / 2 - 0.02
    scene.add(new THREE.HemisphereLight('#ffffff', '#8a8f8c', 1.1))
    const sun = new THREE.DirectionalLight('#ffffff', 1.4)
    sun.position.set(4, 7, 5)
    sun.castShadow = true
    sun.shadow.mapSize.set(1024, 1024)
    Object.assign(sun.shadow.camera, { left: -8, right: 8, top: 8, bottom: -8 })
    scene.add(sun)
    const content = new THREE.Group()
    scene.add(content)

    const resize = () => {
      const w = el.clientWidth, h = el.clientHeight
      renderer.setSize(w, h); camera.aspect = w / h; camera.updateProjectionMatrix()
    }
    const ro = new ResizeObserver(resize); ro.observe(el); resize()
    let raf
    const loop = () => { raf = requestAnimationFrame(loop); controls.update(); renderer.render(scene, camera) }
    loop()

    three.current = { renderer, camera, controls, content, scene }
    return () => {
      cancelAnimationFrame(raf); ro.disconnect(); controls.dispose(); renderer.dispose()
      el.removeChild(renderer.domElement)
    }
  }, [])

  // ---- rebuild the room and furniture whenever inputs change ----
  const key = JSON.stringify([items.map((i) => i.item_id), room.w, room.l, palette, resetKey])
  useEffect(() => {
    const { content, camera, controls, renderer } = three.current
    let cancelled = false
    content.clear()
    const W = room.w, L = room.l
    const col = roomColours(palette)

    const floor = new THREE.Mesh(new THREE.PlaneGeometry(W, L), new THREE.MeshStandardMaterial({ color: col.floor, roughness: 0.85 }))
    floor.rotation.x = -Math.PI / 2; floor.receiveShadow = true; floor.name = 'floor'
    content.add(floor)
    const wallMat = new THREE.MeshStandardMaterial({ color: col.wall, roughness: 0.95, side: THREE.DoubleSide })
    const back = new THREE.Mesh(new THREE.PlaneGeometry(W, WALL_H), wallMat)
    back.position.set(0, WALL_H / 2, -L / 2); back.receiveShadow = true
    const left = new THREE.Mesh(new THREE.PlaneGeometry(L, WALL_H), wallMat)
    left.rotation.y = Math.PI / 2; left.position.set(-W / 2, WALL_H / 2, 0); left.receiveShadow = true
    content.add(back, left)
    if (photoUrl) {   // the user's own photo, hung on the back wall as a reference picture
      new THREE.TextureLoader().load(photoUrl, (tex) => {
        if (cancelled) return
        tex.colorSpace = THREE.SRGBColorSpace
        const ar = tex.image.width / tex.image.height, h = Math.min(1.2, WALL_H * 0.45), w = h * ar
        const frame = new THREE.Mesh(new THREE.PlaneGeometry(w, h), new THREE.MeshBasicMaterial({ map: tex }))
        frame.position.set(W * 0.1, 1.6, -L / 2 + 0.01)
        content.add(frame)
      })
    }

    const { placed, allFit } = layoutRoom(items, W, L)
    setLayoutInfo({ allFit })
    const movers = []
    setStatus({ loaded: 0, total: items.length, failed: 0 })
    items.forEach((item) => {
      const p = placed[item.category]
      const g = new THREE.Group()
      g.position.set(p.x, 0, p.z); g.rotation.y = p.rotY
      g.userData = { half: { w: p.w / 2, d: p.d / 2 }, category: item.category }
      // stand-in box with the real footprint (shown until the model arrives, or if there is none)
      const h = (item.height_cm || 80) / 100
      const box = new THREE.Mesh(
        new THREE.BoxGeometry((item.width_cm || 80) / 100, h, (item.depth_cm || 80) / 100),
        new THREE.MeshStandardMaterial({ color: item.color_hex || '#9aa5a1', transparent: true, opacity: 0.55 }))
      box.position.y = h / 2; box.castShadow = true
      g.add(box); content.add(g); movers.push(g)
      applyTint(g, colorsRef.current[item.category])
      if (!item.model_url) { setStatus((s) => ({ ...s, loaded: s.loaded + 1 })); return }
      loadModel(`${apiUrl}${item.model_url}`).then((obj) => {
        if (cancelled) return
        let bb = new THREE.Box3().setFromObject(obj), size = bb.getSize(new THREE.Vector3())
        const target = (item.height_cm || 0) / 100
        const s = target > 0 && size.y > 0 ? target / size.y : 1    // scale to the real product height
        obj.scale.setScalar(s)
        bb = new THREE.Box3().setFromObject(obj)
        const c = bb.getCenter(new THREE.Vector3())
        obj.position.set(-c.x, -bb.min.y, -c.z)                     // centre it, feet on the floor
        obj.traverse((m) => { if (m.isMesh) { m.castShadow = true; m.receiveShadow = true } })
        g.remove(box); g.add(obj)
        applyTint(g, colorsRef.current[item.category])
        setStatus((st) => ({ ...st, loaded: st.loaded + 1 }))
      }).catch(() => { if (!cancelled) setStatus((st) => ({ ...st, loaded: st.loaded + 1, failed: st.failed + 1 })) })
    })

    three.current.movers = movers

    // camera: a corner view, looking at the middle of the room
    const R = Math.max(W, L)
    camera.position.set(W * 0.75 + 1, R * 0.75, L * 0.75 + 1.5)
    controls.target.set(0, 0.6, 0); controls.update()

    // ---- drag furniture along the floor ----
    const dom = renderer.domElement, ray = new THREE.Raycaster(), ndc = new THREE.Vector2()
    const plane = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0)
    let drag = null, grab = new THREE.Vector3()
    const setRay = (e) => {
      const r = dom.getBoundingClientRect()
      ndc.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1)
      ray.setFromCamera(ndc, camera)
    }
    const groupOf = (o) => { while (o && !movers.includes(o)) o = o.parent; return o }
    const down = (e) => {
      setRay(e)
      const hit = ray.intersectObjects(movers, true)[0]
      if (!hit) return
      drag = groupOf(hit.object)
      const pt = new THREE.Vector3(); ray.ray.intersectPlane(plane, pt)
      grab.copy(pt).sub(drag.position)
      controls.enabled = false; dom.style.cursor = 'grabbing'
    }
    const move = (e) => {
      setRay(e)
      if (!drag) { dom.style.cursor = ray.intersectObjects(movers, true).length ? 'grab' : 'default'; return }
      const pt = new THREE.Vector3()
      if (!ray.ray.intersectPlane(plane, pt)) return
      const rot = Math.abs(Math.sin(drag.rotation.y)) > 0.5
      const hw = rot ? drag.userData.half.d : drag.userData.half.w, hd = rot ? drag.userData.half.w : drag.userData.half.d
      drag.position.x = Math.min(W / 2 - hw, Math.max(-W / 2 + hw, pt.x - grab.x))
      drag.position.z = Math.min(L / 2 - hd, Math.max(-L / 2 + hd, pt.z - grab.z))
    }
    const up = () => { if (drag) { drag = null; controls.enabled = true; dom.style.cursor = 'default' } }
    dom.addEventListener('pointerdown', down); window.addEventListener('pointermove', move); window.addEventListener('pointerup', up)
    return () => {
      cancelled = true
      dom.removeEventListener('pointerdown', down); window.removeEventListener('pointermove', move); window.removeEventListener('pointerup', up)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key])

  // the user recoloured a piece
  useEffect(() => {
    three.current.movers?.forEach((g) => applyTint(g, colors[g.userData.category]))
  }, [colors, key, status.loaded])

  const view = (top) => {
    const { camera, controls } = three.current, R = Math.max(room.w, room.l)
    if (top) camera.position.set(0.001, R * 1.6, 0.001)
    else camera.position.set(room.w * 0.75 + 1, R * 0.75, room.l * 0.75 + 1.5)
    controls.target.set(0, 0.6, 0); controls.update()
  }

  return (
    <div className="room3d">
      <div className="room3d-bar">
        <div>
          <b>Your room, {room.w} × {room.l} m</b>
          <span className="muted"> · furniture is shown at real size. Drag a piece to move it, drag the background to look around.</span>
        </div>
        <div className="btnrow">
          <button type="button" className="ghost" onClick={() => view(false)}>Corner view</button>
          <button type="button" className="ghost" onClick={() => view(true)}>Top view</button>
          <button type="button" className="ghost" onClick={() => setResetKey((k) => k + 1)}>Reset layout</button>
        </div>
      </div>
      <div className="room3d-stage" ref={mount}>
        {status.loaded < status.total && (
          <div className="room3d-load">Loading 3D models {status.loaded}/{status.total}. The first time can take a minute.</div>
        )}
      </div>
      {!layoutInfo.allFit && <div className="notice warn">These pieces are tight for this room size, so some overlap. Drag them apart, or pick smaller items under Swap.</div>}
      {status.failed > 0 && <div className="notice warn">{status.failed} model(s) could not load, so a grey box with the real size is shown instead.</div>}
    </div>
  )
}
