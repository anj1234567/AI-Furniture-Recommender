// Colour helpers: which colours go with the room's palette, and suggestions for recolouring
// furniture. Plain maths (no three.js) so it can be tested on its own (colors.test.mjs).
// The rules are the usual colour-theory ones: neutrals go with everything, colours
// close in hue (analogous) blend in, opposite hues (complementary) make an accent.

export function hexToRgb(hex) {
  const h = hex.replace('#', '')
  const v = h.length === 3 ? h.split('').map((c) => c + c).join('') : h
  return [parseInt(v.slice(0, 2), 16), parseInt(v.slice(2, 4), 16), parseInt(v.slice(4, 6), 16)]
}
export const rgbToHex = (r, g, b) =>
  '#' + [r, g, b].map((x) => Math.max(0, Math.min(255, Math.round(x))).toString(16).padStart(2, '0')).join('')

export function rgbToHsl(r, g, b) {
  r /= 255; g /= 255; b /= 255
  const mx = Math.max(r, g, b), mn = Math.min(r, g, b), l = (mx + mn) / 2, d = mx - mn
  if (d === 0) return [0, 0, l]
  const s = l > 0.5 ? d / (2 - mx - mn) : d / (mx + mn)
  let h
  if (mx === r) h = ((g - b) / d + (g < b ? 6 : 0))
  else if (mx === g) h = (b - r) / d + 2
  else h = (r - g) / d + 4
  return [h * 60, s, l]
}
export function hslToHex(h, s, l) {
  h = ((h % 360) + 360) % 360
  const c = (1 - Math.abs(2 * l - 1)) * s, x = c * (1 - Math.abs(((h / 60) % 2) - 1)), m = l - c / 2
  const [r, g, b] = h < 60 ? [c, x, 0] : h < 120 ? [x, c, 0] : h < 180 ? [0, c, x] : h < 240 ? [0, x, c] : h < 300 ? [x, 0, c] : [c, 0, x]
  return rgbToHex((r + m) * 255, (g + m) * 255, (b + m) * 255)
}
export const hslOf = (hex) => rgbToHsl(...hexToRgb(hex))
const hueDiff = (a, b) => { const d = Math.abs(a - b) % 360; return d > 180 ? 360 - d : d }
const clamp = (v, a, b) => Math.max(a, Math.min(b, v))

const isNeutral = ([, s, l]) => s < 0.14 || l > 0.93 || l < 0.08

// What is the room made of? lightest colour = walls, darker mid colour = floor,
// dominant hue = the most saturated colour that is not a neutral.
export function roomInfo(palette) {
  const list = (palette?.length ? palette : ['#e8e4dc', '#8a7358']).map((hex) => ({ hex, hsl: hslOf(hex) }))
  const byL = [...list].sort((a, b) => b.hsl[2] - a.hsl[2])
  const chromatic = list.filter((c) => !isNeutral(c.hsl)).sort((a, b) => b.hsl[1] * (1 - Math.abs(b.hsl[2] - 0.5)) - a.hsl[1] * (1 - Math.abs(a.hsl[2] - 0.5)))
  const main = chromatic[0]?.hsl ?? null
  const hue = main ? main[0] : 35                               // all-neutral room: assume a warm undertone
  const warm = hue < 75 || hue > 335
  return { wall: byL[0].hex, floor: byL[Math.min(byL.length - 1, Math.floor(byL.length * 0.7))].hex, hue, warm, main, chromatic: chromatic.map((c) => c.hsl) }
}

// How well does this colour go with the room? 0..1 plus a plain-words reason.
export function harmony(hex, palette) {
  if (!hex) return { score: null, label: 'colour unknown' }
  const hsl = hslOf(hex), [h, s] = hsl
  if (isNeutral(hsl)) return { score: 0.85, label: 'neutral, goes with almost anything' }
  const info = roomInfo(palette)
  const vivid = Math.max(0, s - 0.6) * 0.3
  if (!info.chromatic.length) return { score: clamp(0.62 - vivid, 0.3, 0.7), label: 'an accent colour in a neutral room' }
  const d = Math.min(...info.chromatic.map((c) => hueDiff(h, c[0])))
  if (d <= 25) return { score: clamp(0.95 - d / 250 - vivid, 0, 1), label: 'blends with your room colours' }
  if (d >= 150) return { score: clamp(0.8 - vivid, 0, 1), label: 'complementary accent' }
  if (d >= 100) return { score: clamp(0.55 - vivid, 0, 1), label: 'a bold contrast' }
  return { score: clamp(0.35 - vivid, 0, 1), label: 'may clash with your room colours' }
}

// Colours to offer for a piece of furniture, all derived from the photo's palette.
export function suggestColors(palette) {
  const info = roomInfo(palette)
  const H = info.hue, [wh, ws, wl] = hslOf(info.wall), [fh, fs, fl] = hslOf(info.floor)
  const out = [
    { key: 'soft', label: 'Soft neutral', hex: hslToHex(H, info.warm ? 0.16 : 0.08, 0.9) },
    { key: 'walls', label: 'From your walls', hex: hslToHex(wh, clamp(ws, 0.05, 0.4), clamp(wl - 0.08, 0.5, 0.82)) },
    { key: 'greige', label: 'Greige', hex: hslToHex(H, info.warm ? 0.12 : 0.06, 0.62) },
    { key: 'floor', label: 'From your floor', hex: hslToHex(fh, clamp(fs, 0.1, 0.5), clamp(fl, 0.25, 0.5)) },
    { key: 'analogous', label: 'Blends in', hex: hslToHex(info.warm ? H - 18 : H + 25, 0.34, 0.46) },
    { key: 'accent', label: 'Accent', hex: hslToHex(H + 180, 0.36, 0.42) },
    { key: 'deep', label: 'Deep tone', hex: hslToHex(H, 0.3, 0.26) },
    { key: 'wood', label: 'Natural wood', hex: info.warm ? '#a9784f' : '#b3a58e' },
  ]
  const seen = new Set()
  return out.filter((c) => !seen.has(c.hex) && seen.add(c.hex)).map((c) => ({ ...c, ...harmony(c.hex, palette) }))
}

// One sensible colour per category (used by the "Match my room" button).
const ROLE = { bed: 'soft', sofa: 'analogous', table: 'wood', chair: 'accent' }
export function autoAssign(categories, palette) {
  const s = suggestColors(palette), by = Object.fromEntries(s.map((c) => [c.key, c.hex]))
  const out = {}
  categories.forEach((cat, i) => { out[cat] = by[ROLE[cat]] ?? s[i % s.length].hex })
  return out
}
