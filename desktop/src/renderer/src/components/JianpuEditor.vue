<template>
  <div class="editor-shell">
    <div
      v-if="showPageSummary"
      class="editor-pages"
    >
      <button
        v-for="page in pageSummaries"
        :key="`${page.pageNumber}-${page.markerLineIndex}`"
        type="button"
        class="editor-page-link"
        :title="page.inputFileName || `第 ${page.pageNumber} 页`"
        @click="scrollToPage(page.markerLineIndex)"
      >
        <span class="editor-page-number">P{{ page.pageNumber }}</span>
        <span class="editor-page-range">{{ pageRangeText(page) }}</span>
      </button>
      <div class="editor-initial-measure-group">
        <span class="editor-initial-measure-label">修改起始小节号</span>
        <n-input-number
          v-model:value="initialMeasureNumberModel"
          class="editor-initial-measure-number"
          size="tiny"
          :min="1"
          :precision="0"
          :show-button="false"
          placeholder="起始小节号"
          aria-label="第一页起始小节号"
        />
      </div>
    </div>
    <div class="editor-body">
      <div
        ref="gutterRef"
        class="editor-gutter"
      >
        <div
          v-for="(label, i) in measureLabels"
          :key="i"
          class="editor-gutter-line"
          :class="{
            'has-number': !!label && !label.startsWith('P'),
            'page-marker': label.startsWith('P'),
          }"
        >
          {{ label }}
        </div>
      </div>
      <div
        class="editor-main"
        :class="{ 'is-transposing': transposing }"
      >
        <div
          v-if="syntaxHighlight || syntaxDiagnostics.length"
          class="editor-highlight"
          aria-hidden="true"
        >
          <div
            class="editor-highlight-content"
            :style="highlightScrollStyle"
          >
            <div
              v-for="(line, lineIndex) in highlightedLines"
              :key="lineIndex"
              class="editor-highlight-line"
            >
              <span
                v-for="(token, tokenIndex) in line"
                :key="tokenIndex"
                :class="[
                  `token-${token.type}`,
                  {
                    'syntax-error-token': token.syntaxError,
                    'syntax-warning-token': token.syntaxWarning,
                    'active-diagnostic': token.activeDiagnostic,
                  },
                ]"
              >{{ token.text }}</span>
            </div>
          </div>
        </div>
        <textarea
          ref="textareaRef"
          :value="modelValue"
          :readonly="transposing"
          placeholder="title=瑞雪迎春&#10;1=C&#10;4/4&#10;1 2 $345$ 4 |&#10;1=G&#10;3/4&#10;h[1+3+5] \p 4 |&#10;L: 春 风 又 绿"
          :class="['editor-textarea', { 'syntax-highlight-enabled': syntaxHighlight || syntaxDiagnostics.length }]"
          spellcheck="false"
          @input="onInput"
          @scroll="syncScroll"
        />
        <div
          v-if="transposing"
          class="editor-transpose-lock"
          role="status"
        >
          <span class="editor-transpose-lock-dot" />
          转调中…
        </div>
        <div
          v-for="(style, i) in playbackHighlightStyles"
          :key="i"
          class="editor-playback-highlight"
          :style="style"
        />
        <div
          v-if="errorHighlightStyle"
          class="editor-error-line"
          :style="errorHighlightStyle"
        />
        <div
          v-if="errorHighlightStyle && errorBlinkActive"
          :key="`error-blink-${errorBlinkKey}`"
          class="editor-error-line-blink"
          :style="errorHighlightStyle"
        />
        <div
          v-if="pageFlashStyle && pageFlashActive"
          :key="`page-flash-${pageFlashKey}`"
          class="editor-page-flash"
          :style="pageFlashStyle"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, nextTick, onMounted, onUnmounted, watch } from 'vue'
import { findJianpuNoteSpans } from '../utils/jianpuPlayback'
import { horizontalScrollIntoView } from '../utils/editorViewport'
import { tokenizeJianpuLine, type JianpuSyntaxToken } from '../utils/jianpuSyntax'
import type { SyntaxDiagnostic } from '../models/types'
import { NInputNumber, useMessage } from 'naive-ui'
import {
  hasJianpuPageMarkers,
  jianpuGutterLabels,
  jianpuPageSummaries,
  type JianpuPageSummary,
} from '../utils/jianpuPageSections'
import { loadEditorScroll, saveEditorScroll } from '../composables/useViewPersistence'
import { classifyKeyEdit, remapOffset } from '../utils/jianpuTranspose'
import { AutoTransposeGate } from '../utils/autoTransposeGate'
import { useSettingsStore } from '../stores/settings'
import { useLogStore } from '../stores/log'
import { jianpuApi } from '../api/jianpu'
import type { RekeySpanMapping } from '../utils/textAnchorTracking'

