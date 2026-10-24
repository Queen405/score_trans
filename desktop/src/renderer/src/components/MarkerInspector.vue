<template>
  <section
    class="marker-inspector"
    :class="[`marker-inspector--${mode}`]"
    role="dialog"
    :aria-label="title"
  >
    <header class="marker-inspector__head">
      <span class="marker-inspector__chip">
        <RecognitionSymbol
          :shape="displayShape"
          :background="false"
        />
      </span>

      <span class="marker-inspector__identity">
        <span class="marker-inspector__title-line">
          <span class="marker-inspector__title">{{ title }}</span>
          <span
            v-if="variantLabel"
            class="marker-inspector__variant"
          >{{ variantLabel }}</span>
        </span>
        <span class="marker-inspector__subtitle">{{ subtitle }}</span>
      </span>

      <span class="marker-inspector__score">
        <span class="marker-inspector__score-value">{{ currentPercent }}</span>
        <span class="marker-inspector__score-label">{{ scoreLabel }}</span>
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

    <p
      v-if="mode === 'glyph'"
      class="marker-inspector__notice"
    >
      {{ t('convert.marker.suspiciousNotice') }}
    </p>

    <div class="marker-inspector__body">
      <div class="marker-inspector__section">
        <span class="marker-inspector__section-label">{{ t('convert.marker.topCandidates') }}</span>
        <span class="marker-inspector__section-count">{{ candidates.length }}</span>
      </div>

      <div
        v-if="candidates.length"
        class="marker-inspector__list"
      >
        <button
          v-for="(candidate, index) in candidates"
          :key="`${candidate.score_kind}:${candidate.shape}`"
          class="candidate-row"
          :class="{
            'is-selected': candidate.shape === selectedShape,
            'is-current': candidate.shape === originalShape,
            'is-weak': isLowConfidence(candidate.score),
          }"
          type="button"
          :disabled="disabled"
          :title="`${candidate.shape} · ${formatScorePercent(candidate.score)} · ${candidate.score_kind}`"
          :aria-pressed="candidate.shape === selectedShape"
          @click="emit('select', candidate.shape)"
        >
          <span class="candidate-row__rank">{{ index + 1 }}</span>
          <span class="candidate-row__glyph">
            <RecognitionSymbol :shape="candidate.shape" />
          </span>
          <span class="candidate-row__text">
            <span class="candidate-row__label-line">
              <span class="candidate-row__label">{{ labelFor(candidate.shape) }}</span>
              <span
                v-if="candidate.shape === originalShape"
                class="candidate-row__tag"
              >{{ t('convert.marker.currentTag') }}</span>
            </span>
            <span class="candidate-row__meter">
              <i :style="{ width: meterWidth(candidate.score) }" />
            </span>
          </span>
          <span class="candidate-row__score">{{ formatScorePercent(candidate.score) }}</span>
        </button>
      </div>

      <p
        v-else
        class="marker-inspector__empty"
      >
        {{ t('convert.marker.noTopFive') }}
      </p>
    </div>

    <footer class="marker-inspector__foot">
      <svg
        class="marker-inspector__foot-icon"
        viewBox="0 0 16 16"
        width="12"
        height="12"
        aria-hidden="true"
      >
        <circle
          cx="8"
          cy="8"
          r="6.2"
          fill="none"
          stroke="currentColor"
          stroke-width="1.3"
        />
        <path
          d="M8 7.2v4M8 4.9v.9"
          stroke="currentColor"
          stroke-width="1.4"
          stroke-linecap="round"
        />
      </svg>
      <span>{{ footHint }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import RecognitionSymbol from './RecognitionSymbol.vue'
import { t } from '../i18n'
import {
  familyFromTag,
  formatScorePercent,
  isLowConfidence,
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

const subtitle = computed(() => (
  props.mode === 'glyph'
    ? t('convert.marker.glyphSubtitle')
    : t('convert.marker.inspector')
))

const variantLabel = computed(() => variantText(props.shape))

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

const footHint = computed(() => (
  props.mode === 'glyph'
    ? t('convert.marker.glyphApplyHint')
    : t('convert.marker.applySelectionHint')
))

function variantText(shape: string | null | undefined): string {
  const value = (shape ?? '').trim()
  if (!value || value.toUpperCase() === 'UNKNOWN') return ''
  const key = shapeVariantKey(value)
  if (key) return t(`convert.marker.variant.${key}`)
  return shapeVariantText(value)
}

function labelFor(shape: string): string {
  return variantText(shape) || shape
}

function meterWidth(score: number): string {
  const value = Number(score)
  if (!Number.isFinite(value)) return '0%'
  return `${Math.max(0, Math.min(1, value)) * 100}%`
}
</script>

<style scoped>
.marker-inspector {
  width: 100%;
  max-height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid var(--border);
  border-radius: 12px;
  background: var(--bg-elevated);
  color: var(--text-primary);
  box-shadow:
    0 18px 40px -12px rgba(16, 20, 30, 0.28),
    0 4px 12px -4px rgba(16, 20, 30, 0.16),
    0 0 0 1px color-mix(in srgb, var(--accent) 8%, transparent);
  pointer-events: auto;
}

.marker-inspector__head {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 11px 11px 10px 12px;
  border-bottom: 1px solid var(--border-light);
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--accent) 7%, var(--bg-elevated)),
      var(--bg-elevated)
    );
}

