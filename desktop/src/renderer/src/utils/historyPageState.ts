import type { HistoryPage } from '../models/types'
import type { HistoryPagePatchDetail } from './historyEvents'

export type HistoryPageOpenAction = 'choose' | 'restore' | 'wait'

export function historyPageOpenAction(status: string): HistoryPageOpenAction {
  if (status === 'waiting') return 'choose'
  if (status === 'processing' || status === 'pending') return 'wait'
  return 'restore'
}

export function historyPagePatchFromPage(page: HistoryPage): HistoryPagePatchDetail {
  return {
    id: page.id,
    patch: {
      task_id: page.task_id,
      musicxml_file_id: page.musicxml_file_id,
      jianpu_text: page.jianpu_text,
      ocr_text: page.ocr_text,
      svg_file_id: page.svg_file_id,
      start_measure_number: page.start_measure_number,
      status: page.status,
      error_message: page.error_message,
    },
  }
}

export function isPreviewableHistoryFile(fileName: string): boolean {
  return /\.(pdf|png|jpe?g|tiff?|webp)$/i.test(fileName)
}

export function waitingMeasureMessage(options: number[]): string {
  return `等待选择起始小节号：${options.join('、')}`
}

export function failedMeasureSelectionMessage(
  options: number[],
  message: string,
): string {
  const prefix = options.length ? `${waitingMeasureMessage(options)}；` : ''
  return `${prefix}选择小节号失败：${message}`
}

export function parseWaitingMeasureOptions(message: string): number[] {
  const match = message.match(/等待选择起始小节号[:：]\s*([0-9\s、,，]+)/)
  if (!match) return []
  const optionsText = match[1] ?? ''
  return Array.from(optionsText.matchAll(/\d+/g), (valueMatch) => Number(valueMatch[0]))
    .filter((value) => Number.isFinite(value) && value > 0)
}
