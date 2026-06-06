<template>
  <div class="editor-shell">
    <div class="editor-gutter" ref="gutterRef">
      <div
        v-for="(num, i) in measureNumbers"
        :key="i"
        class="editor-gutter-line"
        :class="{ 'has-number': num > 0 }"
      >
        {{ num > 0 ? num : '' }}
      </div>
    </div>
    <textarea
      ref="textareaRef"
      :value="modelValue"
      @input="onInput"
      @scroll="syncScroll"
      placeholder="title=瑞雪迎春&#10;1=C&#10;4/4&#10;1 2 q3 q4 | h[1+3+5] \p |&#10;L: 春 风 又 绿"
      class="editor-textarea"
      spellcheck="false"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, ref, nextTick, watch } from 'vue'

const props = defineProps<{ modelValue: string; startMeasureNumber?: number }>()
const emit = defineEmits<{ 'update:modelValue': [value: string] }>()

const gutterRef = ref<HTMLDivElement | null>(null)
const textareaRef = ref<HTMLTextAreaElement | null>(null)

function onInput(e: Event): void {
  const target = e.target as HTMLTextAreaElement
  const value = target.value
  const cursor = target.selectionStart

  // 刚输入了 | 且后面不是换行符，自动换行
  if (cursor > 0 && value[cursor - 1] === '|' && (cursor >= value.length || value[cursor] !== '\n')) {
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

  emit('update:modelValue', value)
}

function syncScroll(e: Event): void {
  if (gutterRef.value) {
    gutterRef.value.scrollTop = (e.target as HTMLTextAreaElement).scrollTop
  }
}

function needsFormat(text: string): boolean {
  const lines = text.split('\n')
  for (const line of lines) {
    const trimmed = line.trim()
    if (!trimmed) continue
    // 包含 | 的就是小节（即使以 \ 开头），只检查是否需要按 | 分割
    if (trimmed.includes('|')) {
      if (/\|\S/.test(line)) return true
      continue
    }
    if (
      /^key\s*=/i.test(trimmed) ||
      /^time\s*=/i.test(trimmed) ||
      /^title\s*=/i.test(trimmed) ||
      /^tempo\s*=/i.test(trimmed) ||
      /^L:/.test(trimmed) ||
      /^\\/.test(trimmed)
    ) {
      continue
    }
  }
  return false
}

function formatMeasures(text: string): string {
  const lines = text.split('\n')
  const result: string[] = []
  for (const line of lines) {
    const trimmed = line.trimEnd()
    if (!trimmed) {
      result.push(line)
      continue
    }
    // 包含 | 的就是小节行，需要按 | 分割
    if (trimmed.includes('|')) {
      const formatted = trimmed.replace(/\|/g, '|\n')
      const parts = formatted.split('\n').map((l) => l.trim()).filter((l) => l !== '')
      result.push(...parts)
      continue
    }
    if (
      /^key\s*=/i.test(trimmed) ||
      /^time\s*=/i.test(trimmed) ||
      /^title\s*=/i.test(trimmed) ||
      /^tempo\s*=/i.test(trimmed) ||
      /^L:/.test(trimmed) ||
      /^\\/.test(trimmed)
    ) {
      result.push(line)
      continue
    }
    result.push(line)
  }
  return result.join('\n')
}

watch(
  () => props.modelValue,
  (val) => {
    if (!val) return
    if (!needsFormat(val)) return
    const formatted = formatMeasures(val)
    emit('update:modelValue', formatted)
  },
  { immediate: true },
)

const measureNumbers = computed(() => {
  const lines = props.modelValue.split('\n')
  let measureCount = props.startMeasureNumber ?? 1
  return lines.map((line) => {
    const trimmed = line.trim()
    // 包含 | 的就是小节（即使以 \ 开头如 \f）
    if (trimmed.includes('|')) {
      // 检测重复次数 *x（去掉行尾 | 后再匹配）
      const withoutBar = trimmed.replace(/\|$/, '').trim()
      const match = withoutBar.match(/\*\s*(\d+)$/)
      const repeatCount = match ? parseInt(match[1], 10) : 1
      const currentNumber = measureCount
      measureCount += repeatCount
      return currentNumber
    }
    // 跳过元数据、空行、歌词、纯表情记号行
    if (
      !trimmed ||
      /^key\s*=/i.test(trimmed) ||
      /^time\s*=/i.test(trimmed) ||
      /^title\s*=/i.test(trimmed) ||
      /^tempo\s*=/i.test(trimmed) ||
      /^L:/.test(trimmed) ||
      /^\\/.test(trimmed)
    ) {
      return 0
    }
    return 0
  })
})
</script>

<style scoped>
.editor-shell {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: row;
  overflow: hidden;
}

.editor-gutter {
  width: 32px;
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
}

.editor-textarea::placeholder {
  color: var(--text-placeholder, #aaa);
}

/* Dark theme support */
.theme-dark .editor-gutter {
  background: var(--bg-soft, #2a2a2a);
  border-color: var(--border-color, #444);
  color: var(--text-muted, #777);
}

.theme-dark .editor-gutter-line.has-number {
  color: var(--text-primary, #ddd);
}

.theme-dark .editor-textarea {
  background: var(--bg-base, #1e1e1e);
  color: var(--text-primary, #ddd);
}

.theme-dark .editor-textarea::placeholder {
  color: var(--text-placeholder, #666);
}
</style>