const settings = useSettingsStore()
const logStore = useLogStore()
const message = useMessage()

const props = withDefaults(defineProps<{
  modelValue: string
  currentNoteIndex?: number
  syntaxHighlight?: boolean
  syntaxDiagnostics?: SyntaxDiagnostic[]
  activeDiagnosticId?: string | null
  errorLine?: number
  flashLine?: number
  initialMeasureNumber?: number
  scrollPersistenceKey?: string | null
}>(), {
  currentNoteIndex: -1,
  syntaxHighlight: false,
  syntaxDiagnostics: () => [],
  activeDiagnosticId: null,
  errorLine: -1,
  flashLine: -1,
  initialMeasureNumber: 1,
  scrollPersistenceKey: null,
})
const emit = defineEmits<{
  'update:modelValue': [value: string]
  'update:initialMeasureNumber': [value: number]
  'rekey-applied': [payload: {
    before: string
    after: string
    anchorMapping: RekeySpanMapping[] | null
  }]
}>()

const initialMeasureNumberModel = computed({
  get: () => props.initialMeasureNumber,
  set: (value: number | null) => emit(
    'update:initialMeasureNumber',
    Math.max(1, Math.trunc(value || 1)),
  ),
})

const gutterRef = ref<HTMLDivElement | null>(null)
const textareaRef = ref<HTMLTextAreaElement | null>(null)
const transposing = ref(false)
const scrollTop = ref(0)
const scrollLeft = ref(0)
const editorMetrics = ref({
  charWidth: 7.8,
  lineHeight: 22.75,
  paddingLeft: 10,
  paddingTop: 8,
})
let resizeObserver: ResizeObserver | null = null

function selectRange(
  start: number,
  end: number,
  options: { flash?: boolean } = {},
): boolean {
  const element = textareaRef.value
  if (!element || start < 0 || end <= start || end > props.modelValue.length) return false
  const savedScrollTop = element.scrollTop
  element.focus()
  element.setSelectionRange(start, end)
  element.scrollTop = savedScrollTop
  const line = props.modelValue.slice(0, start).split('\n').length - 1
  if (options.flash !== false) triggerPageFlash(line)
  nextTick(() => scrollRangeIntoView(element, start, end))
  return true
}

function getSelectionRange(): { start: number; end: number } | null {
  const element = textareaRef.value
  if (!element) return null
  return { start: element.selectionStart ?? 0, end: element.selectionEnd ?? 0 }
}

defineExpose({ selectRange, getSelectionRange, flushPendingAutoTranspose, transposing })

const noteSpans = computed(() => findJianpuNoteSpans(props.modelValue))
interface HighlightToken extends JianpuSyntaxToken {
  syntaxError?: boolean
  syntaxWarning?: boolean
  activeDiagnostic?: boolean
}

const lineOffsets = computed(() => {
  const offsets: number[] = []
  let offset = 0
  for (const line of props.modelValue.split('\n')) {
    offsets.push(offset)
    offset += line.length + 1
  }
  return offsets
})

const highlightedLines = computed(() => props.modelValue.split('\n').map((line, lineIndex) => {
  const lineStart = lineOffsets.value[lineIndex] ?? 0
  const lineEnd = lineStart + line.length
  const ranges = props.syntaxDiagnostics
    .filter((diagnostic) => diagnostic.end > lineStart && diagnostic.start < lineEnd)
    .map((diagnostic) => ({
      start: Math.max(lineStart, diagnostic.start) - lineStart,
      end: Math.min(lineEnd, diagnostic.end) - lineStart,
      active: diagnostic.id === props.activeDiagnosticId,
      severity: diagnostic.severity ?? 'error',
    }))
    .filter((range) => range.end > range.start)
    .sort((a, b) => a.start - b.start)

  if (!ranges.length) {
    const tokens = tokenizeJianpuLine(line) as HighlightToken[]
    if (props.syntaxHighlight) return tokens
    return tokens.map((token) => ({ ...token, type: 'plain' }))
  }
  const result: HighlightToken[] = []
  let cursor = 0
  for (const token of tokenizeJianpuLine(line)) {
    const tokenStart = cursor
    const tokenEnd = cursor + token.text.length
    cursor = tokenEnd
    const boundaries = new Set<number>([tokenStart, tokenEnd])
    for (const range of ranges) {
      if (range.start < tokenEnd && range.end > tokenStart) {
        boundaries.add(Math.max(tokenStart, range.start))
        boundaries.add(Math.min(tokenEnd, range.end))
      }
    }
    const sortedBoundaries = [...boundaries].sort((a, b) => a - b)
    for (let i = 0; i < sortedBoundaries.length - 1; i += 1) {
      const start = sortedBoundaries[i]
      const end = sortedBoundaries[i + 1]
      const matching = ranges.find((range) => range.start < end && range.end > start)
      result.push({
        text: token.text.slice(start - tokenStart, end - tokenStart),
        type: props.syntaxHighlight ? token.type : 'plain',
        syntaxError: matching?.severity === 'error',
        syntaxWarning: matching?.severity === 'warning',
        activeDiagnostic: matching?.active,
      })
    }
  }
  return result
}))
const highlightScrollStyle = computed(() => ({
  transform: `translate(${-scrollLeft.value}px, ${-scrollTop.value}px)`,
}))
const activeNoteSpans = computed(() => (
  props.currentNoteIndex >= 0
    ? noteSpans.value.filter((span) => span.index === props.currentNoteIndex)
    : []
))
const playbackHighlightStyles = computed(() => {
  const metrics = editorMetrics.value
  return activeNoteSpans.value.map((span) => {
    const top = metrics.paddingTop + span.line * metrics.lineHeight - scrollTop.value
    const left = metrics.paddingLeft + span.startColumn * metrics.charWidth - scrollLeft.value
    const width = Math.max(metrics.charWidth, (span.endColumn - span.startColumn) * metrics.charWidth)
    return {
      transform: `translate(${left}px, ${top}px)`,
      width: `${width}px`,
      height: `${metrics.lineHeight}px`,
    }
  })
})

