<template>
  <section
    class="marker-inspector"
    role="dialog"
    :aria-label="title"
  >
    <header class="marker-inspector__head">
      <span class="marker-inspector__chip">
        <RecognitionSymbol
          :shape="displayShape"
          :background="false"
          fit
          center
        />
      </span>

      <span class="marker-inspector__identity">
        <span class="marker-inspector__title">{{ title }}</span>
        <span class="marker-inspector__subtitle">{{ scoreLabel }}</span>
      </span>

      <span
        v-if="hasCurrentScore"
        class="marker-inspector__score"
      >
        {{ currentPercent }}
      </span>

      <button
        class="marker-inspector__close"
        type="button"
        :aria-label="t('convert.marker.closeInspector')"
        :title="t('convert.marker.closeInspector')"
        @click="emit('close')"
      >
        <svg
          viewBox="0 0 16 16"
          width="12"
          height="12"
          aria-hidden="true"
        >
          <path
            d="M3.5 3.5l9 9M12.5 3.5l-9 9"
            fill="none"
            stroke="currentColor"
            stroke-width="1.6"
            stroke-linecap="round"
          />
        </svg>
      </button>
    </header>

    <div class="marker-inspector__body">
      <div
        v-if="candidates.length"
        class="marker-inspector__list"
      >
        <button
          v-for="(candidate, index) in candidates"
          :key="`${candidate.score_kind}:${candidate.shape}`"
          class="candidate-row"
          :class="{ 'is-selected': candidate.shape === selectedShape }"
          type="button"
          :disabled="disabled"
          :title="`${labelFor(candidate.shape)} · ${formatScorePercent(candidate.score)}`"
          :aria-label="`${index + 1}. ${labelFor(candidate.shape)}, ${formatScorePercent(candidate.score)}`"
          :aria-pressed="candidate.shape === selectedShape"
          @click="emit('select', candidate.shape)"
        >
          <span class="candidate-row__rank">{{ index + 1 }}</span>
          <span class="candidate-row__glyph">
            <RecognitionSymbol
              :shape="candidate.shape"
              fit
              center
            />
          </span>
          <span class="candidate-row__score">{{ formatScorePercent(candidate.score) }}</span>
          <svg
            v-if="candidate.shape === selectedShape"
            class="candidate-row__check"
            viewBox="0 0 16 16"
            width="14"
            height="14"
            aria-hidden="true"
          >
            <path
              d="m3.5 8.2 2.8 2.8 6.2-6"
              fill="none"
              stroke="currentColor"
              stroke-width="1.8"
              stroke-linecap="round"
              stroke-linejoin="round"
            />
          </svg>
        </button>
      </div>

      <p
        v-else
        class="marker-inspector__empty"
      >
        {{ t('convert.marker.noTopFive') }}
      </p>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import RecognitionSymbol from './RecognitionSymbol.vue'
import { t } from '../i18n'
import {
  familyFromTag,
  formatScorePercent,
  shapeClefOctave,
  shapeFamily,
  shapeVariantKey,
  shapeVariantText,
} from '../utils/shapeDescriptor'

export type MarkerCandidate = { shape: string; score: number; score_kind: string }

const props = withDefaults(defineProps<{
  mode?: 'entity' | 'glyph'
  tag?: string | null
  shape?: string
  originalShape?: string
  currentScore?: number
  candidates?: MarkerCandidate[]
  selectedShape?: string
  disabled?: boolean
}>(), {
  mode: 'entity',
  tag: null,
  shape: '',
  originalShape: '',
  currentScore: 0,
  candidates: () => [],
  selectedShape: '',
  disabled: false,
})

const emit = defineEmits<{
  select: [shape: string]
  close: []
}>()

const displayShape = computed(() => props.selectedShape || props.shape || 'UNKNOWN')

const title = computed(() => {
  if (props.mode === 'glyph') return t('convert.marker.suspiciousGlyph')
  const family = familyFromTag(props.tag, props.shape)
  return t(`convert.marker.family.${family}`)
})

const hasCurrentScore = computed(() => {
  const value = Number(props.currentScore)
  if (!Number.isFinite(value)) return false
  // 漏识别字形在未选择候选前没有「当前分数」，避免显示成 0%
  return props.mode === 'entity' || Boolean(props.selectedShape)
})

const currentPercent = computed(() => (
  hasCurrentScore.value ? formatScorePercent(props.currentScore) : '—'
))

const scoreLabel = computed(() => (
  hasCurrentScore.value
    ? t('convert.marker.currentScore')
    : t('convert.marker.notRecognized')
))

function variantText(shape: string | null | undefined): string {
  const value = (shape ?? '').trim()
  if (!value || value.toUpperCase() === 'UNKNOWN') return ''
  const key = shapeVariantKey(value)
  const base = key ? t(`convert.marker.variant.${key}`) : shapeVariantText(value)
  if (!base) return ''
  const octave = shapeClefOctave(value)
  return octave ? `${base}（${t(`convert.marker.variant.${octave}`)}）` : base
}

