<template>
  <div
    v-if="visible"
    class="jianpu-player"
  >
    <div class="player-left">
      <button
        class="player-btn play-btn"
        :disabled="!player.isReady.value"
        :title="player.isPlaying.value ? '暂停' : '播放'"
        @click="togglePlay"
      >
        <svg
          v-if="!player.isPlaying.value"
          viewBox="0 0 24 24"
          fill="currentColor"
        ><path d="M8 5v14l11-7z" /></svg>
        <svg
          v-else
          viewBox="0 0 24 24"
          fill="currentColor"
        ><path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z" /></svg>
      </button>
      <button
        class="player-btn"
        :disabled="!player.isReady.value"
        title="停止"
        @click="stopPlayback"
      >
        <svg
          viewBox="0 0 24 24"
          fill="currentColor"
        ><rect
          x="6"
          y="6"
          width="12"
          height="12"
        /></svg>
      </button>
      <span class="player-time">{{ player.currentTimeFormatted.value }} / {{ player.durationFormatted.value }}</span>
    </div>

    <div class="player-center">
      <div
        ref="progressRef"
        class="progress-bar"
        @mousedown="onProgressDown"
      >
        <div class="progress-track">
          <div
            class="progress-fill"
            :style="{ width: `${player.progress.value * 100}%` }"
          />
          <div
            class="progress-thumb"
            :style="{ left: `${player.progress.value * 100}%` }"
          />
        </div>
      </div>
    </div>

    <div class="player-right">
      <div
        class="tempo-control"
        title="速度"
      >
        <svg
          class="tempo-icon"
          viewBox="0 0 24 24"
          fill="currentColor"
        ><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.42 0-8-3.58-8-8s3.58-8 8-8 8 3.58 8 8-3.58 8-8 8zm-.5-13H11v6l5.25 3.15.75-1.23-4.5-2.67V7z" /></svg>
        <n-select
          :value="player.rate.value"
          :options="rateOptions"
          size="tiny"
          style="width: 72px"
          :consistent-menu-width="false"
          aria-label="播放倍率"
          @update:value="handleRateChange"
        />
      </div>
      <div
        class="volume-control"
        title="音量"
      >
        <button
          class="player-btn-sm"
          @click="toggleMute"
        >
          <svg
            v-if="isMuted || player.volume.value <= -50"
            viewBox="0 0 24 24"
            fill="currentColor"
          ><path d="M16.5 12c0-1.77-1.02-3.29-2.5-4.03v2.21l2.45 2.45c.03-.2.05-.41.05-.63zm2.5 0c0 .94-.2 1.82-.54 2.64l1.51 1.51A8.796 8.796 0 0021 12c0-4.28-2.99-7.86-7-8.77v2.06c2.89.86 5 3.54 5 6.71zM4.27 3L3 4.27 7.73 9H3v6h4l5 5v-6.73l4.25 4.25c-.67.52-1.42.93-2.25 1.18v2.06a8.99 8.99 0 003.69-1.81L19.73 21 21 19.73l-9-9L4.27 3zM12 4L9.91 6.09 12 8.18V4z" /></svg>
          <svg
            v-else-if="player.volume.value < -10"
            viewBox="0 0 24 24"
            fill="currentColor"
          ><path d="M18.5 12c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02zM5 9v6h4l5 5V4L9 9H5z" /></svg>
          <svg
            v-else
            viewBox="0 0 24 24"
            fill="currentColor"
          ><path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z" /></svg>
        </button>
        <n-slider
          :value="volumeRatio"
          :min="0"
          :max="1"
          :step="0.01"
          style="width: 80px"
          :tooltip="false"
          @update:value="handleVolumeChange"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { NSelect, NSlider, useMessage } from 'naive-ui'
import { usePlayer } from '../composables/usePlayer'
import { ApiError, getFileURL, requireData } from '../api/client'
import { exportApi } from '../api/export'
import { useLogStore } from '../stores/log'
import { useSettingsStore } from '../stores/settings'
import {
  loadPlayerVolume,
  savePlayerVolume,
} from '../utils/playerPreferences'
import { buildPlayerLoadId } from '../utils/playerLoadId'
import { PLAYBACK_RATES } from '../utils/jianpuPlayback'

const settings = useSettingsStore()

const props = defineProps<{
  /** MusicXML file ID (used to generate MIDI on demand) */
  musicxmlFileId?: string
  /** Jianpu text (alternative to MusicXML for MIDI generation) */
  jianpuText?: string
  /** Direct MIDI file ID (skip generation) */
  midiFileId?: string
  /** Recognition batch identity; a new batch resets playback to 1x. */
  sessionKey?: string | null
}>()

