export interface JianpuPageSource {
  inputFileName?: string
  jianpuText?: string
}

export interface JianpuPageSection {
  pageIndex: number
  inputFileName: string
  body: string
  markerLine: string
  markerLineIndex: number
}

export interface JianpuPageSummary {
  pageIndex: number
  pageNumber: number
  inputFileName: string
  firstMeasureNumber: number
  lastMeasureNumber: number | null
  measureCount: number
  markerLineIndex: number
}

interface JianpuPageMarker {
  pageNumber: number
  inputFileName: string
}

const PAGE_MARKER_PATTERN = /^\s*\/\/\s*@page\s+(\d+)(?:\s+name=("(?:\\.|[^"\\])*"))?\s*$/
const PAGE_MARKER_PREFIX_PATTERN = /^\s*\/\/\s*@page\b/
const PART_MARKER_PATTERN = /^\s*\/\/\s*@part\s+\d+\s+name="(?:\\.|[^"\\])*"\s*$/

function normalizeLineEndings(text: string): string {
  return text.replace(/\r\n?/g, '\n')
}

function parseMarkerName(rawName: string | undefined): string {
  if (!rawName) return ''
  const value = rawName.trim()
  if (!value.startsWith('"')) return value
  try {
    const parsed = JSON.parse(value)
    return typeof parsed === 'string' ? parsed : value
  } catch {
    return value.slice(1, value.endsWith('"') ? -1 : undefined)
  }
}

export function parseJianpuPageMarker(line: string): JianpuPageMarker | null {
  const match = line.match(PAGE_MARKER_PATTERN)
  if (!match) {
    if (PAGE_MARKER_PREFIX_PATTERN.test(line)) {
      throw new Error(`无效的分页标记：${line.trim()}`)
    }
    return null
  }
  const pageNumber = Number(match[1])
  if (!Number.isInteger(pageNumber) || pageNumber < 1) {
    throw new Error(`无效的分页序号：${match[1]}`)
  }
  return {
    pageNumber,
    inputFileName: parseMarkerName(match[2]),
  }
}

export function formatJianpuPageMarker(
  pageNumber: number,
  inputFileName = '',
): string {
  const name = inputFileName ? ` name=${JSON.stringify(inputFileName)}` : ''
  return `// @page ${pageNumber}${name}`
}

export function hasJianpuPageMarkers(text: string): boolean {
  return normalizeLineEndings(text).split('\n').some((line) => parseJianpuPageMarker(line) !== null)
}

export function parseJianpuPageSections(text: string): JianpuPageSection[] {
  const normalized = normalizeLineEndings(text)
  const lines = normalized.split('\n')
  const markers = lines.flatMap((line, lineIndex) => {
    const marker = parseJianpuPageMarker(line)
    return marker ? [{ marker, line, lineIndex }] : []
  })

  if (!markers.length) {
    return [{
      pageIndex: 0,
      inputFileName: '',
      body: normalized,
      markerLine: '',
      markerLineIndex: -1,
    }]
  }

  return markers.map(({ marker, line, lineIndex }, index) => {
    const nextLineIndex = markers[index + 1]?.lineIndex ?? lines.length
    let body = lines.slice(lineIndex + 1, nextLineIndex).join('\n')
    if (index === 0 && lineIndex > 0) {
      const prefix = lines.slice(0, lineIndex).join('\n')
      body = body ? `${prefix}\n${body}` : prefix
    }
    return {
      pageIndex: marker.pageNumber - 1,
      inputFileName: marker.inputFileName,
      body,
      markerLine: line,
      markerLineIndex: lineIndex,
    }
  })
}

export function serializeJianpuPageSections(sections: JianpuPageSection[]): string {
  return sections
    .map((section, order) => {
      const pageNumber = section.pageIndex >= 0 ? section.pageIndex + 1 : order + 1
      const marker = formatJianpuPageMarker(pageNumber, section.inputFileName)
      return section.body ? `${marker}\n${normalizeLineEndings(section.body)}` : marker
    })
    .join('\n')
}

export function composeJianpuPageText(pages: JianpuPageSource[]): string {
  return serializeJianpuPageSections(pages.map((page, pageIndex) => ({
    pageIndex,
    inputFileName: page.inputFileName ?? '',
    body: normalizeLineEndings(page.jianpuText ?? ''),
    markerLine: '',
    markerLineIndex: -1,
  })))
}

export function migrateLegacyJianpuPageText(
  batchText: string,
  pages: JianpuPageSource[],
): string {
  if (hasJianpuPageMarkers(batchText)) return normalizeLineEndings(batchText)
  if (!pages.length) return normalizeLineEndings(batchText)

  const normalizedBatchText = normalizeLineEndings(batchText)
  if (!normalizedBatchText.trim()) return composeJianpuPageText(pages)

  const legacyMergedText = pages
    .map((page) => normalizeLineEndings(page.jianpuText ?? '').trim())
    .filter(Boolean)
    .join('\n\n')
  if (legacyMergedText === normalizedBatchText.trim()) {
    return composeJianpuPageText(pages)
  }

  return composeJianpuPageText(pages.map((page, pageIndex) => ({
    ...page,
    jianpuText: pageIndex === 0 ? normalizedBatchText : '',
  })))
}

