import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'
import { spawnSync } from 'node:child_process'
import ts from 'typescript'
import midiPackage from '@tonejs/midi'
const { Midi } = midiPackage

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const urlOf = (js) => `data:text/javascript;base64,${Buffer.from(js).toString('base64')}`
const compile = (source) => ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } }).outputText
const sourceMapUrl = urlOf(compile(fs.readFileSync(path.join(root, 'desktop/src/renderer/src/utils/midiSourceMap.ts'), 'utf8')))
const { readMidiSourceMap, sourcePlaybackPosition, sourceRangeSpans, playbackTextHash } = await import(sourceMapUrl)
const marker = (ticks, data) => ({ ticks, type: 'marker', text: 'score-trans-playback:' + JSON.stringify(data) })
const header = marker(0, { kind: 'document', version: 1, source_kind: 'score', text_hash: null })
const visits = [header, marker(0, { kind: 'measure', score_tick: 0, end_tick: 1920 }), marker(1920, { kind: 'measure', score_tick: 0, end_tick: 3840 }), marker(3840, { kind: 'measure', score_tick: 1920, end_tick: 5760 })]
const meta = [...visits, ...Array.from({ length: 12 }, (_, i) => marker(i * 480, { kind: 'onset', score_tick: (i < 4 ? i : i - 4) * 480, score_group: i < 4 ? i : i - 4, ranges: [] }))]

test('repeat boundary, seek, rests and final boundary map to source coordinates', () => {
  const map = readMidiSourceMap(meta)
  assert.ok(map)
  assert.equal(sourcePlaybackPosition(map, 1919, 1440, 480).position.tick, 1919)
  assert.deepEqual(sourcePlaybackPosition(map, 1920, 1920, 480).position, { tick: 0, onsetTick: 0, ppq: 480 })
  assert.equal(sourcePlaybackPosition(map, 2401, 2400, 480).groupIndex, 1)
  assert.equal(sourcePlaybackPosition(map, 3840, 3840, 480).position.onsetTick, 1920)
  const rest = sourcePlaybackPosition(map, 2400, -1, 480)
  assert.equal(rest.position.tick, 480)
  assert.equal(rest.groupIndex, -1)
  assert.equal(sourcePlaybackPosition(map, 5760, 5280, 480).position.tick, -1)
})

test('invalid or unknown mapping never returns guessed highlight positions', () => {
  const invalid = [[], [{...header, text: 'score-trans-playback:{'}], [{...header, text: header.text.replace('"version":1', '"version":2')}, ...meta.slice(1)], [...meta, meta[1]], meta.filter((m) => m !== meta[0]), [...meta, marker(500, {kind:'onset',score_tick:-1,score_group:0,ranges:[]})]]
  for (const data of invalid) assert.equal(readMidiSourceMap(data), null)
  assert.equal(sourcePlaybackPosition(null, 0, 0, 480).groupIndex, -1)
})

test('UTF-16 ranges support simultaneous voices, CRLF and surrogate pairs', async () => {
  const text = '// 😀\r\n1 & w6,\r\n'
  const start = text.indexOf('1')
  const ranges = [{start,end:start+1}, {start:start+4,end:start+7}]
  assert.deepEqual(sourceRangeSpans(text, ranges), [{line:1,startColumn:0,endColumn:1}, {line:1,startColumn:4,endColumn:7}])
  assert.deepEqual(sourceRangeSpans(text, [{start:-1,end:1},{start:0,end:999}]), [])
  assert.equal((await playbackTextHash(text)).length, 64)
})

