<template>
  <div class="sv-panel">
    <section class="sv-section">
      <div class="sv-section-heading">
        <h3>{{ t('settings.conversion.jianpuRules') }}</h3>
      </div>

      <div class="sv-form-stack">
        <settings-form-row :label="t('settings.conversion.jianpuKey')">
          <div class="sv-key-pickers">
            <n-checkbox
              v-model:checked="autoKey"
              :title="t('settings.conversion.autoKeyHint')"
            >
              {{ t('settings.conversion.autoKey') }}
            </n-checkbox>
            <n-select
              v-model:value="accidental"
              :options="accidentalOptions"
              :disabled="autoKey"
              size="small"
              class="key-accidental"
            />
            <n-select
              v-model:value="baseKey"
              :options="baseKeyOptions"
              :disabled="autoKey"
              size="small"
              class="key-base"
            />
          </div>
        </settings-form-row>

        <settings-form-row :label="t('settings.conversion.accidentalMode')">
          <n-radio-group
            v-model:value="settings.draft.accidentalMode"
            class="sv-theme-options"
            size="small"
          >
            <n-radio-button
              v-for="option in accidentalModeOptions"
              :key="option.value"
              :value="option.value"
            >
              {{ option.label }}
            </n-radio-button>
          </n-radio-group>
        </settings-form-row>

        <settings-form-row :label="t('settings.conversion.measureNumber')">
          <n-radio-group
            v-model:value="settings.draft.measureNumberMode"
            class="sv-theme-options"
            size="small"
          >
            <n-radio-button
              v-for="option in measureNumberModeOptions"
              :key="option.value"
              :value="option.value"
            >
              {{ option.label }}
            </n-radio-button>
          </n-radio-group>
        </settings-form-row>

        <settings-form-row
          :label="t('settings.conversion.enableOmrOcr')"
        >
          <n-switch
            v-model:value="settings.draft.enableOmrOcr"
            size="small"
          />
        </settings-form-row>

        <settings-form-row
          :label="t('settings.conversion.polyphony')"
        >
          <n-switch
            :value="settings.draft.polyphonyMode !== 'flatten'"
            size="small"
            @update:value="(value: boolean) => (settings.draft.polyphonyMode = value ? 'auto' : 'flatten')"
          />
        </settings-form-row>

        <settings-form-row
          :label="t('settings.conversion.syntaxHighlight')"
        >
          <n-switch
            v-model:value="settings.draft.jianpuSyntaxHighlight"
            size="small"
          />
        </settings-form-row>

        <settings-form-row
          :label="t('settings.conversion.measureDurationCheck')"
        >
          <n-switch
            v-model:value="settings.draft.jianpuMeasureDurationCheck"
            size="small"
          />
        </settings-form-row>

        <settings-form-row
          :label="t('settings.conversion.autoTranspose')"
        >
          <n-switch
            v-model:value="settings.draft.jianpuAutoTranspose"
            size="small"
          />
        </settings-form-row>
      </div>
    </section>

    <div class="sv-section-divider" />

    <section class="sv-section">
      <div class="sv-section-heading">
        <h3>{{ t('settings.conversion.export') }}</h3>
      </div>

      <div class="sv-form-stack">
        <settings-form-row
          :label="t('settings.conversion.defaultExport')"
        >
          <n-input
            v-model:value="settings.draft.outputDir"
            :placeholder="t('settings.conversion.defaultExportPlaceholder')"
            size="small"
          >
            <template #suffix>
              <n-button
                size="tiny"
                quaternary
                @click="selectOutputDir"
              >
                {{ t('common.action.browse') }}
              </n-button>
            </template>
          </n-input>
        </settings-form-row>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { NButton, NCheckbox, NInput, NRadioButton, NRadioGroup, NSelect, NSwitch } from 'naive-ui'
import { computed, ref, watch } from 'vue'
import { useSettingsStore } from '../../stores/settings'
import { t } from '../../i18n'
import type { AccidentalMode, MeasureNumberMode, TargetKey } from '../../models/types'
import SettingsFormRow from './SettingsFormRow.vue'

const settings = useSettingsStore()

