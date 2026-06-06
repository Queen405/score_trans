<template>
  <div class="workspace">
    <div :class="['ws-history', { open: historyOpen }]">
      <div class="ws-hist-head">
        <span class="ws-hist-title">历史</span>
        <div class="ws-hist-actions">
          <n-button size="tiny" quaternary @click="loadHistory" :loading="histLoading">
            <template #icon><n-icon size="14"><RefreshOutline /></n-icon></template>
          </n-button>
          <n-popconfirm @positive-click="handleDeleteAll" :show-icon="false">
            <template #trigger>
              <n-button size="tiny" quaternary type="error" :disabled="!histBatches.length">
                <template #icon><n-icon size="14"><TrashOutline /></n-icon></template>
              </n-button>
            </template>
            确定删除所有历史记录？
          </n-popconfirm>
        </div>
      </div>
      <div class="ws-hist-body">
        <div v-if="!histLoading && !histBatches.length" class="hist-empty">
          <span>暂无记录</span>
        </div>
        <div v-for="batch in histBatches" :key="batch.id" class="hist-batch">
          <div class="hist-batch-head" @click="toggleBatchExpand(batch.id)">
            <span :class="['hist-dot', batch.status === 'completed' ? 'ok' : 'err']" />
            <span class="hist-batch-name">{{ batch.first_file_name || '未知' }}</span>
            <span class="hist-batch-count" v-if="batch.page_count > 1">{{ batch.page_count }}页</span>
            <n-popconfirm @positive-click="handleDeleteBatch(batch.id)" :show-icon="false">
              <template #trigger>
                <button class="hist-delete" type="button" title="删除该历史记录" @click.stop>
                  <n-icon size="12"><TrashOutline /></n-icon>
                </button>
              </template>
              确定删除这次历史记录？
            </n-popconfirm>
            <n-icon size="12" class="hist-expand-icon" :class="{ rotated: expandedBatchId === batch.id }">
              <ChevronForwardOutline />
            </n-icon>
          </div>
          <div class="hist-batch-meta">{{ formatTime(batch.created_at) }}</div>
          <div v-if="expandedBatchId === batch.id" class="hist-pages">
            <div v-if="loadingBatch" class="hist-loading">加载中...</div>
            <div
              v-for="(page, pi) in expandedPages"
              :key="page.id"
              class="hist-page-item"
              @click="handleRestorePage(page)"
            >
              <span :class="['hist-dot small', page.status === 'completed' ? 'ok' : 'err']" />
              <span class="hist-page-name">{{ page.input_file_name || `第${pi + 1}页` }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="ws-main">
      <div class="ws-toolbar">
        <div class="ws-toolbar-left">
          <button class="hist-toggle" title="历史记录" @click="toggleHistory">
            <n-icon size="16"><TimeOutline /></n-icon>
          </button>
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
        <div class="ws-toolbar-right">
          <n-button size="small" @click="musicxmlToJianpu" :loading="store.isBusy" :disabled="!store.hasMusicxml" type="primary">
            <template #icon><n-icon><ArrowForwardOutline /></n-icon></template>
            XML → 简谱
          </n-button>
          <n-button size="small" type="primary" @click="exportScore" :loading="store.isBusy" :disabled="!store.hasMusicxml">
            <template #icon><n-icon><CloudDownloadOutline /></n-icon></template>
            导出
          </n-button>
          <n-select v-model:value="exportFormat" :options="formatOptions" size="small" style="width: 96px" />
        </div>
      </div>

      <div class="ws-layout">
        <div class="ws-panel ws-left">
          <div class="ws-panel-head">
            <span>原始五线谱</span>
            <span v-if="store.originalFileName" class="panel-filename">{{ store.originalFileName }}</span>
          </div>
          <div class="ws-panel-body">
            <original-preview :file-id="store.originalFileId" :file-name="store.originalFileName" />
          </div>
        </div>

        <div class="ws-panel ws-right">
          <div class="ws-panel-head">
            <span>{{ isViewingFinal ? '最终渲染' : '简谱编辑' }}</span>
            <div class="panel-head-actions">
              <div class="panel-head-meta">
                <span class="meta-label">起始小节</span>
                <n-input-number
                  :value="store.startMeasureNumber"
                  @update:value="handleStartMeasureChange"
                  placeholder="自动"
                  :min="1"
                  clearable
                  size="tiny"
                  style="width: 100px"
                />
              </div>
              <n-button size="tiny" quaternary @click="syntaxGuideOpen = true">
                <template #icon><n-icon size="13"><HelpCircleOutline /></n-icon></template>
                语法说明
              </n-button>
              <n-button size="tiny" quaternary @click="saveJianpu" :loading="store.isBusy" :disabled="store.isBusy || !canSaveCurrentPage">
                保存
              </n-button>
              <n-button size="tiny" quaternary @click="toggleFinalView" :loading="isRenderingFinal" :disabled="store.isBusy || !canRenderCurrentScore">
                {{ isViewingFinal ? '编辑' : '渲染' }}
              </n-button>
            </div>
          </div>
          <div class="ws-panel-body">
            <svg-preview
              v-if="isViewingFinal && finalSvgFileId"
              :svg-file-id="finalSvgFileId"
              :ocr-text="store.ocrText"
              editable-ocr
              @update:ocr-text="handleOcrTextUpdate"
            />
            <div v-else-if="isViewingFinal" class="empty-hint">
              <n-icon size="32" :depth="3"><ImageOutline /></n-icon>
              <span>暂无渲染</span>
            </div>
            <jianpu-editor v-else v-model="jianpuText" :start-measure-number="store.startMeasureNumber ?? 1" />
          </div>
        </div>
      </div>
      <jianpu-player
        :musicxml-file-id="store.musicxmlFileId"
        :jianpu-text="jianpuText"
      />
    </div>
    <jianpu-syntax-guide v-model:show="syntaxGuideOpen" />
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch, onMounted, onUnmounted } from 'vue'
import { useTaskStore } from '../stores/task'
import { useSettingsStore } from '../stores/settings'
import { useLogStore } from '../stores/log'
import { convertApi } from '../api/convert'
import { renderApi } from '../api/render'
import { downloadBlob, exportApi, svgToPngBlob } from '../api/export'
import { historyApi } from '../api/history'
import { ApiError, fileExists } from '../api/client'
import type { HistoryBatchListItem, HistoryBatch, HistoryPage } from '../models/types'
import type { TaskPage } from '../stores/task'
import JianpuEditor from '../components/JianpuEditor.vue'
import JianpuPlayer from '../components/JianpuPlayer.vue'
import JianpuSyntaxGuide from '../components/JianpuSyntaxGuide.vue'
import OriginalPreview from '../components/OriginalPreview.vue'
import SvgPreview from '../components/SvgPreview.vue'
import { splitJianpuAndOcr } from '../utils/ocrText'
import { listenHistoryUpdated } from '../utils/historyEvents'
import { ArrowForwardOutline,
  ImageOutline,
  ChevronBackOutline,
  ChevronForwardOutline,
  CloudDownloadOutline,
  TimeOutline,
  RefreshOutline,
  TrashOutline,
  HelpCircleOutline,
} from '@vicons/ionicons5'
import { NButton, NSelect, NIcon, NPopconfirm, NInputNumber, useMessage } from 'naive-ui'