function exportedMidi(sourceText = `1=C
4/4
|: 1 2 3 4 :| 5 6 7 1' |`) {
  const python = path.join(root, process.platform === 'win32' ? '.venv/Scripts/python.exe' : '.venv/bin/python')
  const result = spawnSync(python, ['-c', String.raw`
from pathlib import Path
from tempfile import TemporaryDirectory
import base64, hashlib, sys
from score_trans.utils.env import load_project_env
load_project_env(Path('backend/score_trans/config/env.example'))
from score_trans.domain.parse.jianpu_text import parse_jianpu_parts
from score_trans.models.playback import PlaybackTextSource
from score_trans.services.export.export_service import ExportService
text=sys.stdin.read()
parts=parse_jianpu_parts(text)
source=PlaybackTextSource(hashlib.sha256(text.encode()).hexdigest())
for part in parts:
 for measure in part.score.measures:
  for event in measure.events:
   if event.source_start_utf16 is not None and event.source_end_utf16 is not None:
    source.event_ranges[id(event)]=(part.body_start_utf16+event.source_start_utf16,part.body_start_utf16+event.source_end_utf16)
with TemporaryDirectory() as tmp:
 p=ExportService().export_midi_scores([part.score for part in parts],Path(tmp)/'repeat.mid',text_source=source)
 print(base64.b64encode(p.read_bytes()).decode())
`], {cwd:root,env:{...process.env,PYTHONPATH:path.join(root,'backend'),SCORE_TRANS_API_AUTH_DISABLED:'1'},encoding:'utf8',input:sourceText})
  assert.equal(result.status, 0, result.stderr)
  return Buffer.from(result.stdout.trim(), 'base64')
}
const midiBytes = exportedMidi()

test('Python MIDI export roundtrips through the actual @tonejs/midi parser', () => {
  const midi = new Midi(midiBytes)
  const map = readMidiSourceMap(midi.header.meta)
  assert.ok(map)
  const groups = midi.tracks[0].notes.map((note) => sourcePlaybackPosition(map, note.ticks, note.ticks, midi.header.ppq).groupIndex)
  assert.deepEqual(groups, [0,1,2,3,0,1,2,3,4,5,6,7])
})

const vueUrl = urlOf(`export const ref=(value)=>({value}); export const shallowRef=ref; export const computed=(fn)=>({get value(){return fn()}}); export const watch=()=>{}; export const onUnmounted=()=>{};`)
const transport = { state:'stopped',ticks:0,PPQ:480,bpm:{value:120},position:0,start(){this.state='started'},stop(){this.state='stopped';this.ticks=0},pause(){this.state='paused'},schedule(){return 1},clear(){} }
globalThis.__repeatTransport = transport
const toneUrl = urlOf(`export const context={state:'running'}; export const start=async()=>{}; export const Synth=class{}; export const getTransport=()=>globalThis.__repeatTransport; export class PolySynth {toDestination(){return this} triggerAttackRelease(){} dispose(){}}`)
const clientUrl = urlOf('export const authenticatedFetch=(...args)=>globalThis.__repeatFetch(...args)')
const cache = new Map()
async function moduleUrl(file) {
  file = path.resolve(file)
  if (cache.has(file)) return cache.get(file)
  let source = fs.readFileSync(file, 'utf8')
  for (const spec of new Set([...source.matchAll(/from '([^']+)'/g)].map((m)=>m[1]))) {
    let dependency
    if (spec==='vue') dependency=vueUrl
    else if(spec==='tone') dependency=toneUrl
    else if(spec==='@tonejs/midi') dependency=urlOf('export const Midi=globalThis.__repeatMidi')
    else if(spec==='../api/client') dependency=clientUrl
    else if(spec.startsWith('.')) dependency=await moduleUrl(path.resolve(path.dirname(file),spec+'.ts'))
    else continue
    source=source.replaceAll(`from '${spec}'`,`from '${dependency}'`)
  }
  const url=urlOf(compile(source));cache.set(file,url);return url
}
globalThis.__repeatMidi=Midi
let playbackFrame
globalThis.requestAnimationFrame=(callback)=>{ playbackFrame=callback; return 1 }
globalThis.cancelAnimationFrame=()=>{}
const {usePlayer}=await import(await moduleUrl(path.join(root,'desktop/src/renderer/src/composables/usePlayer.ts')))
const response = (bytes=midiBytes) => ({ok:true,arrayBuffer:async()=>bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength)})

