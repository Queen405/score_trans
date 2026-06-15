<template>
  <div class="export-view">
    <h2>导出</h2>
    <p class="subtitle">导出简谱为 PDF、PNG、SVG 或 MIDI 文件</p>

    <div class="export-section">
      <div class="export-row">
        <n-select
          v-model:value="exportFormat"
          :options="formatOptions"
          style="width: 120px"
        />
        <n-button
          type="primary"
          @click="doExport"
          :loading="store.isBusy"
          :disabled="!canExport"
        >
          <template #icon><n-icon><CloudDownloadOutline /></n-icon></template>
          {{ exportLabel }}
        </n-button>
        <n-button
          @click="saveMusicxml"
          :disabled="!store.hasMusicxml"
          secondary
        >
          <template #icon><n-icon><DocumentTextOutline /></n-icon></template>
          MusicXML
        </n-button>
      </div>
      <p v-if="store.pageCount > 1 && exportFormat === 'pdf'" class="batch-hint">
        当前共 {{ store.pageCount }} 页，将合并为一个 PDF 文件
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useTaskStore } from '../stores/task'
import { useLogStore } from '../stores/log'
import {
  exportApi,
  svgToPngBlob,
  downloadSvg,
  downloadBlob,
} from '../api/export'
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
  { label: 'SVG', value: 'svg' },
  { label: 'MIDI', value: 'mid' },
]

const canExport = computed(() => {
  if (exportFormat.value === 'mid') return store.hasMusicxml
  return !!store.currentBatchRenderPageFileIds.length || store.pages.some((p) => !!p.svgFileId)
})

const exportLabel = computed(() => {
  if (store.pageCount > 1 && exportFormat.value === 'pdf') return '导出全部为 PDF'
  return '导出'
})

function saveMusicxml(): void {
  const url = getFileURL(store.musicxmlFileId)
  const a = document.createElement('a')
  a.href = url
  a.download = 'score.musicxml'
  a.click()
  log.addLog('已保存 MusicXML')
}

async function doExport(): Promise<void> {
  store.setBusy(true)
  try {
    const fmt = exportFormat.value

    if (fmt === 'svg') {
      const svgId = store.currentBatchRenderPageFileIds[0] || store.svgFileId
      if (!svgId) throw new Error('没有可导出的 SVG')
      downloadSvg(svgId)
      log.addLog('已导出 SVG')
      message.success('导出完成')
      return
    }

    if (fmt === 'png') {
      const svgId = store.currentBatchRenderPageFileIds[0] || store.svgFileId
      if (!svgId) throw new Error('没有可导出的 SVG')
      const url = getFileURL(svgId)
      const blob = await svgToPngBlob(url)
      downloadBlob(blob, 'jianpu.png')
      log.addLog('已导出 PNG')
      message.success('导出完成')
      return
    }

    if (fmt === 'pdf') {
      await exportPdfBatch()
      return
    }

    if (fmt === 'mid') {
      if (!store.musicxmlFileId) throw new Error('没有可导出的 MusicXML')
      const result = await exportApi.exportMidi(store.musicxmlFileId)
      const url = exportApi.getDownloadURL(result.file_id)
      const a = document.createElement('a')
      a.href = url
      a.download = result.filename
      a.click()
      log.addLog('已导出 MIDI')
      message.success('导出完成')
    }
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e)
    log.addError(`导出失败：${msg}`)
    message.error(msg)
  } finally {
    store.setBusy(false)
  }
}

async function exportPdfBatch(): Promise<void> {
  const svgIds = store.currentBatchRenderPageFileIds.length
    ? store.currentBatchRenderPageFileIds
    : store.pages.flatMap((page) => page.svgFileIds.length ? page.svgFileIds : (page.svgFileId ? [page.svgFileId] : []))
  if (svgIds.length === 0) throw new Error('没有可导出的页面')

  const pngBlobs: Blob[] = []
  for (let i = 0; i < svgIds.length; i++) {
    const svgUrl = getFileURL(svgIds[i])
    const blob = await svgToPngBlob(svgUrl)
    pngBlobs.push(blob)
    log.addLog(`渲染页面 ${i + 1}/${svgIds.length}`)
  }

  const result = await exportApi.exportPdf(pngBlobs)
  const url = exportApi.getDownloadURL(result.file_id)
  const a = document.createElement('a')
  a.href = url
  a.download = result.filename
  a.click()
  log.addLog(`已导出 PDF（${svgIds.length} 页）`)
  message.success('导出完成')
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

.batch-hint {
  font-size: 12px;
  color: var(--text-tertiary);
  margin: 8px 0 0;
}
</style>