const errorBlinkKey = ref(0)
const errorBlinkActive = ref(false)
let errorBlinkTimer: ReturnType<typeof setTimeout> | null = null

const pageFlashKey = ref(0)
const pageFlashActive = ref(false)
const pageFlashLine = ref(-1)
let pageFlashTimer: ReturnType<typeof setTimeout> | null = null

const pageFlashStyle = computed(() => {
  if (pageFlashLine.value < 0) return null
  const metrics = editorMetrics.value
  const top = metrics.paddingTop + pageFlashLine.value * metrics.lineHeight - scrollTop.value
  return {
    transform: `translateY(${top}px)`,
    height: `${metrics.lineHeight}px`,
  }
})

const PAGE_FLASH_MS = 1200

function triggerPageFlash(line: number): void {
  const el = textareaRef.value
  if (!el || line < 0) return
  if (pageFlashTimer !== null) {
    clearTimeout(pageFlashTimer)
    pageFlashTimer = null
  }
  nextTick(() => {
    scrollLineIntoView(el, line)
    pageFlashLine.value = line
    pageFlashKey.value++
    pageFlashActive.value = true
    pageFlashTimer = setTimeout(() => {
      pageFlashActive.value = false
      pageFlashTimer = null
    }, PAGE_FLASH_MS)
  })
}

function scrollLineIntoView(el: HTMLTextAreaElement, line: number): void {
  const metrics = editorMetrics.value
  const top = metrics.paddingTop + line * metrics.lineHeight
  const bottom = top + metrics.lineHeight
  if (top < el.scrollTop) {
    el.scrollTop = Math.max(0, top - metrics.lineHeight)
  } else if (bottom > el.scrollTop + el.clientHeight) {
    el.scrollTop = bottom - el.clientHeight + metrics.lineHeight
  }
  syncScrollPosition(el)
}

function scrollRangeIntoView(el: HTMLTextAreaElement, start: number, end: number): void {
  const metrics = editorMetrics.value
  const lineStart = props.modelValue.lastIndexOf('\n', Math.max(0, start - 1)) + 1
  const lineEnd = props.modelValue.indexOf('\n', start)
  const selectedEnd = lineEnd < 0 ? end : Math.min(end, lineEnd)
  const startColumn = start - lineStart
  const endColumn = Math.max(startColumn + 1, selectedEnd - lineStart)
  const line = props.modelValue.slice(0, start).split('\n').length - 1
  const top = metrics.paddingTop + line * metrics.lineHeight
  const bottom = top + metrics.lineHeight
  if (top < el.scrollTop) {
    el.scrollTop = Math.max(0, top - metrics.lineHeight)
  } else if (bottom > el.scrollTop + el.clientHeight) {
    el.scrollTop = bottom - el.clientHeight + metrics.lineHeight
  }
  el.scrollLeft = horizontalScrollIntoView({
    scrollLeft: el.scrollLeft,
    clientWidth: el.clientWidth,
    paddingLeft: metrics.paddingLeft,
    charWidth: metrics.charWidth,
    startColumn,
    endColumn,
  })
  syncScrollPosition(el)
}

const errorHighlightStyle = computed(() => {
  if (props.errorLine < 0) return null
  const metrics = editorMetrics.value
  const top = metrics.paddingTop + props.errorLine * metrics.lineHeight - scrollTop.value
  return {
    transform: `translateY(${top}px)`,
    height: `${metrics.lineHeight}px`,
  }
})

