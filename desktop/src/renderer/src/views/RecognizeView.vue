<template>
  <div class="recognize-view">
    <div class="rv-header">
      <div class="rv-title">
        <h2>智能识别</h2>
        <p>上传乐谱图片或 PDF，快速得到简谱成果</p>
      </div>
      <div v-if="store.pageCount" class="page-nav">
        <n-button size="small" quaternary :disabled="!store.canPrevPage || store.isBusy" @click="store.prevPage()">
          <template #icon><n-icon><ChevronBackOutline /></n-icon></template>
        </n-button>
        <span class="page-indicator">{{ store.currentPageIndex + 1 }} / {{ store.pageCount }}</span>
        <n-button size="small" quaternary :disabled="!store.canNextPage || store.isBusy" @click="store.nextPage()">
          <template #icon><n-icon><ChevronForwardOutline /></n-icon></template>
        </n-button>
      </div>
    </div>

    <file-uploader :disabled="store.isBusy" @uploaded="onFileUploaded" />

    <n-progress
      v-if="store.isBusy"
      type="line"
      :percentage="progressPercent"
      :indicator-placement="'inside'"
      processing
      class="rv-progress"
    >
      {{ progressText }}
    </n-progress>

    <div class="rv-actions">
      <n-button
        type="primary"
        @click="recognize"
        :loading="store.isBusy"
        :disabled="store.isBusy || !store.hasInput"
      >
        <template #icon><n-icon><ScanOutline /></n-icon></template>
        识别并自动填充
      </n-button>
      <n-button
        @click="recognizeAllPages"
        :loading="store.isBusy"
        :disabled="store.isBusy || !store.pageCount"
        secondary
      >
        <template #icon><n-icon><FlashOutline /></n-icon></template>
        批量识别全部
      </n-button>
    </div>

    <div v-if="store.pages.length" class="pages-strip">
      <div
        v-for="(page, index) in store.pages"
        :key="page.id"
        :class="['page-card', { active: index === store.currentPageIndex }]"
        @click="store.selectPage(index)"
      >
        <button class="page-del" type="button" @click.stop="removePage(index)">
          <n-icon size="12"><CloseOutline /></n-icon>
        </button>
        <div class="page-thumb">
          <img
            v-if="isPreviewable(page.inputFileName)"
            :src="getFileURL(page.inputFileId)"
            :alt="page.inputFileName"
          />
          <n-icon v-else size="20" class="page-icon"><DocumentOutline /></n-icon>
        </div>
        <div class="page-label">
          <span class="page-name">{{ page.inputFileName }}</span>
          <span :class="['page-status', page.status]">{{ statusText(page.status) }}</span>
        </div>
      </div>
    </div>

    <n-card
      v-if="store.musicxmlText"
      title="MusicXML 预览"
      size="small"
      :bordered="true"
      class="rv-preview"
    >
      <n-code :code="store.musicxmlText" language="xml" word-wrap />
    </n-card>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useTaskStore } from '../stores/task'
import { useLogStore } from '../stores/log'
import { useSettingsStore } from '../stores/settings'
import { pipelineApi } from '../api/pipeline'
import { historyApi } from '../api/history'
import { getFileURL } from '../api/client'
import type { HistoryCreateRequest } from '../models/types'
import { splitJianpuAndOcr } from '../utils/ocrText'
import FileUploader from '../components/FileUploader.vue'
import {
  ScanOutline,
  FlashOutline,
  CloseOutline,
  ChevronBackOutline,
  ChevronForwardOutline,
  DocumentOutline,
} from '@vicons/ionicons5'
import { NButton, NTag, NCard, NCode, NIcon, NProgress, useMessage } from 'naive-ui'

const store = useTaskStore()
const log = useLogStore()
const settings = useSettingsStore()
const message = useMessage()
const progressPercent = ref(0)
const progressText = ref('等待开始')

function isPreviewable(fileName: string): boolean {
  return /\.(pdf|png|jpe?g|tiff?|webp)$/i.test(fileName)
}

function statusText(status: string): string {
  const map: Record<string, string> = { completed: '完成', failed: '失败', processing: '处理中', pending: '待处理' }
  return map[status] ?? ''
}