test('actual player uses mapped coordinates after seeking and changing rate', async () => {
  globalThis.__repeatFetch=async()=>response()
  const player=usePlayer()
  await player.loadMidi('current')
  assert.equal(player.sourceMapReady.value,true)
  player.seekToTime(2)
  assert.equal(player.playbackPosition.value.tick,0)
  assert.equal(player.currentPlaybackGroupIndex.value,0)
  player.seekToTime(4)
  assert.equal(player.currentPlaybackGroupIndex.value,4)
  player.setRate(2)
  assert.equal(player.currentPlaybackGroupIndex.value,4)
  player.stop()
  assert.equal(player.playbackPosition.value.tick,-1)
})

test('late MIDI fetch and unload cannot overwrite the latest source map', async () => {
  let release
  globalThis.__repeatFetch=(url)=>url==='old'?new Promise((resolve)=>{release=resolve}):Promise.resolve(response())
  const player=usePlayer()
  const old=player.loadMidi('old')
  await Promise.resolve()
  await player.loadMidi('new')
  player.seekToTime(2)
  release(response(Buffer.from([0])))
  await old
  assert.equal(player.error.value,null)
  assert.equal(player.sourceMapReady.value,true)
  assert.equal(player.currentPlaybackGroupIndex.value,0)
  const pending=player.loadMidi('old')
  await Promise.resolve()
  player.unload()
  release(response())
  await pending
  assert.equal(player.isReady.value,false)
  assert.equal(player.sourceMapReady.value,false)
})

test('legacy MIDI still plays while source highlights remain disabled', async () => {
  const legacy = new Midi(midiBytes)
  legacy.header.meta = []
  const bytes = Buffer.from(legacy.toArray())
  globalThis.__repeatFetch=async()=>response(bytes)
  const player=usePlayer()
  await player.loadMidi('legacy')
  assert.equal(player.isReady.value,true)
  assert.equal(player.sourceMapReady.value,false)
  player.seekToTime(2)
  assert.equal(player.currentPlaybackGroupIndex.value,-1)
  assert.equal(player.playbackPosition.value.onsetTick,-1)
  assert.deepEqual(player.playbackHighlight.value.ranges,[])
})

test('source mismatch and repeated stop never expose stale text ranges', async () => {
  globalThis.__repeatFetch=async()=>response()
  const player=usePlayer()
  await player.loadMidi('wrong-source','a'.repeat(64))
  assert.equal(player.sourceMapReady.value,false)
  player.seekToTime(2)
  assert.equal(player.currentPlaybackGroupIndex.value,-1)
  player.stop()
  player.stop()
  assert.deepEqual(player.playbackHighlight.value.ranges,[])
})

async function polyphonicPlayer(body) {
  const text = '1=C\n4/4\n' + body
  const bytes = exportedMidi(text)
  globalThis.__repeatFetch = async () => response(bytes)
  const player = usePlayer()
  await player.loadMidi('polyphonic', await playbackTextHash(text))
  const tokens = () => player.playbackHighlight.value.ranges.map((r) => text.slice(r.start, r.end))
  const advance = (seconds) => { transport.ticks = seconds * 960; playbackFrame() }
  return { player, tokens, advance }
}

test('later chords do not erase the sustained bass text highlight', async () => {
  const { player, tokens } = await polyphonicPlayer('0 [3+#1] [3+#1] [3+#1] & w6, |')
  player.seekToTime(.625)
  assert.deepEqual(tokens(), ['[3+#1]', 'w6,'])
  player.seekToTime(1.125)
  assert.deepEqual(tokens(), ['[3+#1]', 'w6,'])
  player.unload()
})

test('note-off updates only that event while a long voice remains active', async () => {
  const { player, tokens, advance } = await polyphonicPlayer('w1 & 6 0 0 0 |')
  await player.play()
  advance(.25)
  assert.deepEqual(tokens(), ['w1', '6'])
  const focus = player.playbackHighlight.value.focusRange
  advance(.75)
  assert.deepEqual(tokens(), ['w1'])
  assert.equal(player.playbackHighlight.value.focusRange, focus, 'note-off must not scroll')
  const stable = player.playbackHighlight.value
  advance(.8)
  assert.equal(player.playbackHighlight.value, stable, 'no per-frame highlight rebuild')
  player.unload()
})