function scrollErrorLineIntoView(line: number): void {
  const el = textareaRef.value
  if (!el || line < 0) return

  const metrics = editorMetrics.value
  const top = metrics.paddingTop + line * metrics.lineHeight
  const bottom = top + metrics.lineHeight

  if (top < el.scrollTop) {
    el.scrollTop = Math.max(0, top - metrics.lineHeight)
  } else if (bottom > el.scrollTop + el.clientHeight) {
    el.scrollTop = bottom - el.clientHeight + metrics.lineHeight
  }

  syncScrollPosition(el)
}

watch(() => props.errorLine, (line, oldLine) => {
  if (errorBlinkTimer !== null) {
    clearTimeout(errorBlinkTimer)
    errorBlinkTimer = null
  }
  if (line < 0) {
    errorBlinkActive.value = false
    return
  }
  if (line === oldLine) return
  nextTick(() => {
    scrollErrorLineIntoView(line)
    errorBlinkKey.value++
    errorBlinkActive.value = true
    errorBlinkTimer = setTimeout(() => {
      errorBlinkActive.value = false
      errorBlinkTimer = null
    }, 1400)
  })
})

/** 当前光标前的 | 是否是独立小节线（非 ||、|:、:| 的一部分） */
function isStandaloneBarline(value: string, cursor: number): boolean {
  if (cursor > 0 && value[cursor - 1] === '|') {
    const before = cursor >= 2 ? value[cursor - 2] : ''
    const after = cursor < value.length ? value[cursor] : ''
    if (before === ':' || before === '|') return false
    if (after === '|' || after === ':') return false
    return true
  }
  return false
}

function isCursorInLineComment(value: string, cursor: number): boolean {
  const lineStart = value.lastIndexOf('\n', Math.max(0, cursor - 1)) + 1
  const linePrefix = value.slice(lineStart, cursor)
  return linePrefix.includes('//')
}

function onInput(e: Event): void {
  const target = e.target as HTMLTextAreaElement
  const value = target.value
  const cursor = target.selectionStart
  // 此刻 props.modelValue 仍是编辑前的文本（emit 在下面才发生），
  // 它就是自动转调需要的旧调来源。
  const before = props.modelValue

  // 输入了 |：检查是否是独立小节线，自动换行
  if (
    !isCursorInLineComment(value, cursor) &&
    isStandaloneBarline(value, cursor) &&
    (cursor >= value.length || value[cursor] !== '\n')
  ) {
    const newValue = value.slice(0, cursor) + '\n' + value.slice(cursor)
    emit('update:modelValue', newValue)
    nextTick(() => {
      const el = textareaRef.value
      if (el) {
        el.selectionStart = el.selectionEnd = cursor + 1
      }
    })
    scheduleKeyChangeCheck(before, newValue)
    return
  }

  // 输入了 |: 中的 :——撤回之前 | 的自动换行
  if (
    cursor > 0 &&
    value[cursor - 1] === ':' &&
    cursor >= 2 &&
    value[cursor - 2] === '|' &&
    cursor < value.length &&
    value[cursor] === '\n'
  ) {
    const newValue = value.slice(0, cursor) + value.slice(cursor + 1)
    emit('update:modelValue', newValue)
    nextTick(() => {
      const el = textareaRef.value
      if (el) {
        el.selectionStart = el.selectionEnd = cursor
      }
    })
    scheduleKeyChangeCheck(before, newValue)
    return
  }

  emit('update:modelValue', value)
  scheduleKeyChangeCheck(before, value)
}

// 自动转调：debounce 后把「编辑前 → 编辑后」交给后端重记谱。
// 基线时机与竞态判定全部在 AutoTransposeGate 里，此处只负责计时器与 DOM。
let keyChangeTimer: ReturnType<typeof setTimeout> | null = null
let autoTransposeTask: Promise<void> | null = null
const KEY_CHANGE_DEBOUNCE_MS = 600
const autoTransposeGate = new AutoTransposeGate(classifyKeyEdit)

function clearKeyChangeTimer(): void {
  if (keyChangeTimer !== null) {
    clearTimeout(keyChangeTimer)
    keyChangeTimer = null
  }
}

function scheduleKeyChangeCheck(before: string, after: string): void {
  clearKeyChangeTimer()
  if (!settings.jianpuAutoTranspose) {
    autoTransposeGate.reset()
    return
  }
  autoTransposeGate.recordEdit(before, after)
  keyChangeTimer = setTimeout(() => {
    keyChangeTimer = null
    // The task reports failures; background execution must also consume rejection.
    void triggerAutoTranspose().catch(() => {})
  }, KEY_CHANGE_DEBOUNCE_MS)
}

