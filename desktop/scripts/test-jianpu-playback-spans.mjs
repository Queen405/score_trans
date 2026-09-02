import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import ts from 'typescript'

function compile(source) {
  return ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.ESNext,
      target: ts.ScriptTarget.ES2022,
    },
  }).outputText
}

function moduleUrl(javascript) {
  return `data:text/javascript;base64,${Buffer.from(javascript).toString('base64')}`
}

// Inline the relative import graph so each module can be loaded as a data: URL.
const inlinedByPath = new Map()

async function inlineModule(relativePath) {
  const url = new URL(relativePath, import.meta.url)
  const cached = inlinedByPath.get(url.href)
  if (cached) return cached
  let source = await readFile(url, 'utf8')
  const specifiers = new Set(
    Array.from(source.matchAll(/from '(\.[^']+)'/g), (match) => match[1]),
  )
  for (const specifier of specifiers) {
    const dependency = await inlineModule(new URL(`${specifier}.ts`, url).href)
    source = source.replaceAll(`from '${specifier}'`, `from '${dependency}'`)
  }
  const inlined = moduleUrl(compile(source))
  inlinedByPath.set(url.href, inlined)
  return inlined
}

async function loadModule(relativePath) {
  return import(await inlineModule(relativePath))
}

const {
  PLAYBACK_RATES,
  findJianpuNoteSpans,
  isPlayableToken,
  nominalSecondsToTransportTicks,
  rescalePlaybackPosition,
  scaledTransportBpm,
  toNominalSeconds,
  toPlaybackSeconds,
  transportTicksToNominalSeconds,
} = await loadModule(
  '../src/renderer/src/utils/jianpuPlayback.ts',
)
const { transposeOctave } = await loadModule('../src/renderer/src/utils/jianpuTranspose.ts')
const { tokenizeJianpuLine } = await loadModule('../src/renderer/src/utils/jianpuSyntax.ts')

const tokensOf = (text) => findJianpuNoteSpans(text).map((span) => span.token)
const highlightTypeOf = (token) =>
  tokenizeJianpuLine(token)
    .map((span) => span.type)
    .join(',')

test('playback rate scales tempo and seconds without changing the score tempo map', () => {
  assert.deepEqual(PLAYBACK_RATES, [0.5, 0.8, 1, 1.5, 2])
  for (const rate of PLAYBACK_RATES) {
    const playbackSeconds = toPlaybackSeconds(12, rate)
    assert.equal(toNominalSeconds(playbackSeconds, rate), 12)
  }
  assert.equal(scaledTransportBpm(120, 0.5), 60)
  assert.equal(scaledTransportBpm(80, 0.5), 40)
  assert.equal(toPlaybackSeconds(10, 2), 5)
  assert.equal(rescalePlaybackPosition(10, 1, 0.5), 20)
  assert.equal(rescalePlaybackPosition(10, 1, 2), 5)
  assert.equal(nominalSecondsToTransportTicks(3, 120, 192), 1152)
  assert.equal(transportTicksToNominalSeconds(1152, 120, 192), 3)
})

// The playback highlight matches `span.index === currentNoteIndex`, where the
// index comes from the MIDI the backend generated for the same text. So the span
// count must equal the backend's pitched-event count for every construct, or the
// highlight silently drifts by the difference from that point on.

test('a bare dotted note counts as a note, not a pasted measure label', () => {
  // `5.` is a dotted quarter (docs/jianpu-syntax.md 5.2). A `/^\d+[.:：]$/` guard
  // used to swallow it as a measure number, undercounting every such note.
  assert.deepEqual(tokensOf("1=C\n2/4\n6. q1' |\n2. q4 |"), ['6.', "q1'", '2.', 'q4'])
  for (const degree of [1, 2, 3, 4, 5, 6, 7]) {
    assert.equal(isPlayableToken(`${degree}.`), true, `${degree}. must be a dotted note`)
  }
})

test('pasted measure labels are still skipped', () => {
  // Colon-separated, or dot-separated above the 1-7 degree range.
  assert.deepEqual(tokensOf('1=C\n2/4\n12: 5 5 |'), ['5', '5'])
  assert.deepEqual(tokensOf('1=C\n2/4\n10. 5 |'), ['5'])
  assert.equal(isPlayableToken('272:'), false)
  assert.equal(isPlayableToken('8.'), false)
})

test('dotted and double-dotted rests are still skipped', () => {
  assert.deepEqual(tokensOf('1=C\n2/4\n0. q0 |'), [])
  assert.equal(isPlayableToken('0..'), false)
})

test('a double-dotted note counts as a note', () => {
  // The backend consumes every trailing dot (jianpu_tokens.py consume_duration_suffix).
  assert.deepEqual(tokensOf("1=C\n4/4\n6.. s1' |"), ['6..', "s1'"])
})

test('the editor colours a token the same way playback and the backend read it', () => {
  // jianpuSyntax and jianpuPlayback keep separate copies of stripEventDecorations.
  // When only one learned to strip every trailing dot, `6..` played and highlighted
  // as a note while the editor greyed it out as unrecognised text.
  assert.equal(highlightTypeOf('6.'), 'note')
  assert.equal(highlightTypeOf('6..'), 'note')
  assert.equal(highlightTypeOf('0.'), 'rest')
  assert.equal(highlightTypeOf('0..'), 'rest')
  assert.equal(highlightTypeOf('10.'), 'plain')
  assert.equal(highlightTypeOf('12:'), 'plain')
})

test('inline tempo keeps note highlighting and playback spans', () => {
  const line = 'tempo=80 5 6 7 1 |'
  assert.deepEqual(tokensOf(`1=C\n4/4\n${line}`), ['5', '6', '7', '1'])
  assert.deepEqual(
    tokenizeJianpuLine(line).filter((token) => token.type !== 'plain').map((token) => [
      token.text,
      token.type,
    ]),
    [['tempo=80', 'metadata'], ['5', 'note'], ['6', 'note'], ['7', 'note'], ['1', 'note'], ['|', 'barline']],
  )
})

test('octave transpose moves bare dotted notes with everything else', () => {
  // transposeOctave gates on isPlayableToken, so the same guard used to leave
  // dotted notes behind while shifting their neighbours — corrupting the melody.
  // The octave mark sits before the dot; the backend rejects `6.'`.
  assert.equal(transposeOctave("1=C\n2/4\n6. q1' |\n2. q4 |", 1), "1=C\n2/4\n6'. q1'' |\n2'. q4' |")
  assert.equal(transposeOctave("1=C\n2/4\n6'. q1' |", -1), '1=C\n2/4\n6. q1 |')
})

test('span count matches the backend note count on a real score', async () => {
  // Shared with tests/test_jianpu.py::test_playback_alignment_fixture_note_count,
  // which pins the same file to the same number on the backend side. One fixture,
  // two assertions — a copy per stack would drift and stop proving anything.
  const text = await readFile(
    new URL('../../tests/fixtures/playback_alignment.jianpu', import.meta.url),
    'utf8',
  )
  assert.equal(findJianpuNoteSpans(text).length, 180)
})
