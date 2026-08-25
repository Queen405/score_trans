import { useMessage } from 'naive-ui'
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
import {
  isRenderLayoutStale,
  PUBLICATION_ENGINE_VERSION,
} from '../utils/jianpuLayout'

type RebuildOutcome = 'completed' | 'aborted' | 'failed'

export function useHistoryRestore() {
  const message = useMessage()
  const store = useWorkspaceStore()
  const settings = useSettingsStore()
  const log = useLogStore()
  const publicationRender = usePublicationRender()
  let restoreCheckSeq = 0

  async function restoreBatch(entry: HistoryBatchListItem): Promise<boolean> {
    if (store.isBusy) {
      message.warning('识别任务进行中，完成后再恢复历史记录。')
      return false
    }

    let batch: HistoryBatch
    try {
      batch = await requireData(historyApi.get(entry.id))
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e)
      log.addError(`加载历史详情失败：${msg}`)
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
    message.success(`已恢复 ${pages.length} 页`)
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
      title: '简谱',
    })
    if (!requestPages.length) {
      log.addLog('历史记录缺少 MusicXML 或简谱文本，无法用新版渲染器重建。', 'warn')
      return 'failed'
    }
    try {
      const rendered = await requireData(publicationRender.batchA4({
        pages: requestPages,
        source_pages: buildBatchRenderRequests(sourcePages, { title: '简谱' }),
        render_page_ocr_texts: batch.render_page_ocr_texts || [],
        target_key: settings.targetKey,
        accidental_mode: settings.accidentalMode,
        show_measure_numbers: settings.showMeasureNumbers,
        measure_number_mode: settings.measureNumberMode,
        initial_measure_number: 1,
        title: '简谱',
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
      log.addLog(`历史记录已由新版出版渲染器重建，共 ${ids.length} 页。`)
      return 'completed'
    } catch (error: unknown) {
      if (isRenderAborted(error)) return 'aborted'
      if (error instanceof ApiError && error.code === 'jianpu_syntax') {
        const msg = '历史记录存在语法错误，无法重新渲染，请先修复'
        log.addError(msg)
        message.error(msg)
        return 'failed'
      }
      const detail = error instanceof Error ? error.message : String(error)
      log.addLog(`历史谱面重建失败：${detail}`, 'warn')
      message.warning(`历史数据已恢复，但谱面需要重新渲染：${detail}`)
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
          warnings.push(`${page.input_file_name}：原始文件已失效`)
        }
        if (page.musicxml_file_id && !exists[page.musicxml_file_id]) {
          patch.musicxmlFileId = ''
          warnings.push(`${page.input_file_name}：MusicXML 已失效`)
        }
        if (page.svg_file_id && !exists[page.svg_file_id]) {
          patch.svgFileId = ''
          patch.svgFileIds = []
          warnings.push(`${page.input_file_name}：SVG 已失效`)
        }
        if (page.omr_file_id && !exists[page.omr_file_id]) {
          patch.omrFileId = ''
          patch.deletedSourceIds = []
          warnings.push(`${page.input_file_name}：OMR 工程文件已失效`)
        }
        if (page.source_map_file_id && !exists[page.source_map_file_id]) {
          patch.sourceMapFileId = ''
          patch.deletedSourceIds = []
          warnings.push(`${page.input_file_name}：来源映射已失效`)
        }
        if (Object.keys(patch).length) {
          store.patchPageByHistoryPageId(page.id, patch)
        }
      }
      const validRenderIds = renderPageFileIds.filter((fileId) => exists[fileId])
      if (validRenderIds.length !== renderPageFileIds.length) {
        store.setBatchRenderPageFileIds(validRenderIds)
        warnings.push('连续 A4 渲染页部分失效')
      }
      if (warnings.length) {
        log.addLog(`历史恢复部分失效：${warnings.join('，')}`, 'warn')
        message.warning(`${warnings.join('；')}，请重新识别或重新上传。`)
      }
    } catch (e: unknown) {
      if (seq === restoreCheckSeq) {
        log.addLog(`校验历史文件失败：${e instanceof Error ? e.message : String(e)}`, 'warn')
      }
    }
  }

  return { restoreBatch }
}