// Backend skip reasons leave the edit unresolved and must block persistence.
const SKIP_MESSAGES: Record<string, string> = {
  parse_error: '简谱有语法错误，自动转调已跳过',
  unresolvable_key_change: '删除调号无法自动转调，请直接把调号改写成新调',
}

// 保存前调用：把待执行的转调立刻做完并等它落地，避免 debounce 落进保存窗口。
// 刻意不用 cancel —— 丢掉待发转调会留下「新调号 + 未转调音符」的错谱，比报错更糟。
async function flushPendingAutoTranspose(): Promise<void> {
  clearKeyChangeTimer()
  await nextTick()
  await triggerAutoTranspose()
  await nextTick()
}

function triggerAutoTranspose(): Promise<void> {
  if (autoTransposeTask) return autoTransposeTask
  autoTransposeTask = performAutoTranspose().finally(() => {
    autoTransposeTask = null
  })
  return autoTransposeTask
}

async function performAutoTranspose(): Promise<void> {
  if (!settings.jianpuAutoTranspose) return
  const pending = autoTransposeGate.takePending(props.modelValue)
  if (pending === null) return
  const requestId = autoTransposeGate.beginRequest()
  // 转调期间锁定编辑器：响应落地前的任何输入都会让在途结果作废，
  // 还会留下「新调号 + 未转调音符」的错谱。
  transposing.value = true
  try {
    const result = await jianpuApi.rekeyText({
      text: pending.text,
      previous_text: pending.baseline,
    })
    if (!autoTransposeGate.acceptResponse(requestId, pending.text, props.modelValue)) {
      throw new Error('转调期间谱面已变更，请检查当前编辑后重试')
    }
    if (result.error) {
      throw result.error
    }
    const skipReason = result.data?.skip_reason
    if (skipReason) {
      const detail = result.data?.skip_detail
      throw new Error(SKIP_MESSAGES[skipReason] || detail || `自动转调已跳过：${skipReason}`)
    }
    const transposed = result.data?.transposed_text
    if (!transposed) {
      throw new Error('自动转调未返回谱面文本')
    }
    if (transposed === pending.text) {
      autoTransposeGate.commitRequest()
      return
    }
    emit('rekey-applied', {
      before: pending.text,
      after: transposed,
      anchorMapping: result.data?.anchor_mapping ?? null,
    })
    // Queue the semantic marker before changing v-model so a synchronous
    // parent watcher cannot mistake this update for ordinary user input.
    applyTransposed(pending.text, transposed)
    autoTransposeGate.commitRequest()
  } catch (error: unknown) {
    autoTransposeGate.rollbackRequest(requestId)
    if (settings.jianpuAutoTranspose && props.modelValue === pending.text) {
      // Keep the failed edit retryable even after its debounce timer has fired.
      autoTransposeGate.recordEdit(pending.baseline, pending.text)
    }
    const detail = error instanceof Error ? error.message : String(error)
    logStore.addError(`自动转调失败：${detail}`)
    message.warning(`自动转调未完成：${detail}`)
    throw error
  } finally {
    transposing.value = false
  }
}

function applyTransposed(before: string, after: string): void {
  const el = textareaRef.value
  const cursor = el ? el.selectionStart : null
  const anchor = el ? el.selectionEnd : null
  emit('update:modelValue', after)
  if (cursor === null) return
  const nextStart = remapOffset(before, after, cursor)
  const nextEnd = anchor === null ? nextStart : remapOffset(before, after, anchor)
  nextTick(() => {
    const current = textareaRef.value
    if (!current) return
    current.selectionStart = nextStart
    current.selectionEnd = nextEnd
  })
}

function syncScroll(e: Event): void {
  const target = e.target as HTMLTextAreaElement
  syncScrollPosition(target)
}

const measureLabels = computed(() =>
  jianpuGutterLabels(props.modelValue, props.initialMeasureNumber),
)
const pageSummaries = computed(() =>
  jianpuPageSummaries(props.modelValue, props.initialMeasureNumber),
)
const showPageSummary = computed(() =>
  hasJianpuPageMarkers(props.modelValue) && pageSummaries.value.length > 0,
)

function pageRangeText(page: JianpuPageSummary): string {
  if (page.lastMeasureNumber === null) return `${page.firstMeasureNumber}+`
  if (page.lastMeasureNumber === page.firstMeasureNumber) return String(page.firstMeasureNumber)
  return `${page.firstMeasureNumber}-${page.lastMeasureNumber}`
}

function scrollToPage(markerLineIndex: number): void {
  triggerPageFlash(markerLineIndex)
  textareaRef.value?.focus()
}