export function restoreJianpuPageText(
  batchText: string,
  pages: JianpuPageSource[],
): string {
  const migrated = migrateLegacyJianpuPageText(batchText, pages)
  if (!pages.some((page) => page.jianpuText?.trim())) return migrated

  const sections = parseJianpuPageSections(migrated)
  if (sections.length && sections.every((section) => !section.body.trim())) {
    return composeJianpuPageText(pages)
  }
  return migrated
}

export function replaceJianpuSectionBody(
  text: string,
  pageIndex: number,
  body: string,
  source: JianpuPageSource = {},
): string {
  const sections = parseJianpuPageSections(text)
  const section = sections.find((item) => item.pageIndex === pageIndex) ?? sections[pageIndex]
  if (section) {
    section.pageIndex = pageIndex
    section.body = normalizeLineEndings(body)
    if (!section.inputFileName) section.inputFileName = source.inputFileName ?? ''
    return serializeJianpuPageSections(sections)
  }

  sections.push({
    pageIndex,
    inputFileName: source.inputFileName ?? '',
    body: normalizeLineEndings(body),
    markerLine: '',
    markerLineIndex: -1,
  })
  sections.sort((left, right) => left.pageIndex - right.pageIndex)
  return serializeJianpuPageSections(sections)
}

export function removeJianpuPageSection(text: string, pageIndex: number): string {
  if (!hasJianpuPageMarkers(text)) return pageIndex === 0 ? '' : text
  const sections = parseJianpuPageSections(text)
  const removeIndex = sections.findIndex((section) => section.pageIndex === pageIndex)
  const resolvedIndex = removeIndex >= 0 ? removeIndex : pageIndex
  if (resolvedIndex < 0 || resolvedIndex >= sections.length) return text
  sections.splice(resolvedIndex, 1)
  sections.forEach((section, index) => {
    section.pageIndex = index
  })
  return serializeJianpuPageSections(sections)
}

function splitInlineComment(line: string): string {
  const commentStart = line.indexOf('//')
  return commentStart < 0 ? line : line.slice(0, commentStart)
}

export function jianpuMeasureCount(text: string): number {
  const partCounts: number[] = []
  let currentPartCount = 0
  let hasPartMarkers = false
  for (const line of normalizeLineEndings(text).split('\n')) {
    if (PART_MARKER_PATTERN.test(line)) {
      if (hasPartMarkers) partCounts.push(currentPartCount)
      hasPartMarkers = true
      currentPartCount = 0
      continue
    }
    const code = splitInlineComment(line).trim()
    if (!code.includes('|')) continue
    const withoutBar = code.replace(/\|$/, '').trim()
    const repeatMatch = withoutBar.match(/\*\s*(\d+)$/)
    currentPartCount += repeatMatch ? Number(repeatMatch[1]) : 1
  }
  if (!hasPartMarkers) return currentPartCount
  partCounts.push(currentPartCount)
  return Math.max(0, ...partCounts)
}

export function jianpuPageSummaries(text: string): JianpuPageSummary[] {
  const sections = parseJianpuPageSections(text)
  let nextMeasureNumber = 1
  return sections.map((section, order) => {
    const firstMeasureNumber = nextMeasureNumber
    const measureCount = jianpuMeasureCount(section.body)
    const lastMeasureNumber = measureCount ? firstMeasureNumber + measureCount - 1 : null
    nextMeasureNumber = firstMeasureNumber + measureCount
    return {
      pageIndex: section.pageIndex,
      pageNumber: section.pageIndex >= 0 ? section.pageIndex + 1 : order + 1,
      inputFileName: section.inputFileName,
      firstMeasureNumber,
      lastMeasureNumber,
      measureCount,
      markerLineIndex: section.markerLineIndex,
    }
  })
}

export function jianpuGutterLabels(text: string): string[] {
  const normalized = normalizeLineEndings(text)
  const summaries = jianpuPageSummaries(normalized)
  let pageOrder = -1
  let pageStartMeasureNumber = 1
  let measureNumber = pageStartMeasureNumber
  return normalized.split('\n').map((line) => {
    const marker = parseJianpuPageMarker(line)
    if (marker) {
      pageOrder += 1
      pageStartMeasureNumber = summaries[pageOrder]?.firstMeasureNumber ?? measureNumber
      measureNumber = pageStartMeasureNumber
      return `P${marker.pageNumber}`
    }
    if (PART_MARKER_PATTERN.test(line)) {
      measureNumber = pageStartMeasureNumber
      return ''
    }

    const code = splitInlineComment(line).trim()
    if (!code.includes('|')) return ''
    const currentNumber = measureNumber
    const withoutBar = code.replace(/\|$/, '').trim()
    const repeatMatch = withoutBar.match(/\*\s*(\d+)$/)
    measureNumber += repeatMatch ? Number(repeatMatch[1]) : 1
    return String(currentNumber)
  })
}
