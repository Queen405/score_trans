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
          <n-select
            v-model:value="settings.draft.targetKey"
            :options="keyOptions"
            size="small"
          />
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
import { useSettingsStore } from '../../stores/settings'
import type { MeasureNumberMode, TargetKey } from '../../models/types'
import SettingsFormRow from './SettingsFormRow.vue'

const settings = useSettingsStore()

const keyOptions: { label: string; value: TargetKey }[] = [
  { label: 'Cb', value: 'Cb' },
  { label: 'Gb', value: 'Gb' },
  { label: 'Db', value: 'Db' },
  { label: 'Ab', value: 'Ab' },
  { label: 'Eb', value: 'Eb' },
  { label: 'Bb', value: 'Bb' },
  { label: 'F', value: 'F' },
  { label: 'C', value: 'C' },
  { label: 'G', value: 'G' },
  { label: 'D', value: 'D' },
  { label: 'A', value: 'A' },
  { label: 'E', value: 'E' },
  { label: 'B', value: 'B' },
  { label: 'F#', value: 'F#' },
  { label: 'C#', value: 'C#' },
]

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