const emit = defineEmits<{
  'update:currentNoteIndex': [index: number]
  'update:playbackGroupIndex': [index: number]
  'update:playbackPosition': [position: { tick: number; onsetTick: number; ppq: number }]
}>()

const player = usePlayer()
const message = useMessage()
const logStore = useLogStore()
const progressRef = ref<HTMLElement>()
const visible = computed(() => !!props.musicxmlFileId || !!props.jianpuText?.trim() || !!props.midiFileId)
const rateOptions = PLAYBACK_RATES.map((rate) => ({ label: `${rate}x`, value: rate }))

const volumeRatio = computed(() => {
  const db = player.volume.value
  if (db <= -50) return 0
  return Math.pow(10, db / 20)
})

const initialVolumeRatio = loadPlayerVolume()
const isMuted = ref(initialVolumeRatio === 0)
let lastVolumeRatio = initialVolumeRatio > 0 ? initialVolumeRatio : 0.8

// Load MIDI when source changes
let currentLoadId = ''
let loadGeneration = 0

async function loadFromProps(): Promise<void> {
  const loadId = buildPlayerLoadId(props)
  if (loadId === currentLoadId) return
  currentLoadId = loadId
  const gen = ++loadGeneration

  if (props.midiFileId) {
    try {
      await loadMidiForGeneration(getFileURL(props.midiFileId), gen)
    } catch (error: unknown) {
      reportMidiError(error, gen)
    }
    return
  }

  // Need to generate MIDI from backend
  if (props.jianpuText?.trim()) {
    try {
      const result = await requireData(exportApi.exportMidiText({
        jianpu_text: props.jianpuText,
        filename: 'player.mid',
        title: '简谱',
      }))
      if (gen !== loadGeneration) return
      await loadMidiForGeneration(getFileURL(result.file_id), gen)
    } catch (error: unknown) {
      reportMidiError(error, gen)
    }
    return
  }

  if (props.musicxmlFileId) {
    try {
      const result = await requireData(exportApi.exportMidi({
        musicxml_file_id: props.musicxmlFileId,
        filename: 'player.mid',
        target_key: settings.targetKey,
      }))
      if (gen !== loadGeneration) return
      await loadMidiForGeneration(getFileURL(result.file_id), gen)
    } catch (error: unknown) {
      reportMidiError(error, gen)
    }
  }
}

async function loadMidiForGeneration(url: string, generation: number): Promise<void> {
  await player.loadMidi(url)
  if (generation !== loadGeneration) return
  if (player.error.value) throw new Error(player.error.value)
}

function reportMidiError(error: unknown, generation: number): void {
  if (generation !== loadGeneration) return
  const detail = error instanceof Error ? error.message : String(error)
  if (error instanceof ApiError && error.code === 'jianpu_syntax') {
    player.unload()
    const msg = '存在语法错误，无法生成 MIDI，请先修复'
    logStore.addError(msg)
    message.error(msg)
    return
  }
  player.unload()
  const msg = `MIDI 加载失败：${detail}`
  logStore.addError(msg)
  message.error(msg)
}

async function togglePlay(): Promise<void> {
  if (player.isPlaying.value) {
    player.pause()
  } else {
    await player.play()
  }
}

function stopPlayback(): void {
  player.stop()
}

function handleRateChange(value: number): void {
  player.setRate(value)
}

function handleVolumeChange(value: number): void {
  isMuted.value = value === 0
  if (value > 0) lastVolumeRatio = value
  player.setVolumeRatio(value)
  savePlayerVolume(value)
}

function toggleMute(): void {
  if (isMuted.value) {
    isMuted.value = false
    player.setVolumeRatio(lastVolumeRatio)
    savePlayerVolume(lastVolumeRatio)
  } else {
    isMuted.value = true
    lastVolumeRatio = volumeRatio.value
    player.setVolumeDb(-Infinity)
  }
}

// Progress bar dragging
let dragging = false

function onProgressDown(event: MouseEvent): void {
  if (!player.isReady.value) return
  dragging = true
  updateProgressFromMouse(event)
  document.addEventListener('mousemove', onProgressMove)
  document.addEventListener('mouseup', onProgressUp)
  document.body.style.userSelect = 'none'
}

function onProgressMove(event: MouseEvent): void {
  if (dragging) updateProgressFromMouse(event)
}

function onProgressUp(): void {
  dragging = false
  document.removeEventListener('mousemove', onProgressMove)
  document.removeEventListener('mouseup', onProgressUp)
  document.body.style.userSelect = ''
}

function updateProgressFromMouse(event: MouseEvent): void {
  const el = progressRef.value
  if (!el) return
  const rect = el.getBoundingClientRect()
  const ratio = Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width))
  player.seekTo(ratio)
}