watch(() => props.flashLine, (line, oldLine) => {
  if (line < 0) {
    pageFlashActive.value = false
    return
  }
  if (line === oldLine) return
  triggerPageFlash(line)
})

// 注意：这里刻意不监听 props.modelValue 来维护转调基线。
// modelValue 的变化里既有外部同步(切页/历史恢复)，也有本组件 emit 的回环，
// 二者无法区分；一旦在 watcher 里重置基线，用户刚敲入的新调号就会被当成旧调，
// 使 debounce 到期时检测不到变化。基线由 onInput 显式提供，
// 外部覆盖则由 AutoTransposeGate 的 takePending / acceptResponse 用文本比对拦掉。

watch(activeNoteSpans, (spans) => {
  const span = spans[0]
  if (!span) return
  nextTick(() => scrollNoteIntoView(span))
})

// 关闭开关时立刻丢弃待发编辑并让在途响应失效，避免关掉后音符还被改写。
watch(() => settings.jianpuAutoTranspose, (enabled) => {
  if (enabled) return
  clearKeyChangeTimer()
  autoTransposeGate.reset()
})

onMounted(() => {
  refreshEditorMetrics()
  const el = textareaRef.value
  if (!el) return
  const saved = loadEditorScroll(props.scrollPersistenceKey)
  if (saved) {
    scrollTop.value = saved.scrollTop
    scrollLeft.value = saved.scrollLeft
    if (gutterRef.value) gutterRef.value.scrollTop = saved.scrollTop
    nextTick(() => {
      const current = textareaRef.value
      if (!current) return
      current.scrollTop = saved.scrollTop
      current.scrollLeft = saved.scrollLeft
    })
  }
  resizeObserver = new ResizeObserver(refreshEditorMetrics)
  resizeObserver.observe(el)
})

onUnmounted(() => {
  if (props.scrollPersistenceKey) {
    saveEditorScroll(props.scrollPersistenceKey, {
      scrollTop: scrollTop.value,
      scrollLeft: scrollLeft.value,
    })
  }
  resizeObserver?.disconnect()
  resizeObserver = null
  if (errorBlinkTimer !== null) {
    clearTimeout(errorBlinkTimer)
    errorBlinkTimer = null
  }
  if (pageFlashTimer !== null) {
    clearTimeout(pageFlashTimer)
    pageFlashTimer = null
  }
  clearKeyChangeTimer()
  autoTransposeGate.reset()
})

function syncScrollPosition(target: HTMLTextAreaElement): void {
  scrollTop.value = target.scrollTop
  scrollLeft.value = target.scrollLeft
  if (gutterRef.value) {
    gutterRef.value.scrollTop = target.scrollTop
  }
}

function refreshEditorMetrics(): void {
  const el = textareaRef.value
  if (!el) return

  const style = window.getComputedStyle(el)
  const canvas = document.createElement('canvas')
  const context = canvas.getContext('2d')
  if (context) {
    context.font = `${style.fontStyle} ${style.fontWeight} ${style.fontSize} ${style.fontFamily}`
  }
  const fontSize = parseFloat(style.fontSize) || 13
  editorMetrics.value = {
    charWidth: context?.measureText('0').width || fontSize * 0.6,
    lineHeight: parseFloat(style.lineHeight) || fontSize * 1.75,
    paddingLeft: parseFloat(style.paddingLeft) || 0,
    paddingTop: parseFloat(style.paddingTop) || 0,
  }
}

function scrollNoteIntoView(span: { line: number; startColumn: number; endColumn: number }): void {
  const el = textareaRef.value
  if (!el) return

  const metrics = editorMetrics.value
  const top = metrics.paddingTop + span.line * metrics.lineHeight
  const bottom = top + metrics.lineHeight
  const left = metrics.paddingLeft + span.startColumn * metrics.charWidth
  const right = metrics.paddingLeft + span.endColumn * metrics.charWidth

  if (top < el.scrollTop) {
    el.scrollTop = Math.max(0, top - metrics.lineHeight)
  } else if (bottom > el.scrollTop + el.clientHeight) {
    el.scrollTop = bottom - el.clientHeight + metrics.lineHeight
  }

  if (left < el.scrollLeft) {
    el.scrollLeft = Math.max(0, left - metrics.charWidth * 2)
  } else if (right > el.scrollLeft + el.clientWidth) {
    el.scrollLeft = right - el.clientWidth + metrics.charWidth * 2
  }

  syncScrollPosition(el)
}
</script>