function labelFor(shape: string): string {
  const variant = variantText(shape)
  if (variant) return variant
  // 没有专门变体文案时回退到中文族名，绝不显示英文 shape 名
  const base = t(`convert.marker.family.${shapeFamily(shape)}`)
  if (/_ABOVE$/i.test(shape)) return `${base} · ${t('convert.marker.variant.above')}`
  if (/_BELOW$/i.test(shape)) return `${base} · ${t('convert.marker.variant.below')}`
  return base
}
</script>

<style scoped>
.marker-inspector {
  width: 100%;
  max-height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid color-mix(in srgb, var(--accent) 10%, var(--border));
  border-radius: 10px;
  background: color-mix(in srgb, var(--accent) 2%, var(--bg-elevated));
  color: var(--text-primary);
  box-shadow: 0 10px 30px rgba(23, 27, 36, 0.14), 0 2px 8px rgba(23, 27, 36, 0.08);
  pointer-events: auto;
}

.marker-inspector__head {
  display: grid;
  grid-template-columns: 32px minmax(0, 1fr) auto 24px;
  align-items: center;
  gap: 8px;
  padding: 10px 10px 9px 12px;
  border-bottom: 1px solid color-mix(in srgb, var(--accent) 8%, var(--border-light));
  background: color-mix(in srgb, var(--accent) 4%, var(--bg-elevated));
}

.marker-inspector__chip {
  width: 32px;
  height: 32px;
  display: grid;
  place-items: center;
  color: var(--text-primary);
}

.marker-inspector__chip :deep(svg) {
  width: 30px;
  height: 26px;
  overflow: visible;
}

.marker-inspector__identity {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.marker-inspector__title,
.marker-inspector__subtitle {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.marker-inspector__title {
  font-size: 12px;
  font-weight: 600;
  line-height: 1.35;
}

.marker-inspector__subtitle {
  color: var(--text-tertiary);
  font-size: 10.5px;
  line-height: 1.35;
}

.marker-inspector__score {
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.marker-inspector__close {
  width: 24px;
  height: 24px;
  display: grid;
  place-items: center;
  padding: 0;
  border: 0;
  border-radius: 5px;
  background: transparent;
  color: var(--text-tertiary);
  cursor: pointer;
  transition: background 120ms ease, color 120ms ease;
}

.marker-inspector__close:hover {
  background: color-mix(in srgb, var(--text-primary) 7%, transparent);
  color: var(--text-primary);
}

.marker-inspector__close:focus-visible,
.candidate-row:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: -2px;
}

.marker-inspector__body {
  min-height: 0;
  overflow-y: auto;
  padding: 7px;
  background: color-mix(in srgb, var(--accent) 2%, var(--bg-surface));
  scrollbar-width: thin;
  scrollbar-color: color-mix(in srgb, var(--text-primary) 18%, transparent) transparent;
}

.marker-inspector__list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.candidate-row {
  width: 100%;
  min-height: 40px;
  display: grid;
  grid-template-columns: 18px minmax(32px, 1fr) auto 14px;
  align-items: center;
  gap: 6px;
  padding: 4px 8px;
  border: 1px solid color-mix(in srgb, var(--border) 75%, transparent);
  border-radius: 6px;
  background: color-mix(in srgb, var(--accent) 3%, var(--bg-elevated));
  color: var(--text-primary);
  text-align: left;
  cursor: pointer;
  transition: background 120ms ease;
}

.candidate-row:hover:not(:disabled) {
  background: color-mix(in srgb, var(--text-primary) 5%, transparent);
}

.candidate-row:active:not(:disabled) {
  background: color-mix(in srgb, var(--accent) 12%, transparent);
}

.candidate-row:disabled {
  cursor: default;
  opacity: 0.55;
}

.candidate-row.is-selected,
.candidate-row.is-selected:hover:not(:disabled) {
  border-color: color-mix(in srgb, var(--accent) 22%, var(--border));
  background: var(--accent-light);
}

.candidate-row__rank {
  color: var(--text-tertiary);
  font-size: 10px;
  font-variant-numeric: tabular-nums;
  text-align: center;
}

.candidate-row__glyph {
  width: 100%;
  height: 24px;
  display: grid;
  place-items: center;
}

.candidate-row__glyph :deep(svg) {
  width: 28px;
  max-width: 100%;
  height: 22px;
  overflow: visible;
}

.candidate-row__glyph :deep(text) {
  font-size: 22px;
}

.candidate-row__score {
  min-width: 40px;
  color: var(--text-secondary);
  font-size: 11px;
  font-weight: 500;
  font-variant-numeric: tabular-nums;
  text-align: right;
}

.candidate-row.is-selected .candidate-row__score {
  color: var(--accent);
  font-weight: 600;
}

.candidate-row__check {
  color: var(--accent);
}

.marker-inspector__empty {
  margin: 0;
  padding: 18px 12px;
  color: var(--text-tertiary);
  font-size: 11px;
  line-height: 1.6;
  text-align: center;
}

:global(.theme-dark) .marker-inspector {
  box-shadow: 0 10px 32px rgba(0, 0, 0, 0.4);
}

@media (prefers-reduced-motion: reduce) {
  .marker-inspector__close,
  .candidate-row {
    transition: none;
  }
}
</style>
