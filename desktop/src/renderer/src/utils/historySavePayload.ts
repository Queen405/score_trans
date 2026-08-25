import type { TaskPage } from '../stores/workspace'
import type {
  HistoryBatchSaveRequest,
  HistoryCreateRequest,
  RenderPageOcrText,
} from '../models/types'
import { parseJianpuPageSections } from './jianpuPageSections'

export interface BatchPersistenceSnapshotInput {
  pages: TaskPage[]
  jianpuText: string
  renderPageFileIds: string[]
  renderPageOcrTexts: RenderPageOcrText[]
  renderOutputStale: boolean
  renderLayoutKey: string
  source: 'save' | 'reset'
}

export type BatchPersistenceSnapshot =
  | {
    kind: 'update'
    historyBatchId: number
    request: HistoryBatchSaveRequest
  }
  | {
    kind: 'create'
    request: HistoryCreateRequest
  }

function pageTextAt(text: string, pages: TaskPage[], index: number): string {
  const sections = parseJianpuPageSections(text)
  return sections.find((section) => section.pageIndex === index)?.body
    ?? sections[index]?.body
    ?? pages[index]?.jianpuText
    ?? ''
}

function renderState(input: BatchPersistenceSnapshotInput) {
  const renderPageFileIds = [...input.renderPageFileIds]
  return {
    render_page_file_ids: renderPageFileIds,
    render_page_ocr_texts: input.renderPageOcrTexts.map((item) => ({ ...item })),
    render_output_stale: input.renderOutputStale || renderPageFileIds.length === 0,
    render_layout_key: renderPageFileIds.length ? input.renderLayoutKey : '',
  }
}

export function buildBatchPersistenceSnapshot(
  input: BatchPersistenceSnapshotInput,
): BatchPersistenceSnapshot {
  if (!input.pages.length) throw new Error('Cannot save an empty batch')

  const hasAnyHistoryIdentity = input.pages.some(
    (page) => page.historyBatchId !== null || page.historyPageId !== null,
  )
  const hasCompleteHistoryIdentity = input.pages.every(
    (page) => page.historyBatchId !== null && page.historyPageId !== null,
  )
  const batchIds = new Set(
    input.pages
      .map((page) => page.historyBatchId)
      .filter((id): id is number => id !== null),
  )
  if (hasAnyHistoryIdentity && (!hasCompleteHistoryIdentity || batchIds.size !== 1)) {
    throw new Error('Batch pages have inconsistent history identity')
  }

  const commonRenderState = renderState(input)
  if (hasCompleteHistoryIdentity) {
    const historyBatchId = input.pages[0]!.historyBatchId!
    return {
      kind: 'update',
      historyBatchId,
      request: {
        jianpu_text: input.jianpuText,
        source: input.source,
        pages: input.pages.map((page, index) => ({
          page_id: page.historyPageId!,
          task_id: page.taskId,
          musicxml_file_id: page.musicxmlFileId,
          jianpu_text: pageTextAt(input.jianpuText, input.pages, index),
          ocr_text: page.ocrText,
          text_attachments: page.textAttachments,
          svg_file_id: page.svgFileId,
          overlay_file_id: page.overlayFileId,
          source_map_file_id: page.sourceMapFileId,
          text_hash: page.textHash,
          text_anchors: page.textAnchors,
          status: page.status,
          error_message: page.errorMessage,
          omr_file_id: page.omrFileId,
          original_musicxml: page.originalMusicxml,
          working_musicxml: page.workingMusicxml,
          deleted_source_ids: page.deletedSourceIds,
        })),
        ...commonRenderState,
      },
    }
  }

  return {
    kind: 'create',
    request: {
      jianpu_text: input.jianpuText,
      pages: input.pages.map((page, index) => ({
        input_file_name: page.inputFileName,
        input_file_id: page.inputFileId,
        task_id: page.taskId,
        musicxml_file_id: page.musicxmlFileId,
        jianpu_text: pageTextAt(input.jianpuText, input.pages, index),
        ocr_text: page.ocrText,
        text_attachments: page.textAttachments,
        svg_file_id: page.svgFileId,
        overlay_file_id: page.overlayFileId,
        source_map_file_id: page.sourceMapFileId,
        text_hash: page.textHash,
        text_anchors: page.textAnchors,
        status: page.status,
        error_message: page.errorMessage,
        omr_file_id: page.omrFileId,
        original_musicxml: page.originalMusicxml,
        working_musicxml: page.workingMusicxml,
        deleted_source_ids: page.deletedSourceIds,
      })),
      ...commonRenderState,
    },
  }
}