<style scoped>
.editor-shell {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.editor-pages {
  min-height: 32px;
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 6px;
  overflow-x: auto;
  border-bottom: 1px solid var(--border-color, #e0e0e0);
  background: var(--bg-soft, #f5f5f5);
}

.editor-page-link {
  height: 24px;
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 0 7px;
  border: 1px solid transparent;
  border-radius: var(--radius-sm, 4px);
  background: transparent;
  color: var(--text-secondary, #555);
  font: inherit;
  cursor: pointer;
}

.editor-page-link:hover {
  border-color: var(--border-color, #d0d0d0);
  background: var(--bg-base, #fff);
}

.editor-page-number {
  font-weight: 600;
  color: var(--text-primary, #333);
}

.editor-page-range {
  font-family: 'Cascadia Code', 'Consolas', monospace;
  font-size: 12px;
  color: var(--text-muted, #777);
}

.editor-initial-measure-group {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 6px;
}

.editor-initial-measure-label {
  font-size: 11px;
  color: var(--text-muted, #777);
  white-space: nowrap;
}

.editor-initial-measure-number {
  flex: 0 0 72px;
}

.editor-body {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: row;
  overflow: hidden;
}

.editor-main {
  flex: 1;
  min-width: 0;
  min-height: 0;
  display: flex;
  position: relative;
  overflow: hidden;
}

.editor-highlight {
  position: absolute;
  inset: 0;
  z-index: 0;
  overflow: hidden;
  padding: 8px 10px;
  border-radius: 0 var(--radius-sm, 4px) var(--radius-sm, 4px) 0;
  background: var(--bg-base, #fff);
  color: var(--text-primary, #333);
  font-family: 'Cascadia Code', 'Consolas', monospace;
  font-size: 13px;
  line-height: 22.75px;
  white-space: pre;
  pointer-events: none;
}

.editor-highlight-content {
  min-width: max-content;
}

.editor-highlight-line {
  min-height: 22.75px;
}

.editor-gutter {
  /* 宽度必须恒定：flex 子项默认 min-width:auto 会被区间标签（如 "1-3"）撑开，
     用 flex-basis + min-width:0 锁死，内容溢出由 overflow:hidden 裁剪。
     44px 容纳 3 位小节号或 3 字符区间（"10-"）+ 6px 右内边距，更长由 JS 截断为 n+。 */
  flex: 0 0 44px;
  min-width: 0;
  width: 44px;
  max-width: 44px;
  overflow: hidden;
  background: var(--bg-soft, #f5f5f5);
  border-right: 1px solid var(--border-color, #e0e0e0);
  border-radius: var(--radius-sm, 4px) 0 0 var(--radius-sm, 4px);
  font-family: 'Cascadia Code', 'Consolas', monospace;
  font-size: 13px;
  line-height: 22.75px;
  padding: 8px 0;
  user-select: none;
  text-align: right;
  padding-right: 6px;
  color: var(--text-muted, #999);
}

.editor-gutter-line {
  height: 22.75px;
  box-sizing: border-box;
}

.editor-gutter-line.has-number {
  color: var(--text-primary, #333);
  font-weight: 500;
}

.editor-gutter-line.page-marker {
  color: var(--primary-color, #2563eb);
  font-weight: 600;
}

.editor-textarea {
  flex: 1;
  min-height: 0;
  border: none;
  outline: none;
  resize: none;
  font-family: 'Cascadia Code', 'Consolas', monospace;
  font-size: 13px;
  line-height: 22.75px;
  padding: 8px 10px;
  background: var(--bg-base, #fff);
  color: var(--text-primary, #333);
  border-radius: 0 var(--radius-sm, 4px) var(--radius-sm, 4px) 0;
  white-space: pre;
  overflow-wrap: normal;
  overflow-x: auto;
  position: relative;
  z-index: 1;
}

.editor-textarea.syntax-highlight-enabled {
  background: transparent;
  color: transparent;
  caret-color: var(--text-primary, #333);
}

.editor-textarea.syntax-highlight-enabled::selection {
  background: rgba(76, 110, 245, 0.26);
}

.editor-main.is-transposing .editor-textarea,
.editor-main.is-transposing .editor-highlight {
  opacity: 0.55;
}

.editor-textarea[readonly] {
  cursor: default;
}

.editor-transpose-lock {
  position: absolute;
  top: 8px;
  right: 10px;
  z-index: 3;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 3px 10px;
  border: 1px solid var(--border-color, #e0e0e0);
  border-radius: 999px;
  background: var(--bg-soft, #f5f5f5);
  color: var(--text-secondary, #555);
  font-size: 12px;
  line-height: 1.5;
  pointer-events: none;
  user-select: none;
}

.editor-transpose-lock-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--primary-color, #2563eb);
  animation: editor-transpose-lock-pulse 0.9s ease-in-out infinite;
}

@keyframes editor-transpose-lock-pulse {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.25;
  }
}

.syntax-error-token {
  text-decoration-line: underline;
  text-decoration-style: wavy;
  text-decoration-color: var(--danger, #dc2626);
  text-decoration-thickness: 1.5px;
  text-underline-offset: 3px;
}

.syntax-error-token.active-diagnostic {
  background: rgba(220, 38, 38, 0.16);
}

.syntax-warning-token {
  text-decoration-line: underline;
  text-decoration-style: wavy;
  text-decoration-color: var(--warning, #fab005);
  text-decoration-thickness: 1.5px;
  text-underline-offset: 3px;
}

.syntax-warning-token.active-diagnostic {
  background: rgba(250, 176, 5, 0.18);
}

.editor-playback-highlight {
  position: absolute;
  top: 0;
  left: 0;
  border-radius: 3px;
  background: rgba(217, 119, 6, 0.22);
  box-shadow: inset 0 0 0 1px rgba(217, 119, 6, 0.52);
  pointer-events: none;
  z-index: 2;
}

.editor-error-line {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  background: rgba(220, 38, 38, 0.10);
  border-left: 3px solid rgba(220, 38, 38, 0.5);
  pointer-events: none;
  z-index: 2;
}

.editor-error-line-blink {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  background: rgba(220, 38, 38, 0.38);
  border-left: 3px solid rgba(220, 38, 38, 0.9);
  pointer-events: none;
  z-index: 3;
  animation: error-line-blink 1.4s ease-out forwards;
}

@keyframes error-line-blink {
  0% { opacity: 0; }
  10% { opacity: 1; }
  30% { opacity: 0; }
  50% { opacity: 1; }
  70% { opacity: 0; }
  100% { opacity: 0; }
}

.editor-page-flash {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  background: rgba(37, 99, 235, 0.26);
  border-left: 3px solid rgba(37, 99, 235, 0.85);
  pointer-events: none;
  z-index: 3;
  animation: page-line-flash 1.2s ease-out forwards;
}

@keyframes page-line-flash {
  0% { opacity: 0; }
  10% { opacity: 1; }
  40% { opacity: 0; }
  55% { opacity: 1; }
  85% { opacity: 0; }
  100% { opacity: 0; }
}

.editor-textarea::placeholder {
  color: var(--text-placeholder, #aaa);
}

.token-comment { color: #687076; }
.token-metadata { color: #0550ae; }
.token-note { color: #0969da; }
.token-rest { color: #8250df; }
.token-chord { color: #116329; }
.token-tuplet { color: #953800; }
.token-barline { color: #cf222e; }
.token-repeat { color: #9a6700; }
.token-dynamic { color: #1a7f37; }
.token-ornament { color: #bc4c00; }
.token-lyrics { color: #57606a; }

/* Dark theme support */
.theme-dark .editor-gutter {
  background: var(--bg-soft, #2a2a2a);
  border-color: var(--border-color, #444);
  color: var(--text-muted, #777);
}

.theme-dark .editor-gutter-line.has-number {
  color: var(--text-primary, #ddd);
}

.theme-dark .editor-pages {
  background: var(--bg-soft, #2a2a2a);
  border-color: var(--border-color, #444);
}

.theme-dark .editor-page-link:hover {
  background: var(--bg-base, #1e1e1e);
  border-color: var(--border-color, #555);
}

.theme-dark .editor-page-number {
  color: var(--text-primary, #ddd);
}

.theme-dark .editor-gutter-line.page-marker {
  color: #7aa2f7;
}

.theme-dark .editor-textarea {
  background: var(--bg-base, #1e1e1e);
  color: var(--text-primary, #ddd);
}

.theme-dark .editor-highlight {
  background: var(--bg-base, #1e1e1e);
  color: var(--text-primary, #ddd);
}

.theme-dark .editor-textarea.syntax-highlight-enabled {
  background: transparent;
  color: transparent;
  caret-color: var(--text-primary, #ddd);
}

.theme-dark .editor-textarea.syntax-highlight-enabled::selection {
  background: rgba(116, 143, 252, 0.32);
}

.theme-dark .editor-textarea::placeholder {
  color: var(--text-placeholder, #666);
}

.theme-dark .token-comment { color: #6a9955; }
.theme-dark .token-metadata { color: #569cd6; }
.theme-dark .token-note { color: #9cdcfe; }
.theme-dark .token-rest { color: #c586c0; }
.theme-dark .token-chord { color: #4ec9b0; }
.theme-dark .token-tuplet { color: #dcdcaa; }
.theme-dark .token-barline { color: #d7ba7d; }
.theme-dark .token-repeat { color: #b5cea8; }
.theme-dark .token-dynamic { color: #ce9178; }
.theme-dark .token-ornament { color: #d16969; }
.theme-dark .token-lyrics { color: #c8c8c8; }
</style>