test('short voice gap cannot hide an earlier still-sounding voice', async () => {
  const { player, tokens } = await polyphonicPlayer('0 q1 0 0 & w6, |')
  player.seekToTime(.625)
  assert.deepEqual(tokens(), ['q1', 'w6,'])
  player.seekToTime(.9375)
  assert.deepEqual(tokens(), ['w6,'])
  player.unload()
})

test('three voices enter and finish independently, including identical pitches', async () => {
  const { player, tokens } = await polyphonicPlayer('w1 & h1 0 0 & 0 0 3 0 |')
  player.seekToTime(.25)
  assert.deepEqual(tokens(), ['w1', 'h1'])
  player.seekToTime(1.25)
  assert.deepEqual(tokens(), ['w1', '3'])
  player.seekToTime(1.75)
  assert.deepEqual(tokens(), ['w1'])
  player.unload()
})

test('repeat and loop jumps restore all active ranges with new occurrence identities', async () => {
  const { player, tokens, advance } = await polyphonicPlayer('|: 0 [3+#1] [3+#1] [3+#1] & w6, :|')
  await player.play()
  advance(.625)
  assert.deepEqual(tokens(), ['[3+#1]', 'w6,'])
  const first = player.playbackHighlight.value
  advance(2.625)
  assert.deepEqual(player.playbackHighlight.value.ranges, first.ranges)
  assert.notEqual(player.playbackHighlight.value.focusEventId, first.focusEventId)
  const repeated = player.playbackHighlight.value
  player.pause()
  assert.equal(player.playbackHighlight.value, repeated)
  await player.play()
  advance(.625)
  assert.deepEqual(player.playbackHighlight.value.ranges, first.ranges)
  assert.equal(player.playbackHighlight.value.focusEventId, first.focusEventId)
  player.setRate(2)
  assert.deepEqual(tokens(), ['[3+#1]', 'w6,'])
  player.unload()
  assert.equal(player.playbackHighlight.value.focusRange, null)
})

test('v1 remains usable for score navigation but cannot guess sustained text ranges', async () => {
  const legacy = new Midi(midiBytes)
  legacy.header.meta = legacy.header.meta.map((marker) => {
    const data = JSON.parse(marker.text.slice('score-trans-playback:'.length))
    if (data.kind === 'document') data.version = 1
    delete data.events
    return { ...marker, text: 'score-trans-playback:' + JSON.stringify(data) }
  })
  globalThis.__repeatFetch = async () => response(Buffer.from(legacy.toArray()))
  const player = usePlayer()
  await player.loadMidi('v1')
  assert.equal(player.sourceMapReady.value, true)
  assert.equal(player.intervalTrackingReady.value, false)
  player.seekToTime(2)
  assert.equal(player.currentPlaybackGroupIndex.value, 0)
  assert.deepEqual(player.playbackHighlight.value.ranges, [])
  player.unload()
})

test('invalid event intervals invalidate v2 without affecting v1 decoding', () => {
  const valid = new Midi(midiBytes).header.meta
  for (const corrupt of [
    (data, tick) => { data.events[0].end_tick = tick },
    (data) => { data.events[0].end_tick = Number.NaN },
    (data) => { data.events.push({...data.events[0]}) },
    (data) => { data.events[0].ranges = [{start:7,end:2}] },
    (data) => { data.events[0].part_index = -1 },
  ]) {
    let changed = false
    const bad = valid.map((marker) => {
      const data = JSON.parse(marker.text.slice('score-trans-playback:'.length))
      if (data.kind === 'onset' && !changed) { corrupt(data, marker.ticks); changed = true }
      return { ...marker, text: 'score-trans-playback:' + JSON.stringify(data) }
    })
    assert.equal(readMidiSourceMap(bad), null)
  }
})
