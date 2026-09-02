import { ref, computed, shallowRef, onUnmounted, watch, type Ref } from 'vue'
import * as Tone from 'tone'
import { Midi } from '@tonejs/midi'
import { authenticatedFetch } from '../api/client'
import {
  normalizePlaybackRate,
  nominalSecondsToTransportTicks,
  scaledTransportBpm,
  toNominalSeconds,
  toPlaybackSeconds,
  transportTicksToNominalSeconds,
  type PlaybackRate,
} from '../utils/jianpuPlayback'

export interface PlayerNote {
  time: number
  duration: number
  midi: number
  name: string
  velocity: number
}

export interface PlayerNoteGroup {
  time: number
  duration: number
  endTime: number
  notes: PlayerNote[]
}

export interface UsePlayerOptions {
  /** MIDI file URL to load automatically */
  midiUrl?: Ref<string>
  defaultRate?: PlaybackRate
}

export function usePlayer(options: UsePlayerOptions = {}) {
  // ── State ──
  const isReady = ref(false)
  const isPlaying = ref(false)
  const isLoading = ref(false)
  const error = ref<string | null>(null)
  const duration = ref(0)
  const currentTime = ref(0)
  const rate = ref<PlaybackRate>(options.defaultRate ?? 1)
  const volume = ref(0) // dB, 0 = full, -Infinity = mute
  const loop = ref(false)
  const loopStart = ref(0)
  const loopEnd = ref(0)

  // Current note index for SVG highlighting
  const currentNoteIndex = ref(-1)

  // ── Internal ──
  const synth = shallowRef<Tone.PolySynth | null>(null)
  const notes: PlayerNote[] = []
  const noteGroups: PlayerNoteGroup[] = []
  let midiData: Midi | null = null
  let animationId: number | null = null
  let scheduledIds: number[] = []
  let scheduleBpm = 120
  let nominalDuration = 0

  // ── Computed ──
  const progress = computed(() => {
    if (duration.value <= 0) return 0
    return Math.min(1, currentTime.value / duration.value)
  })

  const currentTimeFormatted = computed(() => formatTime(currentTime.value))
  const durationFormatted = computed(() => formatTime(duration.value))

  // ── Init audio context (must be called from user gesture) ──
  async function ensureAudioContext(): Promise<void> {
    if (Tone.context.state !== 'running') {
      await Tone.start()
    }
    if (!synth.value) {
      const s = new Tone.PolySynth(Tone.Synth, {
        envelope: {
          attack: 0.02,
          decay: 0.3,
          sustain: 0.4,
          release: 0.8,
        },
        volume: volume.value,
      }).toDestination()
      s.maxPolyphony = 32
      synth.value = s
    }
  }

  // ── Load MIDI ──
  async function loadMidi(url: string): Promise<void> {
    isLoading.value = true
    error.value = null
    isReady.value = false
    currentNoteIndex.value = -1
    notes.length = 0
    noteGroups.length = 0

    try {
      await ensureAudioContext()

      const response = await authenticatedFetch(url)
      if (!response.ok) throw new Error(`HTTP ${response.status}`)
      const arrayBuffer = await response.arrayBuffer()

      midiData = new Midi(arrayBuffer)
      scheduleBpm = midiData.header.tempos[0]?.bpm ?? 120

      // Extract notes from all tracks.
      let maxEnd = 0
      for (const track of midiData.tracks) {
        for (const note of track.notes) {
          const n: PlayerNote = {
            time: note.time,
            duration: note.duration,
            midi: note.midi,
            name: note.name,
            velocity: note.velocity,
          }
          notes.push(n)
          maxEnd = Math.max(maxEnd, note.time + note.duration)
        }
      }

      // Sort by time for highlighting
      notes.sort((a, b) => a.time - b.time)
      rebuildNoteGroups()

      nominalDuration = maxEnd
      duration.value = toPlaybackSeconds(nominalDuration, rate.value)
      loopEnd.value = duration.value
      isReady.value = true

      Tone.getTransport().bpm.value = scaledTransportBpm(scheduleBpm, rate.value)
    } catch (e) {
      error.value = e instanceof Error ? e.message : String(e)
      isReady.value = false
    } finally {
      isLoading.value = false
    }
  }

  // ── Schedule notes on Transport ──
  function scheduleNotes(): void {
    clearSchedule()
    if (!synth.value || notes.length === 0) return

    for (let i = 0; i < notes.length; i++) {
      const note = notes[i]
      const id = Tone.getTransport().schedule((time) => {
        synth.value!.triggerAttackRelease(
          note.name,
          note.duration / rate.value,
          time,
          note.velocity,
        )
      }, `${nominalSecondsToTransportTicks(
        note.time,
        scheduleBpm,
        Tone.getTransport().PPQ,
      )}i`)
      scheduledIds.push(id)
    }
  }

  function clearSchedule(): void {
    for (const id of scheduledIds) {
      Tone.getTransport().clear(id)
    }
    scheduledIds = []
  }

  // ── Playback controls ──
  async function play(): Promise<void> {
    if (!isReady.value) return
    await ensureAudioContext()

    const transport = Tone.getTransport()
    if (transport.state !== 'started') {
      // MIDI 库已经把完整 tempo map 换算为秒，再映射到固定 tick 时间轴。
      // 倍率只改变 tick 速率，因此播放中调速不会破坏谱面位置或曲内变速比例。
      scheduleNotes()
      transport.bpm.value = scaledTransportBpm(scheduleBpm, rate.value)
      transport.start()
    }
    isPlaying.value = true
    startPositionTracking()
  }

  function pause(): void {
    Tone.getTransport().pause()
    isPlaying.value = false
    stopPositionTracking()
  }

  function stop(): void {
    Tone.getTransport().stop()
    Tone.getTransport().position = 0
    isPlaying.value = false
    currentTime.value = 0
    currentNoteIndex.value = -1
    stopPositionTracking()
  }

  function unload(): void {
    stop()
    clearSchedule()
    midiData = null
    notes.length = 0
    noteGroups.length = 0
    nominalDuration = 0
    duration.value = 0
    isReady.value = false
    error.value = null
  }

  function seekTo(ratio: number): void {
    const nominalTarget = ratio * nominalDuration
    setNominalPosition(nominalTarget)
  }

  function seekToTime(seconds: number): void {
    const clamped = Math.max(0, Math.min(seconds, duration.value))
    setNominalPosition(toNominalSeconds(clamped, rate.value))
  }

  function setNominalPosition(nominalSeconds: number): void {
    const transport = Tone.getTransport()
    const clamped = Math.max(0, Math.min(nominalSeconds, nominalDuration))
    transport.ticks = nominalSecondsToTransportTicks(
      clamped,
      scheduleBpm,
      transport.PPQ,
    )
    currentTime.value = toPlaybackSeconds(clamped, rate.value)
    updateCurrentNoteIndex(clamped)
  }

  function nominalPosition(): number {
    const transport = Tone.getTransport()
    return transportTicksToNominalSeconds(
      transport.ticks,
      scheduleBpm,
      transport.PPQ,
    )
  }

  // ── Playback rate ──
  function setRate(value: number): void {
    const nextRate = normalizePlaybackRate(value)
    const position = nominalPosition()
    rate.value = nextRate
    Tone.getTransport().bpm.value = scaledTransportBpm(scheduleBpm, rate.value)
    if (nominalDuration > 0) {
      duration.value = toPlaybackSeconds(nominalDuration, rate.value)
      loopEnd.value = duration.value
      if (loop.value) Tone.getTransport().loopEnd = loopEnd.value
    }
    currentTime.value = toPlaybackSeconds(position, rate.value)
  }

  // ── Volume ──
  function setVolumeDb(db: number): void {
    volume.value = db
    if (synth.value) {
      synth.value.volume.value = db
    }
  }

  function setVolumeRatio(ratio: number): void {
    // ratio 0..1 → dB
    const db = ratio <= 0 ? -Infinity : 20 * Math.log10(ratio)
    setVolumeDb(db)
  }

  // ── Loop ──
  function setLoop(enabled: boolean): void {
    loop.value = enabled
    Tone.getTransport().loop = enabled
    if (enabled) {
      Tone.getTransport().loopStart = loopStart.value
      Tone.getTransport().loopEnd = loopEnd.value
    }
  }

  function setLoopRegion(start: number, end: number): void {
    loopStart.value = start
    loopEnd.value = end
    if (loop.value) {
      Tone.getTransport().loopStart = start
      Tone.getTransport().loopEnd = end
    }
  }

  // ── Position tracking ──
  function startPositionTracking(): void {
    stopPositionTracking()
    const tick = () => {
      if (Tone.getTransport().state === 'started') {
        const nominalTime = nominalPosition()
        currentTime.value = toPlaybackSeconds(nominalTime, rate.value)
        updateCurrentNoteIndex(nominalTime)

        // Auto-stop at end (when not looping)
        if (!loop.value && nominalTime >= nominalDuration) {
          stop()
          return
        }
        animationId = requestAnimationFrame(tick)
      }
    }
    animationId = requestAnimationFrame(tick)
  }

  function stopPositionTracking(): void {
    if (animationId !== null) {
      cancelAnimationFrame(animationId)
      animationId = null
    }
  }

  function updateCurrentNoteIndex(time: number): void {
    // Find the note/chord group that is currently sounding.
    let idx = -1
    const epsilon = 0.02
    for (let i = noteGroups.length - 1; i >= 0; i--) {
      const group = noteGroups[i]
      if (time + epsilon >= group.time && time <= group.endTime + epsilon) {
        idx = i
        break
      }
      if (group.time < time) break
    }
    currentNoteIndex.value = idx
  }

  function rebuildNoteGroups(): void {
    noteGroups.length = 0
    const sameStartEpsilon = 0.001

    for (const note of notes) {
      const endTime = note.time + note.duration
      const previous = noteGroups[noteGroups.length - 1]
      if (previous && Math.abs(previous.time - note.time) <= sameStartEpsilon) {
        previous.notes.push(note)
        previous.endTime = Math.max(previous.endTime, endTime)
        previous.duration = previous.endTime - previous.time
        continue
      }

      noteGroups.push({
        time: note.time,
        duration: note.duration,
        endTime,
        notes: [note],
      })
    }
  }

  // ── Watch URL changes ──
  if (options.midiUrl) {
    watch(options.midiUrl, (url) => {
      if (url) {
        stop()
        void loadMidi(url)
      }
    }, { immediate: true })
  }

  // ── Cleanup ──
  function dispose(): void {
    stop()
    clearSchedule()
    if (synth.value) {
      synth.value.dispose()
      synth.value = null
    }
    midiData = null
    notes.length = 0
    noteGroups.length = 0
    isReady.value = false
  }

  onUnmounted(() => {
    dispose()
  })

  return {
    // State
    isReady: readonlyRef(isReady),
    isPlaying: readonlyRef(isPlaying),
    isLoading: readonlyRef(isLoading),
    error: readonlyRef(error),
    duration: readonlyRef(duration),
    currentTime: readonlyRef(currentTime),
    progress,
    rate: readonlyRef(rate),
    volume: readonlyRef(volume),
    loop: readonlyRef(loop),
    currentNoteIndex: readonlyRef(currentNoteIndex),
    currentTimeFormatted,
    durationFormatted,
    notes,
    noteGroups,

    // Actions
    loadMidi,
    play,
    pause,
    stop,
    unload,
    seekTo,
    seekToTime,
    setRate,
    setVolumeDb,
    setVolumeRatio,
    setLoop,
    setLoopRegion,
    dispose,
  }
}

function readonlyRef<T>(ref: Ref<T>): Readonly<Ref<T>> {
  return ref as Readonly<Ref<T>>
}

function formatTime(seconds: number): string {
  if (!isFinite(seconds) || seconds < 0) return '0:00'
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}
