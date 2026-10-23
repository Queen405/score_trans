import { nextTick } from 'vue'
import { useMessage } from 'naive-ui'
import { t } from '../i18n'
import { useWorkspaceStore } from '../stores/workspace'
import { useSettingsStore } from '../stores/settings'
import { useLogStore } from '../stores/log'
import { historyApi } from '../api/history'
import { filesApi } from '../api/files'
import { ApiError, requireData } from '../api/client'
import { splitJianpuAndOcr } from '../utils/ocrText'
import {
  isPreviewableHistoryFile,
} from '../utils/historyPageState'
import { liveRecognitionTaskPatch } from '../utils/liveRecognitionState'
import type { HistoryBatch, HistoryBatchListItem, HistoryPage } from '../models/types'
import type { TaskPage } from '../stores/workspace'
import {
  buildBatchRenderRequests,
  renderResponsePageIds,
  renderResponsePageOcrTexts,
} from '../utils/batchRender'
import { usePublicationRender } from './usePublicationRender'
import { isRenderAborted } from '../utils/renderAbort'
import { createWorkspacePersistence } from '../utils/workspacePersistence'
import { notifyHistoryUpdated } from '../utils/historyEvents'
import {
  isRenderLayoutStale,
  PUBLICATION_ENGINE_VERSION,
} from '../utils/jianpuLayout'

type RebuildOutcome = 'completed' | 'aborted' | 'failed'