.marker-inspector--glyph .marker-inspector__head {
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--warning) 12%, var(--bg-elevated)),
      var(--bg-elevated)
    );
}

.marker-inspector__chip {
  flex: 0 0 auto;
  width: 38px;
  height: 38px;
  display: grid;
  place-items: center;
  border: 1px solid color-mix(in srgb, var(--accent) 20%, var(--border));
  border-radius: 10px;
  background: color-mix(in srgb, var(--accent) 8%, var(--bg-elevated));
  color: var(--accent);
}

.marker-inspector--glyph .marker-inspector__chip {
  border-color: color-mix(in srgb, var(--warning) 30%, var(--border));
  background: color-mix(in srgb, var(--warning) 12%, var(--bg-elevated));
  color: color-mix(in srgb, var(--warning) 88%, var(--text-primary));
}

.marker-inspector__chip :deep(svg) {
  width: 26px;
  height: 20px;
}

.marker-inspector__identity {
  min-width: 0;
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.marker-inspector__title-line {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}

.marker-inspector__title {
  overflow: hidden;
  color: var(--text-primary);
  font-size: 12.5px;
  font-weight: 650;
  letter-spacing: 0.1px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.marker-inspector__variant {
  flex: 0 0 auto;
  padding: 1px 6px;
  border-radius: 5px;
  background: color-mix(in srgb, var(--accent) 10%, transparent);
  color: color-mix(in srgb, var(--accent) 80%, var(--text-primary));
  font-size: 10px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  line-height: 1.5;
}

.marker-inspector--glyph .marker-inspector__variant {
  background: color-mix(in srgb, var(--warning) 16%, transparent);
  color: color-mix(in srgb, var(--warning) 70%, var(--text-primary));
}

.marker-inspector__subtitle {
  overflow: hidden;
  color: var(--text-tertiary);
  font-size: 10.5px;
  line-height: 1.3;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.marker-inspector__score {
  flex: 0 0 auto;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 1px;
  padding-right: 2px;
}

.marker-inspector__score-value {
  color: var(--accent);
  font-size: 16px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  line-height: 1.05;
}

.marker-inspector--glyph .marker-inspector__score-value {
  color: color-mix(in srgb, var(--warning) 80%, var(--text-primary));
}

.marker-inspector__score-label {
  color: var(--text-tertiary);
  font-size: 9px;
  font-weight: 500;
  letter-spacing: 0.2px;
  white-space: nowrap;
}

.marker-inspector__close {
  flex: 0 0 auto;
  width: 24px;
  height: 24px;
  display: grid;
  place-items: center;
  padding: 0;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: var(--text-tertiary);
  cursor: pointer;
  transition: background 0.15s ease, color 0.15s ease;
}

.marker-inspector__close:hover {
  background: color-mix(in srgb, var(--text-primary) 8%, transparent);
  color: var(--text-primary);
}

.marker-inspector__close:focus-visible,
.candidate-row:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}

.marker-inspector__notice {
  margin: 0;
  padding: 7px 12px;
  border-bottom: 1px solid var(--border-light);
  background: color-mix(in srgb, var(--warning) 7%, var(--bg-elevated));
  color: color-mix(in srgb, var(--warning) 60%, var(--text-secondary));
  font-size: 10.5px;
  line-height: 1.45;
}

.marker-inspector__body {
  min-height: 0;
  flex: 1 1 auto;
  display: flex;
  flex-direction: column;
  gap: 7px;
  overflow-y: auto;
  padding: 10px 10px 11px;
}

.marker-inspector__section {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 2px;
}

.marker-inspector__section-label {
  color: var(--text-tertiary);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.3px;
  text-transform: uppercase;
}

.marker-inspector__section-count {
  min-width: 16px;
  padding: 0 5px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--text-primary) 7%, transparent);
  color: var(--text-secondary);
  font-size: 9.5px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  line-height: 15px;
  text-align: center;
}

