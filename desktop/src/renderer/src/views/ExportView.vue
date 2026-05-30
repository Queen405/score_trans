<template>
  <div class="export-view">
    <h2>导出</h2>
    <p class="subtitle">导出 MusicXML 或交给 MuseScore 生成成品文件</p>

    <div class="export-section">
      <div class="export-row">
        <n-button
          @click="saveMusicxml"
          :disabled="!store.hasMusicxml"
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
        >
          <template #icon><n-icon><CloudDownloadOutline /></n-icon></template>
          MuseScore 导出
        </n-button>
        <n-select
          v-model:value="exportFormat"
          :options="formatOptions"
          style="width: 120px"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useTaskStore } from '../stores/task'
import { useLogStore } from '../stores/log'
import { exportApi } from '../api/export'
import { getFileURL } from '../api/client'
import { DocumentTextOutline, CloudDownloadOutline } from '@vicons/ionicons5'
import { NButton, NSelect, NIcon, useMessage } from 'naive-ui'

const store = useTaskStore()
const log = useLogStore()
const message = useMessage()

const exportFormat = ref('pdf')
const formatOptions = [
  { label: 'PDF', value: 'pdf' },
  { label: 'PNG', value: 'png' },
  { label: 'MIDI', value: 'mid' },
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
  max-width: 700px;
}

.export-view h2 {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.subtitle {
  font-size: 13px;
  color: var(--text-tertiary);
  margin: 4px 0 20px;
}

.export-section {
  padding: 20px;
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  background: var(--bg-elevated);
}

.export-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
</style>
