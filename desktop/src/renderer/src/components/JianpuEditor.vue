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
      <div class="editor-main">
        <div
          v-if="syntaxHighlight"
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
                :class="`token-${token.type}`"
              >{{ token.text }}</span>
            </div>
          </div>
        </div>
        <textarea
          ref="textareaRef"
          :value="modelValue"
          placeholder="title=瑞雪迎春&#10;1=C&#10;4/4&#10;1 2 $345$ 4 |&#10;1=G&#10;3/4&#10;h[1+3+5] \p 4 |&#10;L: 春 风 又 绿"
          :class="['editor-textarea', { 'syntax-highlight-enabled': syntaxHighlight }]"
          spellcheck="false"
          @input="onInput"
          @scroll="syncScroll"
        />
        <div
          v-if="playbackHighlightStyle"
          class="editor-playback-highlight"
          :style="playbackHighlightStyle"
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
import { tokenizeJianpuLine } from '../utils/jianpuSyntax'
import {
  hasJianpuPageMarkers,
  jianpuGutterLabels,
  jianpuPageSummaries,
  type JianpuPageSummary,
} from '../utils/jianpuPageSections'

const props = withDefaults(defineProps<{
  modelValue: string
  startMeasureNumber?: number
  currentNoteIndex?: number
  syntaxHighlight?: boolean
  errorLine?: number
  flashLine?: number
}>(), {
  startMeasureNumber: 1,
  currentNoteIndex: -1,
  syntaxHighlight: false,
  errorLine: -1,
  flashLine: -1,
})
const emit = defineEmits<{ 'update:modelValue': [value: string] }>()

const gutterRef = ref<HTMLDivElement | null>(null)
const textareaRef = ref<HTMLTextAreaElement | null>(null)
const scrollTop = ref(0)
const scrollLeft = ref(0)
const editorMetrics = ref({
  charWidth: 7.8,
  lineHeight: 22.75,
  paddingLeft: 10,
  paddingTop: 8,
})
let resizeObserver: ResizeObserver | null = null

function selectRange(start: number, end: number): boolean {
  const element = textareaRef.value
  if (!element || start < 0 || end <= start || end > props.modelValue.length) return false
  element.focus()
  element.setSelectionRange(start, end)
  const line = props.modelValue.slice(0, start).split('\n').length - 1
  triggerPageFlash(line)
  return true
}

defineExpose({ selectRange })

const noteSpans = computed(() => findJianpuNoteSpans(props.modelValue))
const highlightedLines = computed(() => props.modelValue.split('\n').map(tokenizeJianpuLine))
const highlightScrollStyle = computed(() => ({
  transform: `translate(${-scrollLeft.value}px, ${-scrollTop.value}px)`,
}))
const activeNoteSpan = computed(() => (
  props.currentNoteIndex >= 0
    ? noteSpans.value.find((span) => span.index === props.currentNoteIndex) ?? null
    : null
))
const playbackHighlightStyle = computed(() => {
  const span = activeNoteSpan.value
  if (!span) return null

  const metrics = editorMetrics.value
  const top = metrics.paddingTop + span.line * metrics.lineHeight - scrollTop.value
  const left = metrics.paddingLeft + span.startColumn * metrics.charWidth - scrollLeft.value
  const width = Math.max(metrics.charWidth, (span.endColumn - span.startColumn) * metrics.charWidth)

  return {
    transform: `translate(${left}px, ${top}px)`,
    width: `${width}px`,
    height: `${metrics.lineHeight}px`,
  }
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
    return
  }

  emit('update:modelValue', value)
}

function syncScroll(e: Event): void {
  const target = e.target as HTMLTextAreaElement
  syncScrollPosition(target)
}

const measureLabels = computed(() =>
  jianpuGutterLabels(props.modelValue, props.startMeasureNumber ?? 1),
)
const pageSummaries = computed(() =>
  jianpuPageSummaries(props.modelValue, props.startMeasureNumber ?? 1),
)
const showPageSummary = computed(() =>
  hasJianpuPageMarkers(props.modelValue) && pageSummaries.value.length > 0,
)

function pageRangeText(page: JianpuPageSummary): string {
  if (page.endMeasureNumber === null) return `${page.startMeasureNumber}+`
  if (page.endMeasureNumber === page.startMeasureNumber) return String(page.startMeasureNumber)
  return `${page.startMeasureNumber}-${page.endMeasureNumber}`
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

watch(activeNoteSpan, (span) => {
  if (!span) return
  nextTick(() => scrollNoteIntoView(span))
})

onMounted(() => {
  refreshEditorMetrics()
  if (textareaRef.value) {
    syncScrollPosition(textareaRef.value)
    resizeObserver = new ResizeObserver(refreshEditorMetrics)
    resizeObserver.observe(textareaRef.value)
  }
})

onUnmounted(() => {
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
  width: 42px;
  flex-shrink: 0;
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