.marker-inspector__list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.candidate-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 7px 6px 6px;
  border: 1px solid transparent;
  border-radius: 8px;
  background: color-mix(in srgb, var(--text-primary) 3%, transparent);
  color: var(--text-secondary);
  text-align: left;
  cursor: pointer;
  transition:
    background 0.14s ease,
    border-color 0.14s ease,
    box-shadow 0.14s ease;
}

.candidate-row:hover:not(:disabled) {
  border-color: color-mix(in srgb, var(--accent) 35%, var(--border));
  background: color-mix(in srgb, var(--accent) 6%, var(--bg-elevated));
}

.candidate-row:disabled {
  cursor: default;
  opacity: 0.6;
}

.candidate-row.is-selected {
  border-color: color-mix(in srgb, var(--accent) 45%, var(--border));
  background: color-mix(in srgb, var(--accent) 9%, var(--bg-elevated));
  box-shadow: inset 2px 0 0 var(--accent);
}

.candidate-row__rank {
  flex: 0 0 auto;
  width: 17px;
  height: 17px;
  display: grid;
  place-items: center;
  border-radius: 5px;
  background: color-mix(in srgb, var(--text-primary) 6%, transparent);
  color: var(--text-tertiary);
  font-size: 9.5px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  transition: background 0.14s ease, color 0.14s ease;
}

.candidate-row.is-selected .candidate-row__rank {
  background: var(--accent);
  color: #fff;
}

.candidate-row__glyph {
  flex: 0 0 auto;
  width: 26px;
  height: 22px;
  display: grid;
  place-items: center;
  color: var(--text-primary);
}

.candidate-row__glyph :deep(svg) {
  width: 26px;
  height: 20px;
}

.candidate-row__text {
  min-width: 0;
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.candidate-row__label-line {
  display: flex;
  align-items: center;
  gap: 5px;
  min-width: 0;
}

.candidate-row__label {
  overflow: hidden;
  color: var(--text-primary);
  font-size: 11.5px;
  font-weight: 600;
  line-height: 1.25;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.candidate-row.is-weak .candidate-row__label {
  color: var(--text-secondary);
  font-weight: 500;
}

.candidate-row__tag {
  flex: 0 0 auto;
  padding: 0 4px;
  border: 1px solid color-mix(in srgb, var(--accent) 40%, var(--border));
  border-radius: 4px;
  color: color-mix(in srgb, var(--accent) 80%, var(--text-primary));
  font-size: 8.5px;
  font-weight: 600;
  line-height: 13px;
}

.candidate-row__meter {
  position: relative;
  display: block;
  height: 3px;
  overflow: hidden;
  border-radius: 999px;
  background: color-mix(in srgb, var(--text-primary) 9%, transparent);
}

.candidate-row__meter i {
  display: block;
  height: 100%;
  border-radius: 999px;
  background: var(--accent);
  opacity: 0.85;
  transition: width 0.22s ease;
}

.candidate-row.is-weak .candidate-row__meter i {
  background: var(--text-tertiary);
  opacity: 0.7;
}

.candidate-row__score {
  flex: 0 0 auto;
  min-width: 34px;
  color: var(--text-secondary);
  font-size: 11px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  text-align: right;
}

.candidate-row.is-selected .candidate-row__score {
  color: var(--accent);
  font-weight: 700;
}

.candidate-row.is-weak .candidate-row__score {
  color: var(--text-tertiary);
  font-weight: 500;
}

.marker-inspector__empty {
  margin: 0;
  padding: 14px 10px;
  border: 1px dashed var(--border);
  border-radius: 8px;
  color: var(--text-tertiary);
  font-size: 10.5px;
  line-height: 1.55;
  text-align: center;
}

.marker-inspector__foot {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  padding: 8px 12px 9px;
  border-top: 1px solid var(--border-light);
  background: color-mix(in srgb, var(--text-primary) 2.5%, var(--bg-elevated));
  color: var(--text-tertiary);
  font-size: 10px;
  line-height: 1.45;
}

.marker-inspector__foot-icon {
  flex: 0 0 auto;
  margin-top: 1px;
  opacity: 0.75;
}
</style>