function removePage(index: number): void {
  const page = store.pages[index]
  if (!page) return
  store.removePage(index)
  log.addLog(`已移除：${page.inputFileName}`)
}

async function onFileUploaded(fileId: string, fileName: string): Promise<void> {
  if (store.isBusy) return
  store.addInputPage(fileName, fileId)
  log.addLog(`已加入：${fileName}`)
}

function setProgress(percent: number, text: string): void {
  progressPercent.value = Math.max(0, Math.min(100, Math.round(percent)))
  progressText.value = text
}

interface PageResult {
  page_index: number
  input_file_name: string
  input_file_id: string
  musicxml_file_id: string
  jianpu_text: string
  ocr_text: string
  svg_file_id: string
  status: string
  error_message: string
}

async function runPipelineForPage(
  pageIndex: number,
  rangeStart = 0,
  rangeEnd = 100,
): Promise<PageResult> {
  const page = store.pages[pageIndex]
  if (!page?.inputFileId || !page.inputFileName) {
    return { page_index: pageIndex, input_file_name: '', input_file_id: '', musicxml_file_id: '', jianpu_text: '', ocr_text: '', svg_file_id: '', status: 'failed', error_message: '无输入文件' }
  }

  const mapPercent = (p: number) => rangeStart + (p / 100) * (rangeEnd - rangeStart)

  store.selectPage(pageIndex)
  store.setCurrentPageStatus('processing')
  const sourceFileId = page.inputFileId
  const sourceFileName = page.inputFileName

  setProgress(mapPercent(8), `读取：${sourceFileName}`)
  const resp = await fetch(getFileURL(sourceFileId))
  const blob = await resp.blob()

  setProgress(mapPercent(24), '识别与转换中')
  const result = await pipelineApi.run(
    new File([blob], sourceFileName),
    settings.targetKey,
    settings.startMeasureNumber ?? undefined,
  )

  setProgress(mapPercent(82), '写入结果')
  store.setMusicxml(result.musicxml_file_id, '')
  if (isPreviewable(sourceFileName)) {
    store.setOriginalFile(sourceFileName, sourceFileId)
  } else {
    store.clearOriginalFile()
  }
  const split = splitJianpuAndOcr(result.jianpu_text)
  store.setJianpu(split.jianpuText)
  store.setOcrText(split.ocrText)
  store.setSvg(result.svg_file_id)
  store.setCurrentPageStatus('completed')
  log.addLog(`识别完成：${sourceFileName}`)

  return {
    page_index: pageIndex,
    input_file_name: sourceFileName,
    input_file_id: sourceFileId,
    musicxml_file_id: result.musicxml_file_id,
    jianpu_text: split.jianpuText,
    ocr_text: split.ocrText,
    svg_file_id: result.svg_file_id,
    status: 'completed',
    error_message: '',
  }
}

async function saveHistoryBatch(pageResults: PageResult[]): Promise<void> {
  if (!pageResults.length) return
  try {
    const created = await historyApi.create({
      pages: pageResults.map((r) => ({
        input_file_name: r.input_file_name,
        input_file_id: r.input_file_id,
        musicxml_file_id: r.musicxml_file_id,
        jianpu_text: r.jianpu_text,
        ocr_text: r.ocr_text,
        svg_file_id: r.svg_file_id,
        status: r.status,
        error_message: r.error_message,
      })),
    })
    created.pages.forEach((page, index) => {
      const pageIndex = pageResults[index]?.page_index
      if (typeof pageIndex === 'number') store.setPageHistoryPageId(pageIndex, page.id)
    })
  } catch { /* ignore */ }
}

async function recognize(): Promise<void> {
  const pageIndex = store.currentPageIndex
  if (pageIndex < 0 || !store.hasInput) return

  store.setBusy(true)
  const results: PageResult[] = []
  try {
    setProgress(0, '准备识别')
    const r = await runPipelineForPage(pageIndex, 0, 100)
    results.push(r)
    setProgress(100, '完成')
    message.success('识别完成')
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e)
    store.setCurrentPageStatus('failed', msg)
    results.push({
      page_index: pageIndex,
      input_file_name: store.pages[pageIndex]?.inputFileName ?? '',
      input_file_id: store.pages[pageIndex]?.inputFileId ?? '',
      musicxml_file_id: '', jianpu_text: '', ocr_text: '', svg_file_id: '',
      status: 'failed', error_message: msg,
    })
    log.addError(`识别失败：${msg}`)
    message.error(msg)
  } finally {
    await saveHistoryBatch(results)
    store.setBusy(false)
  }
}

