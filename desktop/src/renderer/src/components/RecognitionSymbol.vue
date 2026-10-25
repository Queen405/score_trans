<template>
  <svg
    v-if="usesNotehead && fit"
    class="recognition-symbol recognition-symbol--fit"
    viewBox="0 0 32 24"
    aria-hidden="true"
  >
    <NoteheadSymbol
      :shape="shape"
      :background="background"
      fit
    />
  </svg>
  <svg
    v-else-if="smuflCharacter || !usesNotehead"
    class="recognition-symbol"
    :class="{ 'recognition-symbol--fit': fit }"
    viewBox="0 0 48 36"
    aria-hidden="true"
  >
    <text x="24" y="27" text-anchor="middle">{{ smuflCharacter || symbol }}</text>
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

const props = withDefaults(defineProps<{
  shape: string
  background?: boolean
  /** Fill the supplied SVG bounds when used as an image replacement. */
  fit?: boolean
}>(), {
  background: true,
  fit: false,
})

const usesNotehead = computed(() => /NOTEHEAD|WHOLE_NOTE|REST/.test(props.shape))
// Keep the candidate preview in the same SMuFL/Bravura glyph system as the
// Audiveris overlay. The previous fallback drew noteheads with hand-built
// ellipses and musical text with unrelated Unicode glyphs, which made a
// selected candidate visibly different from the recognized score image.
const SMUFL_CODEPOINTS: Record<string, number> = {
  ACCENT: 0xE4A0,
  AUGMENTATION_DOT: 0xE044,
  BOW_DOWN: 0xE610,
  BOW_UP: 0xE612,
  BREVE_REST: 0xE4E2,
  C_CLEF: 0xE05C,
  COMMON_TIME: 0xE08A,
  CUT_TIME: 0xE08B,
  DOUBLE_FLAT: 0xE264,
  DOUBLE_SHARP: 0xE263,
  EIGHTH_REST: 0xE4E6,
  FERMATA: 0xE4C0,
  FERMATA_BELOW: 0xE4C1,
  FLAT: 0xE260,
  F_CLEF: 0xE062,
  G_CLEF: 0xE050,
  HALF_REST: 0xE4E4,
  KEY_CANCEL: 0xE261,
  LONG_REST: 0xE4E1,
  MARCATO: 0xE4AC,
  MARCATO_BELOW: 0xE4AD,
  NATURAL: 0xE261,
  NOTEHEAD_BLACK: 0xE0A4,
  NOTEHEAD_BLACK_SMALL: 0xE0A4,
  NOTEHEAD_CIRCLE_X: 0xE0B3,
  NOTEHEAD_CIRCLE_X_VOID: 0xE0B2,
  NOTEHEAD_CROSS: 0xE0A9,
  NOTEHEAD_CROSS_VOID: 0xE0A8,
  NOTEHEAD_DIAMOND_FILLED: 0xE0DB,
  NOTEHEAD_DIAMOND_VOID: 0xE0D9,
  NOTEHEAD_TRIANGLE_DOWN_FILLED: 0xE0C7,
  NOTEHEAD_TRIANGLE_DOWN_VOID: 0xE0C5,
  NOTEHEAD_VOID: 0xE0A3,
  NOTEHEAD_VOID_SMALL: 0xE0A3,
  WHOLE_NOTE: 0xE0A2,
  WHOLE_NOTE_SMALL: 0xE0A2,
  ONE_16TH_REST: 0xE4E7,
  ONE_32ND_REST: 0xE4E8,
  ONE_64TH_REST: 0xE4E9,
  ONE_128TH_REST: 0xE4EA,
  PERCUSSION_CLEF: 0xE069,
  QUARTER_REST: 0xE4E5,
  SIXTEENTH_REST: 0xE4E7,
  THIRTY_SECOND_REST: 0xE4E8,
  SIXTY_FOURTH_REST: 0xE4E9,
  SHARP: 0xE262,
  STACCATISSIMO: 0xE4A6,
  STACCATISSIMO_BELOW: 0xE4A7,
  STACCATO: 0xE4A2,
  TENUTO: 0xE4A4,
  WHOLE_REST: 0xE4E3,
}

const smuflCharacter = computed(() => {
  const codepoint = SMUFL_CODEPOINTS[props.shape]
  return codepoint ? String.fromCodePoint(codepoint) : ''
})

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
@font-face {
  font-family: 'ScoreTransBravura';
  src: url('../assets/Bravura.otf') format('opentype');
  font-style: normal;
  font-weight: normal;
  font-display: block;
}

.recognition-symbol {
  width: 42px;
  height: 32px;
  color: currentColor;
}

text {
  fill: currentColor;
  font-family: 'ScoreTransBravura', 'Bravura', 'Segoe UI Symbol', 'Noto Music', serif;
  font-size: 27px;
  font-weight: normal;
}

.recognition-symbol--fit text {
  font-size: 38px;
}
</style>
