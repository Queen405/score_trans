import { lyricBlockLineIndexes } from './jianpuSyntax'

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
const STRUCTURE_MARKER_COMMENT_PATTERN = /^(\ufeff?[ \t]*\/\/[ \t]*)@(?=(?:page|part)\b)/gm

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

function tryParseJianpuPageMarker(line: string): JianpuPageMarker | null {
  try {
    return parseJianpuPageMarker(line)
  } catch {
    return null
  }
}

export function isJianpuPageMarker(line: string): boolean {
  return tryParseJianpuPageMarker(line) !== null
}

/**
 * Keep page/part-looking comments inert without changing any UTF-16 offsets.
 * The raw editor text remains untouched; only semantic analysis and requests use this copy.
 */
export function maskJianpuStructureMarkers(text: string): string {
  return text.replace(
    STRUCTURE_MARKER_COMMENT_PATTERN,
    (_match, prefix: string) => `${prefix} `,
  )
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

export function hasLiveJianpuPageMarkers(text: string): boolean {
  return normalizeLineEndings(text).split('\n').some(isJianpuPageMarker)
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

/** Return a page body's UTF-16 start offset in the original text. */
export function jianpuPageSectionBodyOffset(
  text: string,
  sections: JianpuPageSection[],
  sectionOrder: number,
): number {
  const section = sections[sectionOrder]
  if (!section || section.markerLineIndex < 0) return 0
  // The first section owns any prefix before the first page marker.
  if (sectionOrder === 0 && section.markerLineIndex > 0) return 0
  let offset = 0
  let line = 0
  while (line < section.markerLineIndex && offset < text.length) {
    if (text[offset] === '\r') {
      offset += text[offset + 1] === '\n' ? 2 : 1
      line += 1
    } else if (text[offset] === '\n') {
      offset += 1
      line += 1
    } else {
      offset += 1
    }
  }
  while (offset < text.length && text[offset] !== '\r' && text[offset] !== '\n') {
    offset += 1
  }
  if (text[offset] === '\r') return offset + (text[offset + 1] === '\n' ? 2 : 1)
  if (text[offset] === '\n') return offset + 1
  return offset
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

const INITIAL_TEMPO_PATTERN = /^tempo\s*=\s*\d+(?:\s|$)/i
const HEADER_LINE_PATTERN = /^(?:title|instrument|key|time)\s*=/i

export function ensureRecognizedTempoHeader(text: string): string {
  const normalized = normalizeLineEndings(text)
  const lines = normalized.split('\n')
  for (const rawLine of lines) {
    const trimmed = splitInlineComment(rawLine).trim()
    if (
      !trimmed
      || trimmed.startsWith('//')
      || trimmed.startsWith('/L:')
      || trimmed.startsWith('L:')
      || trimmed.startsWith('@text ')
      || HEADER_LINE_PATTERN.test(trimmed)
      || KEY_TOKEN_PATTERN.test(trimmed)
      || TIME_TOKEN_PATTERN.test(trimmed)
    ) continue
    if (INITIAL_TEMPO_PATTERN.test(trimmed)) return normalized
    break
  }
  const firstPartIndex = lines.findIndex((line) => PART_MARKER_PATTERN.test(line))
  if (firstPartIndex >= 0) {
    lines.splice(firstPartIndex + 1, 0, 'tempo=120')
    return lines.join('\n')
  }
  return normalized ? `tempo=120\n${normalized}` : 'tempo=120'
}

export function ensureRecognizedPageTempoHeader(text: string, pageIndex: number): string {
  const normalized = normalizeLineEndings(text)
  return pageIndex === 0 ? ensureRecognizedTempoHeader(normalized) : normalized
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

/**
 * 小节线切词：与后端 `_read_new_syntax` 的核心正则同构（`jianpu_text.py`）。
 * 刻意不含 `\s+` 分支——`jianpuSyntax.ts` 的 TOKEN_PATTERN 为高亮保留了空白 token，
 * 复用它会把每个空格当成小节内容。
 */
const MEASURE_TOKEN_PATTERN = /\$[^$]*\$|\|\||\|:|:\||\||&|[^\s|&]+/g
const REPEAT_TOKEN_PATTERN = /^\*(\d+)$/
const MEASURE_LABEL_TOKEN_PATTERN = /^(\d+)([.:：])$/
const LEADING_MEASURE_LABEL_PATTERN = /^\s*(\d+)([.:：])(?=\s|$)/
const KEY_TOKEN_PATTERN = /^1\s*=\s*[A-G](?:#|b)?$/
const TIME_TOKEN_PATTERN = /^\d+\/\d+$/
const METADATA_LINE_PATTERN = /^(?:title|instrument|key|time)\s*=/i
const TEMPO_LINE_PATTERN = /^tempo\s*=\s*[^\s|]+\s*$/i
const TEMPO_TOKEN_PATTERN = /^tempo\s*=\s*[^\s|]+$/i
// 4 字符可容纳 "1-3"、"10-"；gutter 宽度见 JianpuEditor（44px），更长截断为 n+。
const MAX_GUTTER_LABEL_LENGTH = 4

function isMeasureLabelToken(token: string): boolean {
  const match = MEASURE_LABEL_TOKEN_PATTERN.exec(token)
  if (!match) return false
  return match[2] !== '.' || Number(match[1]) > 7
}

/** 与后端 `_strip_leading_measure_label` 对齐：剥离 AI 输出的行首小节号（`272:`、`10.`）。 */
function stripLeadingMeasureLabel(line: string): string {
  const match = LEADING_MEASURE_LABEL_PATTERN.exec(line)
  if (!match) return line
  if (match[2] === '.' && Number(match[1]) <= 7) return line
  return line.slice(match[0].length)
}

function isNonMeasureLine(trimmed: string): boolean {
  if (!trimmed || trimmed.startsWith('/L:') || trimmed.startsWith('L:')) return true
  if (METADATA_LINE_PATTERN.test(trimmed) || TEMPO_LINE_PATTERN.test(trimmed)) return true
  return KEY_TOKEN_PATTERN.test(trimmed) || TIME_TOKEN_PATTERN.test(trimmed)
}

interface MeasureWalkLine {
  firstMeasure: number | null
  lastMeasure: number | null
}

interface MeasureWalkPage {
  pageIndex: number
  pageNumber: number
  inputFileName: string
  firstMeasureNumber: number
  measureCount: number
  markerLineIndex: number
}

interface MeasureWalkResult {
  lines: MeasureWalkLine[]
  pages: MeasureWalkPage[]
}

/**
 * 按后端解析语义走一遍全文，同时产出「每行承载的小节号区间」与「每页小节数」。
 *
 * 计数真值来自后端 `parse_jianpu_score` 的 flush 逻辑 + 渲染器
 * `_assign_score_measure_numbers`：一个小节对象占 `repeat_count` 个号，
 * 小节线才是边界，换行不是。
 */
function walkJianpuMeasures(
  text: string,
  initialMeasureNumber = 1,
): MeasureWalkResult {
  const normalized = normalizeLineEndings(text)
  const lines = normalized.split('\n')
  const lyricLines = lyricBlockLineIndexes(normalized)
  const lineResults: MeasureWalkLine[] = lines.map(() => ({
    firstMeasure: null,
    lastMeasure: null,
  }))

  const markerLines = lines.flatMap((line, lineIndex) => {
    const marker = tryParseJianpuPageMarker(line)
    return marker
      ? [{ lineIndex, pageNumber: marker.pageNumber, inputFileName: marker.inputFileName }]
      : []
  })
  // 无分页标记时整段视为第 1 页；有标记时，首个标记之前的前缀仍归第 1 页。
  const pagePlan = markerLines.length
    ? markerLines
    : [{ lineIndex: -1, pageNumber: 1, inputFileName: '' }]

  const pages: MeasureWalkPage[] = []
  let pageStart = Math.max(1, Math.trunc(initialMeasureNumber))
  let planIndex = -1
  let partCounts: number[] = []

  let measureNumber = pageStart
  let partAdvance = 0
  let hasContent = false
  let pendingRepeat = 1
  let skipEmpty = false
  let afterRepeatStart = false
  let repeatAppliedBackward = false
  let lastAdvance = 0
  let lastMeasureStart = 0
  let lastMeasureLine = -1
  let countedInPart = false
  let contentLineIndex = -1

  function recordMeasure(lineIndex: number, advance: number): void {
    const target = lineResults[lineIndex]
    const span = Math.max(1, advance)
    if (target) {
      if (target.firstMeasure === null) target.firstMeasure = measureNumber
      target.lastMeasure = measureNumber + span - 1
    }
    lastMeasureStart = measureNumber
    lastMeasureLine = lineIndex
    measureNumber += span
    partAdvance += span
    lastAdvance = span
    countedInPart = true
  }

  function resetPartState(): void {
    measureNumber = pageStart
    partAdvance = 0
    hasContent = false
    pendingRepeat = 1
    skipEmpty = false
    afterRepeatStart = false
    repeatAppliedBackward = false
    lastAdvance = 0
    lastMeasureStart = 0
    lastMeasureLine = -1
    countedInPart = false
    contentLineIndex = -1
  }

  /** 小节线 flush：与后端 `flush_measure` 的空小节/吞并规则一致。 */
  function flushBar(
    lineIndex: number,
    kind: 'bar' | 'repeatStart' | 'repeatEnd',
  ): void {
    if (hasContent) {
      recordMeasure(lineIndex, pendingRepeat)
    } else if (repeatAppliedBackward) {
      // backward `*N` 之后的空小节被整个吞掉，不分配号。
      repeatAppliedBackward = false
    } else if (kind === 'bar' && !skipEmpty) {
      // 空小节保留为整小节休止，占 1 个号。`|:`/`:|` 的空 flush 不保留。
      recordMeasure(lineIndex, 1)
    }
    hasContent = false
    pendingRepeat = 1
    afterRepeatStart = false
    if (kind === 'bar') skipEmpty = false
  }

  function finishPart(): void {
    // 后端每 part 结束时有 final flush：末小节可以没有小节线。
    if (hasContent) recordMeasure(contentLineIndex, pendingRepeat)
    partCounts.push(partAdvance)
    resetPartState()
  }

  function finishPage(): void {
    finishPart()
    const plan = pagePlan[planIndex]
    const measureCount = partCounts.length ? Math.max(0, ...partCounts) : 0
    pages.push({
      pageIndex: (plan?.pageNumber ?? planIndex + 1) - 1,
      pageNumber: plan?.pageNumber ?? planIndex + 1,
      inputFileName: plan?.inputFileName ?? '',
      firstMeasureNumber: pageStart,
      measureCount,
      markerLineIndex: plan?.lineIndex ?? -1,
    })
    pageStart += measureCount
    measureNumber = pageStart
    partCounts = []
  }

  function startPage(index: number): void {
    planIndex = index
    resetPartState()
  }

  startPage(0)
  for (let lineIndex = 0; lineIndex < lines.length; lineIndex += 1) {
    const nextPage = pagePlan[planIndex + 1]
    if (nextPage && nextPage.lineIndex === lineIndex) {
      finishPage()
      startPage(planIndex + 1)
    }
    const line = lines[lineIndex]
    if (lyricLines.has(lineIndex)) continue
    if (tryParseJianpuPageMarker(line)) continue
    if (PART_MARKER_PATTERN.test(line)) {
      finishPart()
      continue
    }

    const code = stripLeadingMeasureLabel(splitInlineComment(line))
    if (isNonMeasureLine(code.trim())) continue

    for (const match of code.matchAll(MEASURE_TOKEN_PATTERN)) {
      const raw = match[0]
      // 后端在遇到任何非 `|`/`||` token 时清除 skip_empty，顺序在分支之前。
      if (skipEmpty && raw !== '|' && raw !== '||') skipEmpty = false
      if (isMeasureLabelToken(raw)) continue
      if (raw === '|' || raw === '||') {
        flushBar(lineIndex, 'bar')
        continue
      }
      if (raw === '|:') {
        flushBar(lineIndex, 'repeatStart')
        afterRepeatStart = true
        continue
      }
      if (raw === ':|') {
        flushBar(lineIndex, 'repeatEnd')
        skipEmpty = true
        continue
      }
      const repeat = REPEAT_TOKEN_PATTERN.exec(raw)
      if (repeat) {
        const count = Math.max(1, Number(repeat[1]))
        if (!hasContent && countedInPart && !afterRepeatStart) {
          // backward：覆盖上一小节的反复次数，而非叠加。
          const delta = count - lastAdvance
          measureNumber = Math.max(pageStart, measureNumber + delta)
          partAdvance = Math.max(0, partAdvance + delta)
          lastAdvance = count
          repeatAppliedBackward = true
          // 该小节现在吃掉 count 个号，把区间标签补上（前向反复同理）。
          const previous = lineResults[lastMeasureLine]
          if (previous && previous.lastMeasure !== null) {
            previous.lastMeasure = Math.max(
              previous.lastMeasure,
              lastMeasureStart + count - 1,
            )
          }
        } else {
          pendingRepeat = count
        }
        continue
      }
      if (
        KEY_TOKEN_PATTERN.test(raw)
        || TIME_TOKEN_PATTERN.test(raw)
        || TEMPO_TOKEN_PATTERN.test(raw)
      ) continue
      hasContent = true
      repeatAppliedBackward = false
      contentLineIndex = lineIndex
    }
  }
  finishPage()

  const firstMeasure = pages[0]?.firstMeasureNumber ?? null
  const lastPage = pages.at(-1)
  const lastMeasure = lastPage?.measureCount
    ? lastPage.firstMeasureNumber + lastPage.measureCount - 1
    : null
  for (const lyricLine of lyricLines) {
    const result = lineResults[lyricLine]
    if (result && firstMeasure !== null && lastMeasure !== null) {
      result.firstMeasure = firstMeasure
      result.lastMeasure = lastMeasure
    }
  }

  return { lines: lineResults, pages }
}

let cachedWalkKey = ''
let cachedWalkResult: MeasureWalkResult | null = null

function walkWithCache(text: string, initialMeasureNumber: number): MeasureWalkResult {
  const key = `${initialMeasureNumber} ${text}`
  if (key !== cachedWalkKey || cachedWalkResult === null) {
    cachedWalkKey = key
    cachedWalkResult = walkJianpuMeasures(text, initialMeasureNumber)
  }
  return cachedWalkResult
}

export function jianpuMeasureCount(text: string, initialMeasureNumber = 1): number {
  const { pages } = walkWithCache(normalizeLineEndings(text), initialMeasureNumber)
  return pages.reduce((total, page) => total + page.measureCount, 0)
}

export function jianpuPageSummaries(
  text: string,
  initialMeasureNumber = 1,
): JianpuPageSummary[] {
  const { pages } = walkWithCache(normalizeLineEndings(text), initialMeasureNumber)
  return pages.map((page) => ({
    pageIndex: page.pageIndex,
    pageNumber: page.pageNumber,
    inputFileName: page.inputFileName,
    firstMeasureNumber: page.firstMeasureNumber,
    lastMeasureNumber: page.measureCount
      ? page.firstMeasureNumber + page.measureCount - 1
      : null,
    measureCount: page.measureCount,
    markerLineIndex: page.markerLineIndex,
  }))
}

export function jianpuGutterLabels(text: string, initialMeasureNumber = 1): string[] {
  const normalized = normalizeLineEndings(text)
  const { lines, pages } = walkWithCache(normalized, initialMeasureNumber)
  const totalMeasures = pages.reduce((total, page) => total + page.measureCount, 0)
  const scoreRange = totalMeasures
    ? `${initialMeasureNumber}-${initialMeasureNumber + totalMeasures - 1}`
    : ''
  const rawLines = normalized.split('\n')
  const lyricLines = lyricBlockLineIndexes(normalized)
  return rawLines.map((line, index) => {
    const marker = tryParseJianpuPageMarker(line)
    if (marker) return `P${marker.pageNumber}`

    const info = lines[index]
    if (lyricLines.has(index)) return scoreRange
    if (!info || info.firstMeasure === null || info.lastMeasure === null) return ''
    if (info.firstMeasure === info.lastMeasure) return String(info.firstMeasure)
    const label = `${info.firstMeasure}-${info.lastMeasure}`
    // 一行挤了太多小节时退化为 `n+`，避免撑破 gutter（宽度见 JianpuEditor）。
    return label.length > MAX_GUTTER_LABEL_LENGTH ? `${info.firstMeasure}+` : label
  })
}
