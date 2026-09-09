<template>
  <span>
    <template
      v-for="(segment, index) in segments"
      :key="index"
    >
      <mark
        v-if="segment.hit"
        class="query-hit"
      >{{ segment.text }}</mark>
      <template v-else>{{ segment.text }}</template>
    </template>
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue'

interface HighlightSegment {
  text: string
  hit: boolean
}

const props = defineProps<{
  text: string
  query: string
}>()

const segments = computed<HighlightSegment[]>(() => {
  const query = props.query
  if (!query) return [{ text: props.text, hit: false }]

  // 不能使用带 trim 的归一化结果：会破坏原文切片索引
  const haystack = props.text.toLocaleLowerCase('zh-CN')
  // 大小写折叠后长度变化会导致切片错位，退回不分段的纯文本
  if (haystack.length !== props.text.length) return [{ text: props.text, hit: false }]

  const result: HighlightSegment[] = []
  let cursor = 0
  let found = haystack.indexOf(query)
  while (found !== -1) {
    if (found > cursor) result.push({ text: props.text.slice(cursor, found), hit: false })
    result.push({ text: props.text.slice(found, found + query.length), hit: true })
    cursor = found + query.length
    found = haystack.indexOf(query, cursor)
  }
  if (cursor < props.text.length) result.push({ text: props.text.slice(cursor), hit: false })
  return result.length ? result : [{ text: props.text, hit: false }]
})
</script>

<style scoped>
.query-hit {
  padding: 0 1px;
  border-radius: 3px;
  background: var(--accent-light);
  color: var(--accent);
  font-weight: 650;
}
</style>
