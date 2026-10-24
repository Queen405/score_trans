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
  if (shape.startsWith('KEY_SHARP_')) return '♯'.repeat(Number(shape.slice('KEY_SHARP_'.length)) || 1)
  if (shape.startsWith('KEY_FLAT_')) return '♭'.repeat(Number(shape.slice('KEY_FLAT_'.length)) || 1)
  if (shape === 'KEY_CANCEL') return '♮'
  const timeLabels: Record<string, string> = {
    TIME_FOUR_FOUR: '4/4', TIME_TWO_TWO: '2/2', TIME_TWO_FOUR: '2/4',
    TIME_THREE_FOUR: '3/4', TIME_FIVE_FOUR: '5/4', TIME_SIX_FOUR: '6/4',
    TIME_THREE_EIGHT: '3/8', TIME_SIX_EIGHT: '6/8', TIME_NINE_EIGHT: '9/8',
    TIME_TWELVE_EIGHT: '12/8',
  }
  if (timeLabels[shape]) return timeLabels[shape]
  if (shape === 'COMMON_TIME') return 'C'
  if (shape === 'CUT_TIME') return '¢'
  if (shape.startsWith('DYNAMICS_')) return shape.slice('DYNAMICS_'.length).toLowerCase()
  if (shape === 'SF' || shape === 'SFZ') return shape.toLowerCase()
  if (shape === 'TUPLET_THREE') return '3'
  if (shape === 'TUPLET_SIX') return '6'
  if (/^DIGIT_[0-5]$/.test(shape)) return shape.slice(-1)
  if (shape.startsWith('PLUCK_')) return shape.slice(-1).toLowerCase()
  if (shape === 'BOW_UP') return '∨'
  if (shape === 'BOW_DOWN') return '⌄'
  if (shape === 'ARPEGGIATO') return 'arp.'
  if (shape === 'BREATH_MARK') return ','
  if (shape === 'CAESURA') return '//'
  if (shape === 'CRESCENDO') return '<'
  if (shape === 'DIMINUENDO') return '>'
  if (shape === 'PEDAL_MARK') return 'Ped.'
  if (shape === 'PEDAL_UP_MARK') return '✱'
  if (shape === 'STACCATO' || shape === 'STACCATO_BELOW') return '·'
  if (shape === 'STACCATISSIMO' || shape === 'STACCATISSIMO_BELOW') return '▾'
  if (shape.includes('MARCATO') || shape.includes('ACCENT')) return '›'
  if (shape.includes('TENUTO')) return '—'
  if (shape === 'FERMATA_BELOW') return '𝄑'
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