const store = useTaskStore()
const settings = useSettingsStore()
const log = useLogStore()
const message = useMessage()

const jianpuText = ref(store.jianpuText)
const hasJianpuText = computed(() => jianpuText.value.trim().length > 0)
const canRenderCurrentScore = computed(() => hasJianpuText.value || store.hasMusicxml)
const canSaveCurrentPage = computed(() => hasJianpuText.value || store.hasMusicxml || !!store.ocrText.trim() || !!store.svgFileId)
const isViewingFinal = ref(false)
const isRenderingFinal = ref(false)
const finalSvgFileId = ref(store.svgFileId)
const syntaxGuideOpen = ref(false)
const exportFormat = ref('pdf')
const formatOptions = [
  { label: 'PDF', value: 'pdf' },
  { label: 'PNG', value: 'png' },
  { label: 'MIDI', value: 'mid' },
]

const historyOpen = ref(false)
const histBatches = ref<HistoryBatchListItem[]>([])
const histLoading = ref(false)
const expandedBatchId = ref<number | null>(null)
const expandedPages = ref<HistoryPage[]>([])
const loadingBatch = ref(false)
let stopHistoryUpdatedListener: (() => void) | null = null

watch(() => store.jianpuText, (v) => {
  if (v !== jianpuText.value) jianpuText.value = v
})
watch(jianpuText, (v) => {
  if (v !== store.jianpuText) store.setJianpu(v, true)
})
watch(() => store.svgFileId, (v) => { finalSvgFileId.value = v })

