<template>
  <div class="export-view">
    <h2>导出</h2>
    <p class="subtitle">
      导出简谱为 PDF、PNG、SVG 或 MIDI 文件
    </p>

    <div class="export-section">
      <div class="export-row">
        <n-select
          v-model:value="exportFormat"
          :options="formatOptions"
          style="width: 120px"
        />
        <n-button
          type="primary"
          :loading="store.isBusy"
          :disabled="!canExport"
          @click="doExport"
        >
          <template #icon>
            <n-icon><CloudDownloadOutline /></n-icon>
          </template>
          {{ exportLabel }}
        </n-button>
        <n-button
          :disabled="!store.hasMusicxml"
          secondary
          @click="saveMusicxml"
        >
          <template #icon>
            <n-icon><DocumentTextOutline /></n-icon>
          </template>
          MusicXML
        </n-button>
      </div>
      <p
        v-if="store.pageCount > 1 && exportFormat === 'pdf'"
        class="batch-hint"
      >
        当前共 {{ store.pageCount }} 页，将合并为一个 PDF 文件
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useWorkspaceStore } from '../stores/workspace'
import { useLogStore } from '../stores/log'
import { useSettingsStore } from '../stores/settings'
import {
  exportApi,
  svgToJpegBlob,
  svgToPngBlob,
  downloadSvg,
  downloadBlob,
} from '../api/export'
import { renderApi } from '../api/render'
import { getFileURL, requireData } from '../api/client'
import {
  buildBatchRenderRequests,
  buildSourcePageRenderRequests,
  renderPageOcrTextsForRequest,
  renderResponsePageOcrTexts,
} from '../utils/batchRender'
import { DocumentTextOutline, CloudDownloadOutline } from '@vicons/ionicons5'
import { NButton, NSelect, NIcon, useMessage } from 'naive-ui'

const store = useWorkspaceStore()
const settings = useSettingsStore()
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
  return !!store.currentBatchRenderPageFileIds.length
    || !!store.currentBatchJianpuText.trim()
    || store.pages.some((p) => !!p.svgFileId || !!p.musicxmlFileId || !!p.jianpuText.trim())
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
      const svgId = (await ensureExportSvgIds())[0] || store.svgFileId
      if (!svgId) throw new Error('没有可导出的 SVG')
      downloadSvg(svgId)
      log.addLog('已导出 SVG')
      message.success('导出完成')
      return
    }

    if (fmt === 'png') {
      const svgId = (await ensureExportSvgIds())[0] || store.svgFileId
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
      const result = await requireData(exportApi.exportMidi(store.musicxmlFileId))
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
  const svgIds = await ensureExportSvgIds()
  if (svgIds.length === 0) throw new Error('没有可导出的页面')

  const imageBlobs: Blob[] = []
  for (let i = 0; i < svgIds.length; i++) {
    const svgUrl = getFileURL(svgIds[i])
    const blob = await svgToJpegBlob(svgUrl)
    imageBlobs.push(blob)
    log.addLog(`渲染页面 ${i + 1}/${svgIds.length}`)
  }

  const result = await requireData(exportApi.exportPdf(imageBlobs))
  const url = exportApi.getDownloadURL(result.file_id)
  const a = document.createElement('a')
  a.href = url
  a.download = result.filename
  a.click()
  log.addLog(`已导出 PDF（${svgIds.length} 页）`)
  message.success('导出完成')
}

async function ensureExportSvgIds(): Promise<string[]> {
  if (!store.currentBatchRenderPageOcrDirty && store.currentBatchRenderPageFileIds.length) {
    return store.currentBatchRenderPageFileIds
  }
  const pages = buildBatchRenderPages()
  if (!pages.length) {
    return store.pages.flatMap((page) =>
      page.svgFileIds.length ? page.svgFileIds : (page.svgFileId ? [page.svgFileId] : []),
    )
  }
  const result = await requireData(renderApi.batchA4({
    pages,
    source_pages: buildBatchRenderSourcePages(),
    render_page_ocr_texts: currentRenderPageOcrTextsForRequest(),
    target_key: settings.targetKey,
    accidental_mode: settings.accidentalMode,
    measure_number_mode: settings.measureNumberMode,
    title: '简谱',
  }))
  const ids = result.pages.map((page) => page.svg_file_id).filter(Boolean)
  store.setBatchRenderPageFileIds(ids)
  store.setBatchRenderPageOcrTexts(renderResponsePageOcrTexts(result.pages), false)
  store.markBatchRenderPageOcrClean()
  return ids
}

function buildBatchRenderPages() {
  const batchText = store.currentBatchJianpuText.trim()
  const batchPages = store.currentBatchPages.length ? store.currentBatchPages : store.pages
  return buildBatchRenderRequests(batchPages, {
    jianpuText: batchText,
    title: '简谱',
    combineJianpuText: true,
  })
}

function buildBatchRenderSourcePages() {
  const batchPages = store.currentBatchPages.length ? store.currentBatchPages : store.pages
  return buildSourcePageRenderRequests(batchPages, '简谱')
}

function currentRenderPageOcrTextsForRequest() {
  return renderPageOcrTextsForRequest(
    store.currentBatchRenderPageOcrTextEntries(),
    store.currentBatchRenderPageOcrDirty,
  )
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