// Stop player when changing songs
onMounted(() => {
  player.setVolumeRatio(initialVolumeRatio)
  void loadFromProps()
})

onUnmounted(() => {
  if (jianpuDebounce) { clearTimeout(jianpuDebounce); jianpuDebounce = null }
  onProgressUp()
})

// Watch for source changes (debounce jianpuText since user may be typing)
let jianpuDebounce: ReturnType<typeof setTimeout> | null = null

watch(player.playbackPosition, (position) => {
  emit('update:playbackPosition', position)
}, { immediate: true })

watch(player.currentPlaybackGroupIndex, (index) => {
  emit('update:currentNoteIndex', index)
  emit('update:playbackGroupIndex', index)
}, { immediate: true })

watch(() => [props.midiFileId, props.musicxmlFileId], () => {
  player.stop()
  if (jianpuDebounce) { clearTimeout(jianpuDebounce); jianpuDebounce = null }
  currentLoadId = ''
  void loadFromProps()
})

watch(() => props.sessionKey, (value, previous) => {
  if (previous !== undefined && value !== previous) {
    player.stop()
    player.setRate(1)
  }
})

watch(() => props.jianpuText, () => {
  if (jianpuDebounce) clearTimeout(jianpuDebounce)
  jianpuDebounce = setTimeout(() => {
    jianpuDebounce = null
    player.stop()
    currentLoadId = ''
    void loadFromProps()
  }, 600)
})
</script>

<style scoped>
.jianpu-player {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 6px 16px;
  background: var(--bg-elevated, #fff);
  border-top: 1px solid var(--border, #e9ecef);
  height: 48px;
  flex-shrink: 0;
}

.player-left {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}

.player-btn {
  width: 32px;
  height: 32px;
  border: none;
  border-radius: 50%;
  background: transparent;
  color: var(--text-1, #212529);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  transition: background 0.15s, color 0.15s;
}

.player-btn:hover:not(:disabled) {
  background: var(--hover-color, rgba(0,0,0,0.06));
}

.player-btn:disabled {
  opacity: 0.35;
  cursor: default;
}

.player-btn svg {
  width: 20px;
  height: 20px;
}

.play-btn {
  width: 36px;
  height: 36px;
  background: var(--primary-color, #4c6ef5);
  color: #fff;
}

.play-btn:hover:not(:disabled) {
  background: var(--primary-color-hover, #5c7aff);
}

.play-btn svg {
  width: 22px;
  height: 22px;
}

.player-time {
  font-size: 12px;
  color: var(--text-2, #868e96);
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
  min-width: 80px;
}

.player-center {
  flex: 1;
  display: flex;
  align-items: center;
  min-width: 0;
}

.progress-bar {
  width: 100%;
  height: 24px;
  display: flex;
  align-items: center;
  cursor: pointer;
  padding: 0 4px;
}

.progress-track {
  position: relative;
  width: 100%;
  height: 4px;
  background: var(--border, #e9ecef);
  border-radius: 2px;
}

.progress-fill {
  position: absolute;
  left: 0;
  top: 0;
  height: 100%;
  background: var(--primary-color, #4c6ef5);
  border-radius: 2px;
  transition: width 0.05s linear;
}

.progress-thumb {
  position: absolute;
  top: 50%;
  width: 12px;
  height: 12px;
  background: var(--primary-color, #4c6ef5);
  border-radius: 50%;
  transform: translate(-50%, -50%);
  opacity: 0;
  transition: opacity 0.15s;
}

.progress-bar:hover .progress-thumb {
  opacity: 1;
}

.progress-bar:hover .progress-track {
  height: 6px;
}

.player-right {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
}

.tempo-control {
  display: flex;
  align-items: center;
  gap: 4px;
}

.tempo-icon {
  width: 16px;
  height: 16px;
  color: var(--text-2, #868e96);
  flex-shrink: 0;
}

.player-btn-sm {
  width: 22px;
  height: 22px;
  border: none;
  border-radius: 4px;
  background: transparent;
  color: var(--text-2, #868e96);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  transition: background 0.15s, color 0.15s;
}

.player-btn-sm:hover {
  background: var(--hover-color, rgba(0,0,0,0.06));
  color: var(--text-1, #212529);
}

.player-btn-sm svg {
  width: 14px;
  height: 14px;
}

.volume-control {
  display: flex;
  align-items: center;
  gap: 4px;
}

/* Dark theme adjustments */
.theme-dark .player-btn:hover:not(:disabled) {
  background: rgba(255,255,255,0.08);
}

.theme-dark .player-btn-sm:hover {
  background: rgba(255,255,255,0.08);
}
</style>