onMounted(() => {
  loadHistory()
  stopHistoryUpdatedListener = listenHistoryUpdated(loadHistory)
})

onUnmounted(() => {
  stopHistoryUpdatedListener?.()
  stopHistoryUpdatedListener = null
})

function toggleHistory() {
  historyOpen.value = !historyOpen.value
  if (historyOpen.value) loadHistory()
}

async function loadHistory(): Promise<void> {
  histLoading.value = true
  try {
    histBatches.value = await historyApi.list()
  } catch (e: unknown) {
    log.addError(`加载历史失败：${e instanceof Error ? e.message : String(e)}`)
  } finally {
    histLoading.value = false
  }
}

async function handleDeleteAll(): Promise<void> {
  await historyApi.deleteAll()
  histBatches.value = []
  expandedBatchId.value = null
  expandedPages.value = []
  message.success('已清空')
}

async function handleDeleteBatch(batchId: number): Promise<void> {
  try {
    await historyApi.deleteOne(batchId)
    histBatches.value = histBatches.value.filter((batch) => batch.id !== batchId)
    if (expandedBatchId.value === batchId) {
      expandedBatchId.value = null
      expandedPages.value = []
    }
    message.success('已删除')
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e)
    log.addError(`删除历史失败：${msg}`)
    message.error(msg)
  }
}

async function toggleBatchExpand(batchId: number): Promise<void> {
  if (expandedBatchId.value === batchId) {
    expandedBatchId.value = null
    expandedPages.value = []
    return
  }
  expandedBatchId.value = batchId
  loadingBatch.value = true
  try {
    const batch: HistoryBatch = await historyApi.get(batchId)
    expandedPages.value = batch.pages
  } catch (e: unknown) {
    log.addError(`加载详情失败：${e instanceof Error ? e.message : String(e)}`)
    expandedPages.value = []
  } finally {
    loadingBatch.value = false
  }
}

async function handleRestorePage(page: HistoryPage): Promise<void> {
  if (store.isBusy) {
    message.warning('识别任务进行中，完成后再恢复历史记录。')
    return
  }

  const batchId = expandedBatchId.value
  if (!batchId) return

  let allPages = expandedPages.value
  let pageIndex = allPages.findIndex((p) => p.id === page.id)
  if (!allPages.length || pageIndex < 0) {
    try {
      const batch: HistoryBatch = await historyApi.get(batchId)
      allPages = batch.pages
      expandedPages.value = batch.pages
      pageIndex = allPages.findIndex((p) => p.id === page.id)
    } catch (e: unknown) {
      log.addError(`刷新历史详情失败：${e instanceof Error ? e.message : String(e)}`)
    }
  }
  if (!allPages.length) return

  const warnings: string[] = []
  const selectedChecks = pageIndex >= 0
    ? await checkHistoryPageFiles(allPages[pageIndex], warnings)
    : null
  const migratedPages = allPages.map((p, index) => {
    const split = splitJianpuAndOcr(p.jianpu_text || '')
    const checks = index === pageIndex && selectedChecks
      ? selectedChecks
      : {
          inputOk: !!p.input_file_id,
          musicxmlOk: !!p.musicxml_file_id,
          svgOk: !!p.svg_file_id,
        }
    return { page: p, split, jianpu: split.jianpuText, ...checks }
  })

  store.loadBatch(
    migratedPages.map((r) => ({
      inputFileName: r.inputOk ? r.page.input_file_name : '',
      inputFileId: r.inputOk ? r.page.input_file_id : '',
      originalFileName: r.inputOk && /\.(pdf|png|jpe?g|tiff?|webp)$/i.test(r.page.input_file_name) ? r.page.input_file_name : '',
      originalFileId: r.inputOk && /\.(pdf|png|jpe?g|tiff?|webp)$/i.test(r.page.input_file_name) ? r.page.input_file_id : '',
      historyPageId: r.page.id,
      musicxmlFileId: r.musicxmlOk ? r.page.musicxml_file_id : '',
      jianpuText: r.jianpu,
      ocrText: r.page.ocr_text || r.split.ocrText,
      svgFileId: r.svgOk ? r.page.svg_file_id : '',
      startMeasureNumber: r.page.start_measure_number ?? null,
      status: r.page.status as any,
    })),
    pageIndex >= 0 ? pageIndex : 0,
  )
  isViewingFinal.value = false

  if (warnings.length) { message.warning(warnings.join('；')); return }
  message.success(`已恢复 ${allPages.length} 页`)
}

