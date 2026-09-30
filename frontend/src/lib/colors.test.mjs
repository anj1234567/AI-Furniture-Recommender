import assert from 'node:assert'
import { hexToRgb, rgbToHsl, hslToHex, harmony, suggestColors, autoAssign, roomInfo } from './colors.js'
// round trip
for (const hex of ['#a9784f', '#336699', '#ffffff', '#101010', '#e8e4dc']) {
  const [h, s, l] = rgbToHsl(...hexToRgb(hex)); const back = hslToHex(h, s, l)
  const d = hexToRgb(hex).map((v, i) => Math.abs(v - hexToRgb(back)[i])); assert(Math.max(...d) <= 2, `${hex} -> ${back}`)
}
const warmRoom = ['#e9dfd0', '#b8946a', '#7a5a3a', '#cfc5b8', '#3b3128']       // beige walls, wood floor
const blueRoom = ['#dfe6ee', '#4f7fb0', '#2c4a6b', '#c9d3de', '#20262e']
assert(roomInfo(warmRoom).warm && !roomInfo(blueRoom).warm)
assert(harmony('#ffffff', warmRoom).score > 0.8, 'white is neutral')
assert(harmony('#b0824f', warmRoom).score > 0.85, 'brown blends into a wood room')
assert(harmony('#3a86d8', warmRoom).score < harmony('#b0824f', warmRoom).score, 'blue clashes more than wood in a warm room')
assert(harmony('#d8863a', blueRoom).label.includes('complementary'), 'orange vs blue room')
assert(harmony(null, warmRoom).score === null)
const s = suggestColors(warmRoom); assert(s.length >= 6 && s.every((c) => /^#[0-9a-f]{6}$/.test(c.hex)))
assert(s.every((c) => c.score >= 0.3), 'all suggestions are reasonable: ' + JSON.stringify(s.map((c) => [c.key, c.score])))
const a = autoAssign(['bed', 'sofa', 'table', 'chair'], blueRoom); assert(Object.keys(a).length === 4)
console.log('colors ok', s.map((c) => `${c.key}:${c.hex}:${c.score.toFixed(2)}`).join(' '))
console.log('auto', JSON.stringify(a))
console.log('scores: white', harmony('#ffffff', warmRoom).score, 'sofa-blue', harmony('#3a86d8', warmRoom).score.toFixed(2))
