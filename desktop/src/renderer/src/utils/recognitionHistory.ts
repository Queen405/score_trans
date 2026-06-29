export type RecognitionHistoryStatus =
  | 'pending'
  | 'processing'
  | 'waiting'
  | 'completed'
  | 'failed'
  | 'unrecognized'

export interface RecognitionHistoryPageSource {
  id: string
  inputFileName: string
  inputFileId: string
  originalFileId?: string
  musicxmlFileId?: string
  jianpuText?: string
  ocrText?: string
  svgFileId?: string
  startMeasureNumber?: number | null
}

export interface HistoryPageCreateSnapshot {
  input_file_name: string
  input_file_id: string
  musicxml_file_id: string
  jianpu_text: string
  ocr_text: string
  svg_file_id: string
  start_measure_number: number | null
  status: RecognitionHistoryStatus
  error_message: string
}

export interface HistoryBatchSnapshot {
  pageIds: string[]
  pages: HistoryPageCreateSnapshot[]
}

export function buildHistoryBatchSnapshot(
  pages: RecognitionHistoryPageSource[],
  selectedPageIds: ReadonlySet<string>,
): HistoryBatchSnapshot {
  return {
    pageIds: pages.map((page) => page.id),
    pages: pages.map((page) => ({
      input_file_name: page.inputFileName,
      input_file_id: page.originalFileId || page.inputFileId,
      musicxml_file_id: page.musicxmlFileId ?? '',
      jianpu_text: page.jianpuText ?? '',
      ocr_text: page.ocrText ?? '',
      svg_file_id: page.svgFileId ?? '',
      start_measure_number: page.startMeasureNumber ?? null,
      status: selectedPageIds.has(page.id) ? 'processing' : 'unrecognized',
      error_message: '',
    })),
  }
}

export function isRecognitionBatchReadyForRender(statuses: readonly string[]): boolean {
  return statuses.includes('completed')
    && statuses.every((status) => status === 'completed' || status === 'unrecognized')
}