async function checkHistoryPageFiles(page: HistoryPage, warnings: string[]): Promise<{
  inputOk: boolean
  musicxmlOk: boolean
  svgOk: boolean
}> {
  const [inputOk, musicxmlOk, svgOk] = await Promise.all([
    page.input_file_id ? fileExists(page.input_file_id) : Promise.resolve(false),
    page.musicxml_file_id ? fileExists(page.musicxml_file_id) : Promise.resolve(false),
    page.svg_file_id ? fileExists(page.svg_file_id) : Promise.resolve(false),
  ])
  if (page.input_file_id && !inputOk) warnings.push(`${page.input_file_name}：原始文件已失效`)
  if (page.musicxml_file_id && !musicxmlOk) warnings.push(`${page.input_file_name}：MusicXML 已失效`)
  if (page.svg_file_id && !svgOk) warnings.push(`${page.input_file_name}：SVG 已失效`)
  return { inputOk, musicxmlOk, svgOk }
}

function replaceExpandedHistoryPage(page: HistoryPage): void {
  const index = expandedPages.value.findIndex((entry) => entry.id === page.id)
  if (index < 0) return
  expandedPages.value[index] = page
}

function formatTime(iso: string): string {
  if (!iso) return ''
  const d = new Date(iso.replace(' ', 'T'))
  if (isNaN(d.getTime())) return iso
  const p = (n: number) => String(n).padStart(2, '0')
  return `${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}

function resolveMissingFileId(msg: string): string | null {
  const match = msg.match(/文件不存在[:：]\s*([A-Za-z0-9_-]+)/)
  return match?.[1] ?? null
}

function handleMissingMusicxml(errorMessage: string): string {
  const missingId = resolveMissingFileId(errorMessage)
  if (!missingId || missingId !== store.musicxmlFileId) return errorMessage
  store.setMusicxml('', '')
  finalSvgFileId.value = ''
  return '当前 MusicXML 引用已失效，请回到"识别"页重新识别。'
}

async function exportScore(): Promise<void> {
  store.setBusy(true)
  try {
    const format = exportFormat.value
    if (format === 'mid') {
      const page = currentExportPage()
      const result = page.jianpuText.trim()
        ? await exportApi.exportMidiText({ jianpu_text: page.jianpuText, filename: 'score.mid', title: '简谱' })
        : await exportApi.exportMidi(store.musicxmlFileId, 'score.mid')
      downloadFile(result.file_id, result.filename)
      log.addLog(`导出完成：${result.filename}`)
      message.success('导出完成')
      return
    }

    if (format === 'png') {
      const svgFileId = await renderExportSvg(currentExportPage())
      const png = await svgToPngBlob(exportApi.getDownloadURL(svgFileId), 2)
      downloadBlob(png, 'jianpu.png')
      log.addLog('导出完成：jianpu.png')
      message.success('导出完成')
      return
    }

    const pages = exportPages()
    if (!pages.length) throw new Error('暂无可导出的页面')
    const pngPages: Blob[] = []
    for (const page of pages) {
      const svgFileId = await renderExportSvg(page)
      pngPages.push(await svgToPngBlob(exportApi.getDownloadURL(svgFileId), 2))
    }
    const result = await exportApi.exportPdf(pngPages, 'jianpu.pdf')
    downloadFile(result.file_id, result.filename)
    log.addLog(`导出完成：${result.filename}`)
    message.success('导出完成')
  } catch (e: unknown) {
    log.addError(`导出失败：${e instanceof Error ? e.message : String(e)}`)
    message.error(e instanceof Error ? e.message : String(e))
  } finally {
    store.setBusy(false)
  }
}

function downloadFile(fileId: string, filename: string): void {
  const url = exportApi.getDownloadURL(fileId)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
}

function currentExportPage(): TaskPage {
  const page = store.currentPage
  return {
    ...(page ?? {
      id: 'current',
      historyPageId: store.historyPageId,
      inputFileName: store.inputFileName,
      inputFileId: store.inputFileId,
      originalFileName: store.originalFileName,
      originalFileId: store.originalFileId,
      musicxmlFileId: store.musicxmlFileId,
      musicxmlText: store.currentPage?.musicxmlText ?? '',
      jianpuText: store.jianpuText,
      ocrText: store.ocrText,
      jianpuDirty: store.jianpuDirty,
      svgFileId: store.svgFileId,
      status: 'completed',
      errorMessage: '',
    }),
    jianpuText: jianpuText.value,
    ocrText: store.ocrText,
    svgFileId: finalSvgFileId.value || store.svgFileId,
  } as TaskPage
}

function exportPages(): TaskPage[] {
  if (!store.pages.length) return [currentExportPage()]
  return store.pages.map((page, index) => (
    index === store.currentPageIndex ? currentExportPage() : page
  ))
}

async function renderExportSvg(page: TaskPage): Promise<string> {
  if (page.jianpuText.trim()) {
    const result = await renderApi.jianpuTextSvg({
      jianpu_text: page.jianpuText,
      page_image_file_id: page.originalFileId || page.inputFileId || undefined,
      ocr_text: page.ocrText || undefined,
      include_ocr_text: true,
      title: '简谱',
    })
    if (result.jianpu_text && page.id === store.currentPage?.id) {
      jianpuText.value = result.jianpu_text
      store.setJianpu(result.jianpu_text)
    }
    return result.svg_file_id
  }
  if (page.svgFileId) return page.svgFileId
  if (page.musicxmlFileId) {
    const result = await renderApi.jianpuSvg({
      musicxml_file_id: page.musicxmlFileId,
      page_image_file_id: page.originalFileId || page.inputFileId || undefined,
      target_key: settings.targetKey,
      start_measure_number: store.startMeasureNumber ?? settings.startMeasureNumber ?? undefined,
    })
    return result.svg_file_id
  }
  throw new Error(`页面 ${page.inputFileName || ''} 暂无可导出的渲染结果`)
}

async function musicxmlToJianpu(): Promise<void> {
  store.setBusy(true)
  try {
    const result = await convertApi.musicxmlToJianpu({
      musicxml_file_id: store.musicxmlFileId,
      page_image_file_id: store.originalFileId || undefined,
      target_key: settings.targetKey,
      start_measure_number: store.startMeasureNumber ?? settings.startMeasureNumber ?? undefined,
    })
    const split = splitJianpuAndOcr(result.jianpu_text)
    store.setJianpu(split.jianpuText)
    store.setOcrText(split.ocrText)
    log.addLog('已转换为简谱')
    message.success('转换完成')
  } catch (e: unknown) {
    const raw = e instanceof Error ? e.message : String(e)
    const msg = e instanceof ApiError ? handleMissingMusicxml(raw) : raw
    log.addError(`转换失败：${msg}`)
    message.error(msg)
  } finally {
    store.setBusy(false)
  }
}

async function saveJianpu(): Promise<void> {
  if (!canSaveCurrentPage.value) {
    message.warning('暂无可保存内容')
    return
  }
  store.setBusy(true)
  try {
    await persistRenderedHistory(finalSvgFileId.value || store.svgFileId || '')
    store.markJianpuClean()
    log.addLog('已保存 OMR、简谱和 OCR 信息')
    message.success('已保存')
  } catch (e: unknown) {
    const raw = e instanceof Error ? e.message : String(e)
    log.addError(`保存失败：${raw}`)
    message.error(raw)
  } finally {
    store.setBusy(false)
  }
}

function handleOcrTextUpdate(value: string): void {
  store.setOcrText(value, true)
}

function applyReturnedOcr(value?: string | null): void {
  if (!value || store.ocrText.trim()) return
  store.setOcrText(value)
}


async function renderSvg(): Promise<void> {
  store.setBusy(true)
  try {
    if (hasJianpuText.value) {
      const result = await renderApi.jianpuTextSvg({
        jianpu_text: jianpuText.value,
        page_image_file_id: store.originalFileId || undefined,
        ocr_text: store.ocrText || undefined,
        include_ocr_text: false,
        title: '简谱',
        start_measure_number: store.startMeasureNumber ?? undefined,
      })
      store.setSvg(result.svg_file_id)
      finalSvgFileId.value = result.svg_file_id
      if (result.jianpu_text) {
        jianpuText.value = result.jianpu_text
        store.setJianpu(result.jianpu_text)
      }
      applyReturnedOcr(result.ocr_text)
      isViewingFinal.value = true
    } else {
      const result = await renderApi.jianpuSvg({
        musicxml_file_id: store.musicxmlFileId,
        page_image_file_id: store.originalFileId || undefined,
        target_key: settings.targetKey,
        start_measure_number: store.startMeasureNumber ?? settings.startMeasureNumber ?? undefined,
      })
      store.setSvg(result.svg_file_id)
      finalSvgFileId.value = result.svg_file_id
      isViewingFinal.value = true
    }
    log.addLog('已渲染 SVG')
    message.success('渲染完成')
  } catch (e: unknown) {
    const raw = e instanceof Error ? e.message : String(e)
    const msg = e instanceof ApiError ? handleMissingMusicxml(raw) : raw
    log.addError(`渲染失败：${msg}`)
    message.error(msg)
  } finally {
    store.setBusy(false)
  }
}

async function handleStartMeasureChange(value: number | null): Promise<void> {
  store.setPageStartMeasureNumber(value)
  if (isViewingFinal.value && finalSvgFileId.value) {
    await renderSvg()
  }
}

async function toggleFinalView(): Promise<void> {
  if (isViewingFinal.value) { isViewingFinal.value = false; return }
  isRenderingFinal.value = true
  store.setBusy(true)
  try {
    const result = hasJianpuText.value
      ? await renderApi.jianpuTextSvg({
          jianpu_text: jianpuText.value,
          page_image_file_id: store.originalFileId || undefined,
          ocr_text: store.ocrText || undefined,
          include_ocr_text: false,
          title: '简谱',
          start_measure_number: store.startMeasureNumber ?? undefined,
        })
      : await renderApi.finalOutput({
          musicxml_file_id: store.musicxmlFileId,
          page_image_file_id: store.originalFileId || undefined,
          target_key: settings.targetKey,
          start_measure_number: store.startMeasureNumber ?? settings.startMeasureNumber ?? undefined,
        })
    finalSvgFileId.value = result.svg_file_id
      store.setSvg(result.svg_file_id)
      if ('jianpu_text' in result && result.jianpu_text) {
        jianpuText.value = result.jianpu_text
        store.setJianpu(result.jianpu_text)
      }
      applyReturnedOcr('ocr_text' in result ? result.ocr_text : undefined)
      isViewingFinal.value = true
  } catch (e: unknown) {
    const raw = e instanceof Error ? e.message : String(e)
    const msg = e instanceof ApiError ? handleMissingMusicxml(raw) : raw
    log.addError(`渲染失败：${msg}`)
    message.error(msg)
  } finally {
    store.setBusy(false)
    isRenderingFinal.value = false
  }
}

async function persistRenderedHistory(svgFileId: string): Promise<void> {
  let normalizedJianpu = jianpuText.value
  if (normalizedJianpu.trim()) {
    const normalized = await renderApi.normalizeJianpuText({ jianpu_text: normalizedJianpu, title: '简谱' })
    normalizedJianpu = normalized.jianpu_text
    if (normalizedJianpu !== jianpuText.value) {
      jianpuText.value = normalizedJianpu
      store.setJianpu(normalizedJianpu)
    }
  }
  const payload = {
    musicxml_file_id: store.musicxmlFileId,
    jianpu_text: normalizedJianpu,
    ocr_text: store.ocrText,
    svg_file_id: svgFileId,
    start_measure_number: store.startMeasureNumber ?? null,
    status: 'completed',
    error_message: '',
  }

  if (store.historyPageId) {
    const updated = await historyApi.updatePage(store.historyPageId, payload)
    replaceExpandedHistoryPage(updated)
    return
  }

  const created = await historyApi.create({
    pages: [{
      input_file_name: store.inputFileName,
      input_file_id: store.inputFileId,
      musicxml_file_id: store.musicxmlFileId,
      jianpu_text: normalizedJianpu,
      ocr_text: store.ocrText,
      svg_file_id: svgFileId,
      status: 'completed',
      error_message: '',
    }],
  })
  const pageId = created.pages[0]?.id
  if (pageId) {
    store.setHistoryPageId(pageId)
    await loadHistory()
  }
}
</script>

<style scoped>
.workspace {
  height: 100%;
  display: flex;
  min-height: 0;
  overflow: hidden;
}

.ws-history {
  width: 0;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  border-right: 1px solid var(--border);
  background: var(--bg-elevated);
  overflow: hidden;
  transition: width 0.2s ease;
}

.ws-history.open {
  width: 240px;
}

.ws-hist-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 10px;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}

.ws-hist-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.4px;
}

.ws-hist-actions {
  display: flex;
  gap: 2px;
}

.ws-hist-body {
  flex: 1;
  overflow-y: auto;
  padding: 6px;
}

.hist-empty {
  padding: 24px 0;
  text-align: center;
  font-size: 12px;
  color: var(--text-tertiary);
}

.hist-batch {
  border-radius: var(--radius-sm);
  margin-bottom: 2px;
}

.hist-batch-head {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 8px;
  cursor: pointer;
  border-radius: var(--radius-sm);
  transition: background-color 0.12s ease;
}

.hist-batch-head:hover {
  background: var(--accent-light);
}

.hist-delete {
  width: 20px;
  height: 20px;
  border: 0;
  border-radius: 4px;
  background: transparent;
  color: var(--text-tertiary);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  flex-shrink: 0;
}

.hist-delete:hover {
  background: rgba(220, 38, 38, 0.08);
  color: var(--danger);
}

.hist-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
}

.hist-dot.small {
  width: 4px;
  height: 4px;
}

.hist-dot.ok { background: var(--success); }
.hist-dot.err { background: var(--danger); }

.hist-batch-name {
  flex: 1;
  font-size: 12px;
  font-weight: 500;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.hist-batch-count {
  font-size: 10px;
  color: var(--text-tertiary);
  background: var(--bg-surface);
  padding: 1px 5px;
  border-radius: 8px;
  flex-shrink: 0;
}

.hist-expand-icon {
  color: var(--text-tertiary);
  transition: transform 0.15s ease;
  flex-shrink: 0;
}

.hist-expand-icon.rotated {
  transform: rotate(90deg);
}

.hist-batch-meta {
  font-size: 10px;
  color: var(--text-tertiary);
  padding: 0 8px 4px 20px;
}

.hist-pages {
  padding: 2px 0 4px 20px;
}

.hist-loading {
  font-size: 11px;
  color: var(--text-tertiary);
  padding: 4px 0;
}

.hist-page-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 8px;
  cursor: pointer;
  border-radius: var(--radius-sm);
  transition: background-color 0.12s ease;
}

.hist-page-item:hover {
  background: var(--accent-light);
}

.hist-page-name {
  font-size: 11px;
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ws-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
}

.ws-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding-bottom: 10px;
  flex-shrink: 0;
  flex-wrap: wrap;
}

.ws-toolbar-left {
  display: flex;
  align-items: center;
  gap: 6px;
}

.ws-toolbar-right {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-wrap: wrap;
}

.hist-toggle {
  width: 30px;
  height: 30px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg-elevated);
  color: var(--text-tertiary);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.15s ease;
}

.hist-toggle:hover {
  border-color: var(--accent);
  color: var(--accent);
}

.toolbar-sep {
  width: 1px;
  height: 20px;
  background: var(--border);
  margin: 0 4px;
}

.page-nav {
  display: flex;
  align-items: center;
  gap: 2px;
}

.page-indicator {
  font-size: 12px;
  color: var(--text-tertiary);
  min-width: 36px;
  text-align: center;
}

.ws-layout {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

.ws-panel {
  display: flex;
  flex-direction: column;
  min-width: 0;
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  background: var(--bg-elevated);
  overflow: hidden;
}

.ws-panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 10px;
  border-bottom: 1px solid var(--border);
  background: var(--bg-surface);
  font-size: 11px;
  font-weight: 600;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.4px;
}

.panel-head-actions {
  display: flex;
  align-items: center;
  gap: 4px;
}

.panel-head-meta {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-right: 6px;
  padding-right: 6px;
  border-right: 1px solid var(--border-soft);
}

.meta-label {
  font-weight: 400;
  color: var(--text-tertiary);
  font-size: 10px;
  text-transform: none;
  letter-spacing: 0;
  white-space: nowrap;
}

.panel-filename {
  font-weight: 400;
  color: var(--text-tertiary);
  font-size: 10px;
  text-transform: none;
}

.ws-panel-body {
  flex: 1;
  min-height: 0;
  display: flex;
  padding: 6px;
}

.empty-hint {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: var(--text-tertiary);
  font-size: 13px;
}

@media (max-width: 900px) {
  .ws-layout {
    grid-template-columns: 1fr;
  }

  .ws-history.open {
    width: 200px;
  }
}
</style>
