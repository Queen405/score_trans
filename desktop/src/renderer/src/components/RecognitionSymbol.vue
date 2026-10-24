<template>
  <svg
    v-if="!usesNotehead"
    class="recognition-symbol"
    viewBox="0 0 48 36"
    aria-hidden="true"
  >
    <text x="24" y="27" text-anchor="middle">{{ symbol }}</text>
  </svg>
  <NoteheadSymbol
    v-else
    :shape="shape"
    :background="background"
  />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import NoteheadSymbol from './NoteheadSymbol.vue'

const props = withDefaults(defineProps<{ shape: string; background?: boolean }>(), {
  background: true,
})

const usesNotehead = computed(() => /NOTEHEAD|WHOLE_NOTE|REST/.test(props.shape))
const symbol = computed(() => {
  const shape = props.shape
  const accidentals: Record<string, string> = {
    SHARP: '♯', FLAT: '♭', NATURAL: '♮', DOUBLE_SHARP: '𝄪', DOUBLE_FLAT: '𝄫',
  }
  if (accidentals[shape]) return accidentals[shape]
  if (shape.includes('G_CLEF')) return '𝄞'
  if (shape.includes('F_CLEF')) return '𝄢'
  if (shape.includes('C_CLEF')) return '𝄡'
  if (shape.includes('PERCUSSION_CLEF')) return '𝄥'
  if (shape.startsWith('KEY_SHARP_')) return '♯'.repeat(Number(shape.slice(-1)) || 1)
  if (shape.startsWith('KEY_FLAT_')) return '♭'.repeat(Number(shape.slice(-1)) || 1)
  if (shape === 'KEY_CANCEL') return '♮'
  const time = shape.match(/^TIME_(\d+)_(\d+)$/)
  if (time) return `${time[1]}/${time[2]}`
  if (shape === 'COMMON_TIME') return 'C'
  if (shape === 'CUT_TIME') return '¢'
  if (shape.startsWith('DYNAMICS_')) return shape.slice('DYNAMICS_'.length).toLowerCase()
  if (shape === 'STACCATO' || shape === 'STACCATO_BELOW') return '·'
  if (shape.includes('MARCATO') || shape.includes('ACCENT')) return '›'
  if (shape.includes('TENUTO')) return '—'
  if (shape.includes('FERMATA')) return '𝄐'
  if (shape.includes('MORDENT') || shape === 'TR') return '𝆔'
  if (shape.includes('TURN')) return '𝆗'
  if (shape.includes('SLUR') || shape.includes('TIE')) return '⌒'
  if (shape.includes('AUGMENTATION_DOT')) return '·'
  return '♪'
})
</script>

<style scoped>
.recognition-symbol {
  width: 42px;
  height: 32px;
  color: currentColor;
}

text {
  fill: currentColor;
  font-family: 'Bravura', 'Segoe UI Symbol', 'Noto Music', serif;
  font-size: 25px;
  font-weight: 600;
}
</style>
