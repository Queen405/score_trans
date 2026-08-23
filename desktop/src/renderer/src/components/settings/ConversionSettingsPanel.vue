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
            <n-checkbox
              v-model:checked="autoKey"
              title="勾选后自动识别 MusicXML 中的调号，未识别到时默认 C 调"
            >
              自动识别
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
          label="识别五线谱文字（OCR）"
          hint="关闭后仍执行音符识别、MusicXML 转换和简谱生成"
        >
          <n-switch
            v-model:value="settings.draft.enableOmrOcr"
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
          <h3>简谱版式</h3>
          <p>调整 A4 简谱的整体大小与排版密度。</p>
        </div>
      </div>

      <div class="sv-form-stack">
        <settings-form-row label="整体大小">
          <div class="sv-layout-control">
            <n-slider
              v-model:value="settings.draft.jianpuContentScalePercent"
              :min="65"
              :max="100"
              :step="1"
            />
            <n-input-number
              v-model:value="settings.draft.jianpuContentScalePercent"
              :min="65"
              :max="100"
              :step="1"
              size="small"
            >
              <template #suffix>
                %
              </template>
            </n-input-number>
          </div>
        </settings-form-row>

        <settings-form-row label="行间距">
          <div class="sv-layout-control">
            <n-slider
              v-model:value="settings.draft.jianpuSystemGapPercent"
              :min="80"
              :max="120"
              :step="1"
            />
            <n-input-number
              v-model:value="settings.draft.jianpuSystemGapPercent"
              :min="80"
              :max="120"
              :step="1"
              size="small"
            >
              <template #suffix>
                %
              </template>
            </n-input-number>
          </div>
        </settings-form-row>

        <settings-form-row label="短音符间距">
          <div class="sv-layout-control">
            <n-slider
              v-model:value="settings.draft.jianpuShortNoteGapPercent"
              :min="80"
              :max="120"
              :step="1"
            />
            <n-input-number
              v-model:value="settings.draft.jianpuShortNoteGapPercent"
              :min="80"
              :max="120"
              :step="1"
              size="small"
            >
              <template #suffix>
                %
              </template>
            </n-input-number>
          </div>
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

        <settings-form-row
          label="MIDI 速度"
          hint="关闭时使用识别到的速度（未识别到则用默认 120 BPM），开启后使用指定速度"
        >
          <div class="sv-midi-tempo">
            <n-switch
              v-model:value="manualTempo"
              size="small"
            />
            <n-input-number
              v-model:value="tempoBpm"
              :disabled="!manualTempo"
              :min="1"
              :max="400"
              size="small"
              style="width: 140px"
            >
              <template #suffix>
                BPM
              </template>
            </n-input-number>
          </div>
        </settings-form-row>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { NButton, NCheckbox, NInput, NInputNumber, NSelect, NSlider, NSwitch } from 'naive-ui'
import { computed, ref, watch } from 'vue'
import { useSettingsStore } from '../../stores/settings'
import type { MeasureNumberMode, TargetKey } from '../../models/types'
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

const lastSpecificTempo = ref(120)

watch(
  () => settings.draft.midiTempo,
  (value) => {
    if (value !== 'auto') lastSpecificTempo.value = value
  },
  { immediate: true },
)

const manualTempo = computed<boolean>({
  get: () => settings.draft.midiTempo !== 'auto',
  set: (value: boolean) => {
    settings.draft.midiTempo = value ? lastSpecificTempo.value : 'auto'
  },
})

const tempoBpm = computed<number>({
  get: () =>
    typeof settings.draft.midiTempo === 'number'
      ? settings.draft.midiTempo
      : lastSpecificTempo.value,
  set: (value: number) => {
    lastSpecificTempo.value = value
    settings.draft.midiTempo = value
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

.sv-midi-tempo {
  display: flex;
  align-items: center;
  gap: 12px;
}

.sv-layout-control {
  display: grid;
  grid-template-columns: minmax(160px, 1fr) 108px;
  align-items: center;
  gap: 16px;
  max-width: 560px;
}

@media (max-width: 720px) {
  .sv-layout-control {
    grid-template-columns: minmax(0, 1fr) 96px;
  }
}
</style>