export function useHistoryRestore(flushPendingEdits: () => Promise<void>) {
  const message = useMessage()
  const store = useWorkspaceStore()
  const settings = useSettingsStore()
  const log = useLogStore()
  const publicationRender = usePublicationRender()
  const workspacePersistence = createWorkspacePersistence(historyApi, notifyHistoryUpdated)
  let restoreCheckSeq = 0

  // loadBatch 会整页替换当前批次。切走前先保存仍有历史目标的编辑；没有本地批次
  // 或历史目标已被删除时保留现场，等目标成功加载后再随工作区替换一起丢弃。
  async function persistUnsavedBeforeRestore(): Promise<boolean> {
    store.setBusy(true)
    try {
      await flushPendingEdits()
      if (!store.hasUnsavedChanges) return true
      const result = await workspacePersistence.saveAllUnsavedBatches(store, {
        mode: 'discard',
      })
      if (result.savedBatchIds.length) {
        log.addLog(t('runtime.history.autoSavedBeforeRestore'))
      }
      return true
    } catch (e: unknown) {
      if (isRenderAborted(e)) return false
      const msg = e instanceof Error ? e.message : String(e)
      log.addError(t('runtime.history.autoSaveFailed', { message: msg }))
      message.error(t('runtime.history.saveFailed', { message: msg }))
      return false
    } finally {
      store.setBusy(false)
    }
  }

  async function restoreBatch(entry: HistoryBatchListItem): Promise<boolean> {
    if (store.isBusy) {
      message.warning(t('runtime.history.recognizingInProgress'))
      return false
    }

    if (!(await persistUnsavedBeforeRestore())) return false

    let batch: HistoryBatch
    try {
      batch = await requireData(historyApi.get(entry.id))
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e)
      log.addError(t('runtime.history.loadDetailFailed', { message: msg }))
      message.error(msg)
      return false
    }

    const pages = batch.pages
    if (!pages.length) return false
    const renderPageFileIds = batch.render_page_file_ids ?? []
    store.loadBatch(
      pages.map((page) => buildTaskPageInput(page, batch.id)),
      0,
      renderPageFileIds,
      batch.jianpu_text || '',
      batch.render_page_ocr_texts || [],
      batch.render_output_stale ?? false,
      batch.render_layout_key ?? '',
    )
    await nextTick()
    await validateRestoredBatchFiles(pages, renderPageFileIds)
    if (
      !renderPageFileIds.length
      || batch.engine_version !== PUBLICATION_ENGINE_VERSION
      || batch.render_output_stale
      || isRenderLayoutStale(batch.render_layout_key ?? '', settings.jianpuLayoutKey)
    ) {
      const outcome = await rebuildPublicationPages(batch)
      if (outcome !== 'completed') return true
    }
    message.success(t('runtime.history.restoredPages', { count: pages.length }))
    return true
  }

  async function rebuildPublicationPages(batch: HistoryBatch): Promise<RebuildOutcome> {
    const sourcePages = batch.pages.map((page) => {
      const split = splitJianpuAndOcr(page.jianpu_text || '')
      return {
        inputFileName: page.input_file_name,
        inputFileId: page.input_file_id,
        originalFileId: isPreviewableHistoryFile(page.input_file_name) ? page.input_file_id : '',
        musicxmlFileId: page.musicxml_file_id,
        jianpuText: split.jianpuText,
        ocrText: page.ocr_text || split.ocrText,
        sourceMapFileId: page.source_map_file_id || '',
        textAttachments: page.text_attachments || [],
      }
    })
    const requestPages = buildBatchRenderRequests(sourcePages, {
      jianpuText: batch.jianpu_text || '',
      title: t('runtime.history.scoreTitle'),
    })
    if (!requestPages.length) {
      log.addLog(t('runtime.history.missingMusicxmlOrText'), 'warn')
      return 'failed'
    }
    try {
      const rendered = await requireData(publicationRender.batchA4({
        pages: requestPages,
        source_pages: buildBatchRenderRequests(sourcePages, { title: t('runtime.history.scoreTitle') }),
        render_page_ocr_texts: batch.render_page_ocr_texts || [],
        target_key: settings.targetKey,
        accidental_mode: settings.accidentalMode,
        show_measure_numbers: settings.showMeasureNumbers,
        measure_number_mode: settings.measureNumberMode,
        initial_measure_number: 1,
        title: t('runtime.history.scoreTitle'),
        ...settings.jianpuLayoutRequest,
      }))
      const ids = renderResponsePageIds(rendered.pages, rendered.svg_file_id)
      const layoutKey = rendered.pages[0]?.layout_key || settings.jianpuLayoutKey
      store.setBatchRenderPageFileIds(ids, undefined, layoutKey)
      store.setBatchRenderPageOcrTexts(
        renderResponsePageOcrTexts(rendered.pages),
        false,
      )
      await requireData(historyApi.updateRenderState(batch.id, {
        render_page_file_ids: ids,
        render_page_ocr_texts: store.currentBatchRenderPageOcrTextEntries(),
        render_output_stale: false,
        render_layout_key: layoutKey,
      }))
      log.addLog(t('runtime.history.rebuiltPages', { count: ids.length }))
      return 'completed'
    } catch (error: unknown) {
      if (isRenderAborted(error)) return 'aborted'
      if (error instanceof ApiError && error.code === 'jianpu_syntax') {
        const msg = t('runtime.history.syntaxError')
        log.addError(msg)
        message.error(msg)
        return 'failed'
      }
      const detail = error instanceof Error ? error.message : String(error)
      log.addLog(t('runtime.history.rebuildFailed', { message: detail }), 'warn')
      message.warning(t('runtime.history.restoredNeedsRerender', { message: detail }))
      return 'failed'
    }
  }

  function buildTaskPageInput(page: HistoryPage, batchId: number) {
    const split = splitJianpuAndOcr(page.jianpu_text || '')
    const previewable = isPreviewableHistoryFile(page.input_file_name)
    const hasTextAnchorBaseline = page.text_anchor_baseline_text !== undefined
      && page.text_anchor_baseline_anchors !== undefined
    return {
      inputFileName: page.input_file_name,
      inputFileId: page.input_file_id,
      originalFileName: previewable ? page.input_file_name : '',
      originalFileId: previewable ? page.input_file_id : '',
      historyPageId: page.id,
      historyBatchId: batchId,
      musicxmlFileId: page.musicxml_file_id,
      jianpuText: split.jianpuText,
      ocrText: page.ocr_text || split.ocrText,
      svgFileId: page.svg_file_id,
      svgFileIds: page.svg_file_id ? [page.svg_file_id] : [],
      overlayFileId: page.overlay_file_id || page.overlay_svg_file_id || '',
      sourceMapFileId: page.source_map_file_id || '',
      textAnchors: page.text_anchors || [],
      textAnchorBaselineText: hasTextAnchorBaseline
        ? page.text_anchor_baseline_text
        : split.jianpuText,
      textAnchorBaselineAnchors: hasTextAnchorBaseline
        ? page.text_anchor_baseline_anchors
        : (page.text_anchors || []),
      textAttachments: page.text_attachments || [],
      textHash: page.text_hash || '',
      taskId: page.task_id || '',
      status: page.status as TaskPage['status'],
      errorMessage: page.error_message,
      omrFileId: page.omr_file_id || '',
      originalMusicxml: page.original_musicxml || '',
      workingMusicxml: page.working_musicxml || page.original_musicxml || '',
      deletedSourceIds: page.deleted_source_ids || [],
      recognitionCandidateSelections: page.recognition_candidate_selections || {},
      ...liveRecognitionTaskPatch(page.id, page.status),
    }
  }

  async function validateRestoredBatchFiles(
    pages: HistoryPage[],
    renderPageFileIds: string[] = [],
  ): Promise<void> {
    const seq = ++restoreCheckSeq
    const fileIds = pages
      .flatMap((page) => [
        page.input_file_id,
        page.musicxml_file_id,
        page.svg_file_id,
        page.omr_file_id || '',
        page.source_map_file_id || '',
      ])
      .concat(renderPageFileIds)
      .filter(Boolean)
    if (!fileIds.length) return
    try {
      const exists = await requireData(filesApi.existsMany(fileIds))
      if (seq !== restoreCheckSeq) return
      const warnings: string[] = []
      for (const page of pages) {
        const patch: Partial<TaskPage> = {}
        if (page.input_file_id && !exists[page.input_file_id]) {
          patch.inputFileId = ''
          patch.originalFileId = ''
          patch.originalFileName = ''
          warnings.push(`${page.input_file_name}: ${t('runtime.history.originalFileExpired')}`)
        }
        if (page.musicxml_file_id && !exists[page.musicxml_file_id]) {
          patch.musicxmlFileId = ''
          warnings.push(`${page.input_file_name}: ${t('runtime.history.musicxmlExpired')}`)
        }
        if (page.svg_file_id && !exists[page.svg_file_id]) {
          patch.svgFileId = ''
          patch.svgFileIds = []
          warnings.push(`${page.input_file_name}: ${t('runtime.history.svgExpired')}`)
        }
        if (page.omr_file_id && !exists[page.omr_file_id]) {
          patch.omrFileId = ''
          patch.deletedSourceIds = []
          warnings.push(`${page.input_file_name}: ${t('runtime.history.omrExpired')}`)
        }
        if (page.source_map_file_id && !exists[page.source_map_file_id]) {
          patch.sourceMapFileId = ''
          patch.deletedSourceIds = []
          warnings.push(`${page.input_file_name}: ${t('runtime.history.sourceMapExpired')}`)
        }
        if (Object.keys(patch).length) {
          store.patchPageByHistoryPageId(page.id, patch)
        }
      }
      const validRenderIds = renderPageFileIds.filter((fileId) => exists[fileId])
      if (validRenderIds.length !== renderPageFileIds.length) {
        store.setBatchRenderPageFileIds(validRenderIds)
        warnings.push(t('runtime.history.continuousA4Expired'))
      }
      if (warnings.length) {
        log.addLog(`${t('runtime.history.partialExpired')}${warnings.join(', ')}`, 'warn')
        message.warning(`${warnings.join('; ')}${t('runtime.history.rerecognizeOrReupload')}`)
      }
    } catch (e: unknown) {
      if (seq === restoreCheckSeq) {
        log.addLog(`${t('runtime.history.validateFailed')}${e instanceof Error ? e.message : String(e)}`, 'warn')
      }
    }
  }

  return { restoreBatch }
}
