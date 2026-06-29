<template>
  <div class="sv-panel">
    <section class="sv-section">
      <div class="sv-section-heading">
        <div>
          <h3>简谱规则</h3>
          <p>设置默认的调号、变音记法与小节编号方式。</p>
        </div>
      </div>

      <div class="sv-form-stack">
        <settings-form-row label="简谱调">
          <div class="sv-key-pickers">
            <n-select
              v-model:value="accidental"
              :options="accidentalOptions"
              size="small"
            />
            <n-select
              v-model:value="baseKey"
              :options="baseKeyOptions"
              size="small"
            />
          </div>
        </settings-form-row>

        <settings-form-row label="半音记谱">
          <n-select
            v-model:value="settings.draft.accidentalMode"
            :options="accidentalModeOptions"
            size="small"
          />
        </settings-form-row>

        <settings-form-row label="小节号">
          <n-select
            v-model:value="settings.draft.measureNumberMode"
            :options="measureNumberModeOptions"
            size="small"
          />
        </settings-form-row>

        <settings-form-row
          label="确认起始小节"
          hint="识别结果缺少明确编号时，在继续转换前询问起始小节"
        >
          <n-switch
            v-model:value="settings.draft.confirmStartMeasureNumber"
            size="small"
          />
        </settings-form-row>

        <settings-form-row
          label="代码配色"
          hint="在简谱编辑器中显示语法高亮"
        >
          <n-switch
            v-model:value="settings.draft.jianpuSyntaxHighlight"
            size="small"
          />
        </settings-form-row>
      </div>
    </section>

    <div class="sv-section-divider" />

    <section class="sv-section">
      <div class="sv-section-heading">
        <div>
          <h3>导出</h3>
          <p>指定转换结果的默认保存位置。</p>
        </div>
      </div>

      <div class="sv-form-stack">
        <settings-form-row
          label="默认导出位置"
          hint="留空则每次导出时手动选择"
        >
          <n-input
            v-model:value="settings.draft.outputDir"
            placeholder="选择默认导出目录"
            size="small"
          >
            <template #suffix>
              <n-button
                size="tiny"
                quaternary
                @click="selectOutputDir"
              >
                浏览
              </n-button>
            </template>
          </n-input>
        </settings-form-row>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { NButton, NInput, NSelect, NSwitch } from 'naive-ui'
import { computed } from 'vue'
import { useSettingsStore } from '../../stores/settings'
import type { MeasureNumberMode, TargetKey } from '../../models/types'
import SettingsFormRow from './SettingsFormRow.vue'

const settings = useSettingsStore()

type KeyAccidental = 'sharp' | 'flat' | 'natural'
type KeyBase = 'C' | 'D' | 'E' | 'F' | 'G' | 'A' | 'B'

const allBases: KeyBase[] = ['C', 'D', 'E', 'F', 'G', 'A', 'B']

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

const accidentalOptions = [
  { label: '无', value: 'natural' as KeyAccidental },
  { label: '升号', value: 'sharp' as KeyAccidental },
  { label: '降号', value: 'flat' as KeyAccidental },
]

const baseKeyOptions = computed(() =>
  allowedBases(accidental.value).map((b) => ({ label: baseLabels[b], value: b })),
)

const accidentalModeOptions = [
  { label: '自由记谱', value: 'auto' },
  { label: '全部升号', value: 'sharp' },
  { label: '全部降号', value: 'flat' },
]

const measureNumberModeOptions: { label: string; value: MeasureNumberMode }[] = [
  { label: '全部显示', value: 'all' },
  { label: '每行首显示', value: 'row_start' },
  { label: '隐藏', value: 'none' },
]

async function selectOutputDir(): Promise<void> {
  const result = await desktopApi().selectDirectory()
  if (result) settings.draft.outputDir = result
}

function desktopApi(): any {
  return (globalThis as any).api
}
</script>

<style scoped>
.sv-key-pickers {
  display: flex;
  align-items: center;
  gap: 12px;
  max-width: 560px;
}

.sv-key-pickers .n-select:first-child {
  width: 96px;
  flex-shrink: 0;
}

.sv-key-pickers .n-select:last-child {
  flex: 1;
}
</style>
