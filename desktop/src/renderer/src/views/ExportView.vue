<template>
  <div class="export-view">
    <n-card title="📤 导出乐谱" :bordered="false" class="export-card">
      <n-space vertical :size="20">
        <n-space :size="12" wrap align="center">
          <n-button
            @click="saveMusicxml"
            :disabled="!store.hasMusicxml"
            size="large"
            secondary
          >
            <template #icon><n-icon><DocumentTextOutline /></n-icon></template>
            保存 MusicXML
          </n-button>
          <n-button
            type="primary"
            @click="exportScore"
            :loading="store.isBusy"
            :disabled="!store.hasMusicxml"
            size="large"
          >
            <template #icon><n-icon><CloudDownloadOutline /></n-icon></template>
            MuseScore 导出
          </n-button>
          <n-select
            v-model:value="exportFormat"
            :options="formatOptions"
            style="width: 130px"
            size="large"
          />
        </n-space>

        <n-divider style="margin: 0" />

        <n-card title="📋 操作日志" size="small" :bordered="false" class="log-card">
          <log-panel />
        </n-card>
      </n-space>
    </n-card>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useTaskStore } from '../stores/task'
import { useLogStore } from '../stores/log'
import { exportApi } from '../api/export'
import { getFileURL } from '../api/client'
import LogPanel from '../components/LogPanel.vue'
import { DocumentTextOutline, CloudDownloadOutline } from '@vicons/ionicons5'
import { NSpace, NButton, NSelect, NCard, NDivider, NIcon, useMessage } from 'naive-ui'

const store = useTaskStore()
const log = useLogStore()
const message = useMessage()

const exportFormat = ref('pdf')
const formatOptions = [
  { label: '📄 PDF', value: 'pdf' },
  { label: '🖼️ PNG', value: 'png' },
  { label: '🎹 MIDI', value: 'mid' },
]

function saveMusicxml(): void {
  const url = getFileURL(store.musicxmlFileId)
  const a = document.createElement('a')
  a.href = url
  a.download = 'score.musicxml'
  a.click()
  log.addLog('已保存 MusicXML')
}

async function exportScore(): Promise<void> {
  store.setBusy(true)
  try {
    const result = await exportApi.exportScore({
      musicxml_file_id: store.musicxmlFileId,
      output_format: exportFormat.value as 'pdf' | 'png' | 'mid',
    })
    const url = exportApi.getDownloadURL(result.file_id)
    const a = document.createElement('a')
    a.href = url
    a.download = result.filename
    a.click()
    log.addLog(`导出完成：${result.filename}`)
    message.success('导出完成')
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e)
    log.addError(`导出失败：${msg}`)
    message.error(msg)
  } finally {
    store.setBusy(false)
  }
}
</script>

<style scoped>
.export-view {
  max-width: 800px;
}

.export-card {
  border-radius: 12px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
}

.log-card {
  background: rgba(0, 0, 0, 0.02);
  border-radius: 8px;
}
</style>