type KeyAccidental = 'sharp' | 'flat' | 'natural'
type KeyBase = 'C' | 'D' | 'E' | 'F' | 'G' | 'A' | 'B'

const allBases: KeyBase[] = ['C', 'D', 'E', 'F', 'G', 'A', 'B']

const lastSpecificKey = ref<TargetKey>('C')

watch(
  () => settings.draft.targetKey,
  (key) => {
    if (key !== 'auto') lastSpecificKey.value = key
  },
  { immediate: true },
)

const autoKey = computed<boolean>({
  get: () => settings.draft.targetKey === 'auto',
  set: (value: boolean) => {
    settings.draft.targetKey = value ? 'auto' : lastSpecificKey.value
  },
})

const baseLabels: Record<KeyBase, string> = {
  C: 'C',
  D: 'D',
  E: 'E',
  F: 'F',
  G: 'G',
  A: 'A',
  B: 'B',
}

function splitTargetKey(key: TargetKey): { accidental: KeyAccidental; base: KeyBase } {
  if (key === 'auto') return { accidental: 'natural', base: 'C' }
  if (key.endsWith('#')) {
    return { accidental: 'sharp', base: key.slice(0, 1) as KeyBase }
  }
  if (key.endsWith('b')) {
    return { accidental: 'flat', base: key.slice(0, 1) as KeyBase }
  }
  return { accidental: 'natural', base: key as KeyBase }
}

function allowedBases(accidental: KeyAccidental): KeyBase[] {
  if (accidental === 'sharp') {
    return allBases.filter((b) => b === 'C' || b === 'F')
  }
  if (accidental === 'flat') {
    return allBases.filter((b) => b !== 'F')
  }
  return allBases
}

function buildTargetKey(accidental: KeyAccidental, base: KeyBase): TargetKey {
  if (accidental === 'sharp') return `${base}#` as TargetKey
  if (accidental === 'flat') return `${base}b` as TargetKey
  return base as TargetKey
}

const accidental = computed<KeyAccidental>({
  get: () => splitTargetKey(settings.draft.targetKey).accidental,
  set: (value) => {
    const currentBase = splitTargetKey(settings.draft.targetKey).base
    const bases = allowedBases(value)
    const base = bases.includes(currentBase) ? currentBase : bases[0]
    settings.draft.targetKey = buildTargetKey(value, base)
  },
})

const baseKey = computed<KeyBase>({
  get: () => splitTargetKey(settings.draft.targetKey).base,
  set: (value) => {
    settings.draft.targetKey = buildTargetKey(accidental.value, value)
  },
})

const accidentalOptions = computed(() => [
  { label: t('settings.conversion.optionNone'), value: 'natural' as KeyAccidental },
  { label: t('settings.conversion.optionSharp'), value: 'sharp' as KeyAccidental },
  { label: t('settings.conversion.optionFlat'), value: 'flat' as KeyAccidental },
])

const baseKeyOptions = computed(() =>
  allowedBases(accidental.value).map((b) => ({ label: baseLabels[b], value: b })),
)

const accidentalModeOptions = computed<{ label: string; value: AccidentalMode }[]>(() => [
  { label: t('settings.conversion.optionAuto'), value: 'auto' },
  { label: t('settings.conversion.optionSharp'), value: 'sharp' },
  { label: t('settings.conversion.optionFlat'), value: 'flat' },
])

const measureNumberModeOptions = computed<{ label: string; value: MeasureNumberMode }[]>(() => [
  { label: t('settings.conversion.measureAll'), value: 'all' },
  { label: t('settings.conversion.measureRowStart'), value: 'row_start' },
  { label: t('settings.conversion.measureHide'), value: 'none' },
])

async function selectOutputDir(): Promise<void> {
  const result = await desktopApi().selectDirectory()
  if (result) settings.draft.outputDir = result
}

function desktopApi() {
  return window.api
}
</script>

<style scoped>
.sv-key-pickers {
  display: flex;
  align-items: center;
  gap: 12px;
  max-width: 560px;
}

.sv-key-pickers .key-accidental {
  width: 96px;
  flex-shrink: 0;
}

.sv-key-pickers .key-base {
  flex: 1;
}
</style>
