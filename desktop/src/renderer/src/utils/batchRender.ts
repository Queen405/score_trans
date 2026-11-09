import type {
  BatchRenderPageRequest,
  RenderedSvgPage,
  RenderPageOcrText,
  SourceTextAttachment,
  TextAnchor,
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
  textAnchors?: TextAnchor[]
}

export interface BatchRenderBuildOptions {
  jianpuText?: string
  title?: string
  // Passed to text parsing only; never override the document with this label.
  fallbackTitle?: string
  combineJianpuText?: boolean
}

export function buildBatchRenderRequests(
  pages: BatchRenderSourcePage[],
  options: BatchRenderBuildOptions = {},
): BatchRenderPageRequest[] {
  const text = options.jianpuText?.trim() ? options.jianpuText : ''
  if (!text) return buildSourcePageRenderRequests(pages, options.title, options.fallbackTitle)

  if (options.combineJianpuText) {
    return [
      compactRequest({
        jianpu_text: text,
        include_ocr_text: false,
        title: options.title || pages.map((page) => sourceTitle(page)).find(Boolean) || options.fallbackTitle,
      }),
    ]
  }

  return parseJianpuPageSections(text)
    .map((section, order) => {
      const page = pages[section.pageIndex] ?? pages[order]
      const sourcePageIndex = pages[section.pageIndex] ? section.pageIndex : order
      const sourceImageId = page?.originalFileId || page?.inputFileId || undefined
      if (section.body.trim()) {
        return compactRequest({
          input_file_name: section.inputFileName || page?.inputFileName,
          jianpu_text: section.body,
          page_image_file_id: sourceImageId,
          source_map_file_id: page?.sourceMapFileId || undefined,
          source_page_index: sourcePageIndex,
          ocr_text: page?.ocrText || undefined,
          text_attachments: page?.textAttachments ?? [],
          text_anchors: page?.textAnchors ?? [],
          include_ocr_text: false,
          title: options.title || sourceTitle(page) || options.fallbackTitle,
        })
      }
      if (page?.musicxmlFileId) {
        return compactRequest({
          input_file_name: section.inputFileName || page.inputFileName,
          musicxml_file_id: page.musicxmlFileId,
          page_image_file_id: sourceImageId,
          source_map_file_id: page.sourceMapFileId || undefined,
          source_page_index: sourcePageIndex,
          ocr_text: page.ocrText || undefined,
          text_attachments: page.textAttachments,
          text_anchors: page.textAnchors ?? [],
          include_ocr_text: false,
          title: options.title || sourceTitle(page),
        })
      }
      return null
    })
    .filter((page): page is BatchRenderPageRequest => page !== null)
}

export function buildSourcePageRenderRequests(
  pages: BatchRenderSourcePage[],
  title?: string,
  fallbackTitle?: string,
): BatchRenderPageRequest[] {
  return pages
    .map((page, sourcePageIndex) => {
      const sourceImageId = page.originalFileId || page.inputFileId || undefined
      const common = {
        input_file_name: page.inputFileName,
        page_image_file_id: sourceImageId,
        source_map_file_id: page.sourceMapFileId || undefined,
        source_page_index: sourcePageIndex,
        ocr_text: page.ocrText || undefined,
        text_attachments: page.textAttachments,
        text_anchors: page.textAnchors ?? [],
        include_ocr_text: false,
        title: title || sourceTitle(page),
      }
      if (page.jianpuText.trim()) {
        return compactRequest({
          ...common,
          title: common.title || fallbackTitle,
          jianpu_text: page.jianpuText,
        })
      }
      if (page.musicxmlFileId) {
        return compactRequest({ ...common, musicxml_file_id: page.musicxmlFileId })
      }
      return null
    })
    .filter((page): page is BatchRenderPageRequest => page !== null)
}

function sourceTitle(page: BatchRenderSourcePage | undefined): string | undefined {
  return page?.textAttachments?.find((item) => item.role === 'title' && item.text.trim())?.text.trim()
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