async function recognizeAllPages(): Promise<void> {
  const indexes = store.pages
    .map((page, index) => ({ page, index }))
    .filter((entry) => !!entry.page.inputFileId)
    .map((entry) => entry.index)
  if (!indexes.length) return

  store.setBusy(true)
  const results: PageResult[] = []
  try {
    setProgress(0, '准备批量识别')
    for (let i = 0; i < indexes.length; i += 1) {
      const pageIndex = indexes[i]
      const rangeStart = (i / indexes.length) * 100
      const rangeEnd = ((i + 1) / indexes.length) * 100
      setProgress(rangeStart, `处理第 ${i + 1} / ${indexes.length} 页`)
      try {
        const r = await runPipelineForPage(pageIndex, rangeStart, rangeEnd)
        results.push(r)
      } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : String(e)
        store.selectPage(pageIndex)
        store.setCurrentPageStatus('failed', msg)
        results.push({
          page_index: pageIndex,
          input_file_name: store.pages[pageIndex]?.inputFileName ?? '',
          input_file_id: store.pages[pageIndex]?.inputFileId ?? '',
          musicxml_file_id: '', jianpu_text: '', ocr_text: '', svg_file_id: '',
          status: 'failed', error_message: msg,
        })
        log.addError(`第 ${i + 1} 页失败：${msg}`)
      }
      setProgress(rangeEnd, `已完成 ${i + 1} / ${indexes.length} 页`)
    }
    setProgress(100, '批量识别完成')
    message.success('批量识别完成')
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e)
    log.addError(`批量识别失败：${msg}`)
    message.error(msg)
  } finally {
    await saveHistoryBatch(results)
    store.setBusy(false)
  }
}
</script>

<style scoped>
.recognize-view {
  display: flex;
  flex-direction: column;
  gap: 16px;
  max-width: 900px;
  margin: 0 auto;
  min-height: 100%;
  justify-content: center;
}

.rv-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.rv-header h2 {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.rv-header p {
  font-size: 13px;
  color: var(--text-tertiary);
  margin: 4px 0 0;
}

.page-nav {
  display: flex;
  align-items: center;
  gap: 4px;
}

.page-indicator {
  font-size: 12px;
  color: var(--text-tertiary);
  min-width: 40px;
  text-align: center;
}

.rv-progress {
  margin: 0;
}

.rv-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.pages-strip {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  padding: 4px 0;
}

.page-card {
  width: 110px;
  position: relative;
  cursor: pointer;
  border-radius: var(--radius-md);
  border: 1.5px solid var(--border);
  background: var(--bg-elevated);
  padding: 6px;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

.page-card:hover {
  border-color: var(--accent);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.page-card.active {
  border-color: var(--accent);
  box-shadow: 0 0 0 1px var(--accent);
}

.page-del {
  position: absolute;
  top: 2px;
  right: 2px;
  width: 20px;
  height: 20px;
  border: 0;
  border-radius: 50%;
  background: var(--bg-base);
  color: var(--text-tertiary);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  opacity: 0;
  transition: opacity 0.12s ease, background-color 0.12s ease, color 0.12s ease;
  z-index: 2;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.page-card:hover .page-del {
  opacity: 1;
}

.page-del:hover {
  background: var(--danger);
  color: #fff;
}

.page-thumb {
  width: 100%;
  height: 64px;
  border-radius: var(--radius-sm);
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-surface);
}

.page-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.page-icon {
  color: var(--text-tertiary);
}

.page-label {
  margin-top: 4px;
  text-align: center;
}

.page-name {
  display: block;
  font-size: 10px;
  color: var(--text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.page-status {
  font-size: 10px;
  color: var(--text-tertiary);
}

.page-status.completed { color: var(--success); }
.page-status.failed { color: var(--danger); }
.page-status.processing { color: var(--warning); }

.rv-preview {
  border-radius: var(--radius-lg);
}
</style>
