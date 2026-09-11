import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import ts from 'typescript'

async function load(name) {
  const source = fs.readFileSync(new URL(`../src/renderer/src/utils/${name}.ts`, import.meta.url), 'utf8')
  const code = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ES2022, target: ts.ScriptTarget.ES2022 } }).outputText
  return import(`data:text/javascript;base64,${Buffer.from(code).toString('base64')}`)
}
const { readPlaybackRange, playbackPage, playbackTargets } = await load('playbackNavigation')
const sanitizer = await load('svgSanitizer')
function svg(start, end, notes = []) {
  const attrs = { 'data-playback-version': '1', 'data-playback-ppq': '480', 'data-playback-start-tick': String(start), 'data-playback-end-tick': String(end) }
  return {
    getAttribute: (key) => attrs[key] ?? null,
    querySelectorAll: (selector) => {
      const tick = Number(selector.match(/data-playback-tick="(\d+)"/)[1])
      return notes.filter((note) => note.tick === tick)
    },
  }
}
const ranges = [readPlaybackRange(svg(0, 12000)), readPlaybackRange(svg(12000, 29040)), readPlaybackRange(svg(29040, 38000))]
test('all voices finish before the exact page boundary; seek works in both directions', () => {
  const p = (tick) => ({ tick, onsetTick: tick, ppq: 480 })
  assert.equal(playbackPage(ranges, p(29039)), 1)
  assert.equal(playbackPage(ranges, p(29040)), 2)
  assert.equal(playbackPage(ranges, p(100)), 0)
  assert.equal(playbackPage(ranges, p(-1)), null)
  assert.equal(playbackPage([null, ranges[1]], p(12000)), 1)
  assert.equal(playbackPage([], p(29040)), null)
})
test('rest positions navigate using clock tick while onset highlight is absent', () => {
  const position = { tick: 29040, onsetTick: -1, ppq: 480 }
  assert.equal(playbackPage(ranges, position), 2)
  assert.deepEqual(playbackTargets(svg(29040, 38000), position), [])
})
test('newly loaded next page highlights both voices without an index fallback', () => {
  const targets = [{ tick: 29040, part: 0 }, { tick: 29040, part: 1 }, { tick: 29160, part: 0 }]
  const position = { tick: 29040, onsetTick: 29040, ppq: 480 }
  assert.deepEqual(playbackTargets(svg(12000, 29040), position), [])
  assert.deepEqual(playbackTargets(svg(29040, 38000, targets), position), targets.slice(0, 2))
  assert.deepEqual(playbackTargets(svg(29040, 38000, targets), { ...position, onsetTick: 232 }), [])
})
test('history metadata survives sanitization and PPQ conversion', () => {
  for (const key of ['data-playback-version', 'data-playback-ppq', 'data-playback-start-tick', 'data-playback-end-tick', 'data-playback-tick', 'data-part-index']) {
    assert.equal(sanitizer.isAllowedSvgAttribute('g', key), true)
    assert.equal(sanitizer.isSafeSvgAttributeValue('g', key, '29040'), true)
  }
  assert.equal(playbackPage(ranges, { tick: 58080, onsetTick: 58080, ppq: 960 }), 2)
  assert.equal(readPlaybackRange({ getAttribute: () => null }), null)
  assert.equal(readPlaybackRange(svg(3, 2)), null)
})
