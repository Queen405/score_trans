import { useMessage } from 'naive-ui'
import { useWorkspaceStore } from '../stores/workspace'
import { useLogStore } from '../stores/log'
import { historyApi } from '../api/history'
import { filesApi } from '../api/files'
import { requireData } from '../api/client'
import { splitJianpuAndOcr } from '../utils/ocrText'
import {
  isPreviewableHistoryFile,
  parseWaitingMeasureOptions,
} from '../utils/historyPageState'
import { liveRecognitionTaskPatch } from '../utils/liveRecognitionState'
import type { HistoryBatch, HistoryBatchListItem, HistoryPage } from '../models/types'
import type { TaskPage } from '../stores/workspace'

export function useHistoryRestore() {
  const message = useMessage()
  const store = useWorkspaceStore()
  const log = useLogStore()
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
    store.loadBatch(
      pages.map((page) => buildTaskPageInput(page, batch.id)),
      0,
      batch.render_page_file_ids,
      batch.jianpu_text || '',
      batch.render_page_ocr_texts || [],
    )
    await validateRestoredBatchFiles(pages, batch.render_page_file_ids)
    message.success(`已恢复 ${pages.length} 页`)
    return true
  }

  function buildTaskPageInput(page: HistoryPage, batchId: number) {
    const split = splitJianpuAndOcr(page.jianpu_text || '')
    const previewable = isPreviewableHistoryFile(page.input_file_name)
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
      taskId: page.task_id || '',
      startMeasureNumber: page.start_measure_number ?? null,
      status: page.status as TaskPage['status'],
      measureNumberOptions: parseWaitingMeasureOptions(page.error_message),
      errorMessage: page.error_message,
      ...liveRecognitionTaskPatch(page.id, page.status),
    }
  }

  async function validateRestoredBatchFiles(
    pages: HistoryPage[],
    renderPageFileIds: string[] = [],
  ): Promise<void> {
    const seq = ++restoreCheckSeq
    const fileIds = pages
      .flatMap((page) => [page.input_file_id, page.musicxml_file_id, page.svg_file_id])
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
