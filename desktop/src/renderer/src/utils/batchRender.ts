import type {
  BatchRenderPageRequest,
  RenderedSvgPage,
  RenderPageOcrText,
  SourceTextAttachment,
} from '../models/types'
import { parseJianpuPageSections } from './jianpuPageSections'

export interface BatchRenderSourcePage {
  inputFileName: string
  inputFileId: string
  originalFileId: string
  musicxmlFileId: string
  jianpuText: string
  ocrText: string
  sourceMapFileId: string
  textAttachments: SourceTextAttachment[]
  startMeasureNumber: number | null
}

export interface BatchRenderBuildOptions {
  jianpuText?: string
  title?: string
  combineJianpuText?: boolean
}

export function buildBatchRenderRequests(
  pages: BatchRenderSourcePage[],
  options: BatchRenderBuildOptions = {},
): BatchRenderPageRequest[] {
  const text = options.jianpuText?.trim() ? options.jianpuText : ''
  if (!text) return buildSourcePageRenderRequests(pages, options.title)

  if (options.combineJianpuText) {
    return [
      compactRequest({
        jianpu_text: text,
        include_ocr_text: false,
        start_measure_number: pages[0]?.startMeasureNumber ?? undefined,
        title: options.title,
      }),
    ]
  }

  return parseJianpuPageSections(text)
    .map((section, order) => {
      const page = pages[section.pageIndex] ?? pages[order]
      const sourceImageId = page?.originalFileId || page?.inputFileId || undefined
      const start = section.startMeasureNumber
        ?? (!section.markerLine && order === 0
          ? (page?.startMeasureNumber ?? undefined)
          : undefined)
      if (section.body.trim()) {
        return compactRequest({
          input_file_name: section.inputFileName || page?.inputFileName,
          jianpu_text: section.body,
          page_image_file_id: sourceImageId,
          source_map_file_id: page?.sourceMapFileId || undefined,
          ocr_text: page?.ocrText || undefined,
          text_attachments: page?.textAttachments ?? [],
          include_ocr_text: false,
          start_measure_number: start,
          title: options.title,
        })
      }
      if (page?.musicxmlFileId) {
        return compactRequest({
          input_file_name: section.inputFileName || page.inputFileName,
          musicxml_file_id: page.musicxmlFileId,
          page_image_file_id: sourceImageId,
          source_map_file_id: page.sourceMapFileId || undefined,
          ocr_text: page.ocrText || undefined,
          text_attachments: page.textAttachments,
          include_ocr_text: false,
          start_measure_number: start,
          title: options.title,
        })
      }
      return null
    })
    .filter((page): page is BatchRenderPageRequest => page !== null)
}

export function buildSourcePageRenderRequests(
  pages: BatchRenderSourcePage[],
  title?: string,
): BatchRenderPageRequest[] {
  return pages
    .map((page) => {
      const sourceImageId = page.originalFileId || page.inputFileId || undefined
      const common = {
        input_file_name: page.inputFileName,
        page_image_file_id: sourceImageId,
        source_map_file_id: page.sourceMapFileId || undefined,
        ocr_text: page.ocrText || undefined,
        text_attachments: page.textAttachments,
        include_ocr_text: false,
        start_measure_number: page.startMeasureNumber ?? undefined,
        title,
      }
      if (page.jianpuText.trim()) {
        return compactRequest({ ...common, jianpu_text: page.jianpuText })
      }
      if (page.musicxmlFileId) {
        return compactRequest({ ...common, musicxml_file_id: page.musicxmlFileId })
      }
      return null
    })
    .filter((page): page is BatchRenderPageRequest => page !== null)
}

export function renderResponsePageIds(
  pages: RenderedSvgPage[] | null | undefined,
  fallback: string,
): string[] {
  const ids = (pages ?? []).map((page) => page.svg_file_id).filter(Boolean)
  return ids.length ? ids : (fallback ? [fallback] : [])
}

export function renderResponsePageOcrTexts(
  pages: RenderedSvgPage[] | null | undefined,
): RenderPageOcrText[] {
  return (pages ?? []).map((page) => ({
    page_index: page.page_index,
    ocr_text: page.ocr_text || '',
  }))
}

export function renderPageOcrTextsForRequest(
  entries: RenderPageOcrText[],
  dirty: boolean,
): RenderPageOcrText[] {
  return dirty ? entries : entries.filter((item) => item.ocr_text.trim())
}

function compactRequest(request: BatchRenderPageRequest): BatchRenderPageRequest {
  return Object.fromEntries(
    Object.entries(request).filter(([, value]) => value !== undefined),
  ) as BatchRenderPageRequest
}
