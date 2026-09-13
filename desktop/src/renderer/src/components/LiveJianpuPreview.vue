<template>
  <div ref="rootRef" class="live-preview">
    <div v-if="svg" ref="hostRef" class="live-svg" v-html="safeSvg" />
    <div v-else class="live-status">{{ loading ? '渲染中…' : '输入简谱后自动预览当前小节' }}</div>
    <div v-if="loading && svg" class="live-loading" role="status">渲染中…</div>
    <div v-if="error" class="live-error" role="status">
      <span v-if="svg">显示上次成功预览。 </span>{{ error }}
    </div>
    <div v-else-if="warnings?.length" class="live-warning" role="status">
      <div v-for="warning in warnings" :key="warning.id">{{ warning.message }}</div>
    </div>
  </div>
</template>
<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from "vue"
import type { SyntaxDiagnostic } from '../models/types'
import { sanitizeSvg } from "../utils/svgSanitizer"

const props = defineProps<{ svg: string; loading?: boolean; error?: string; warnings?: SyntaxDiagnostic[] }>()
const safeSvg = computed(() => sanitizeSvg(props.svg).outerHTML)
const rootRef = ref<HTMLDivElement | null>(null)
const hostRef = ref<HTMLDivElement | null>(null)

const CONTENT_PADDING = 12

interface ContentBox {
  x: number
  y: number
  width: number
  height: number
}

function contentBBox(svg: SVGSVGElement): ContentBox | null {
  const content = svg.querySelector<SVGGElement>(".publication-content")
  if (!content) return null
  const svgRect = svg.getBoundingClientRect()
  const rect = content.getBoundingClientRect()
  if (svgRect.width <= 0 || svgRect.height <= 0 || rect.width <= 0 || rect.height <= 0) {
    return null
  }
  const viewBox = svg.viewBox.baseVal
  if (viewBox.width <= 0 || viewBox.height <= 0) return null
  const kx = viewBox.width / svgRect.width
  const ky = viewBox.height / svgRect.height
  return {
    x: (rect.left - svgRect.left) * kx,
    y: (rect.top - svgRect.top) * ky,
    width: rect.width * kx,
    height: rect.height * ky,
  }
}

function fitSvg(): void {
  const root = rootRef.value
  const svg = hostRef.value?.querySelector("svg")
  if (!root || !svg || svg.hasAttribute("data-live-fit")) return
  for (const chrome of Array.from(
    svg.querySelectorAll(".page-background, .page-number, text[opacity='0']"),
  )) {
    chrome.remove()
  }
  const bbox = contentBBox(svg)
  if (!bbox) return
  const width = bbox.width + CONTENT_PADDING * 2
  const height = bbox.height + CONTENT_PADDING * 2
  svg.setAttribute(
    "viewBox",
    `${bbox.x - CONTENT_PADDING} ${bbox.y - CONTENT_PADDING} ${width} ${height}`,
  )
  svg.setAttribute("width", `${width}`)
  svg.setAttribute("height", `${height}`)
  svg.setAttribute("data-live-fit", "")
}

watch(() => [props.svg, props.loading], () => { void nextTick(fitSvg) })
onMounted(() => { void nextTick(fitSvg) })
</script>
<style scoped>
.live-preview {
  position: relative;
  height: 100%;
  overflow: hidden;
  background: var(--panel-bg, #fff);
}

.live-svg {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.live-svg:deep(svg) {
  display: block;
  flex: none;
}

.live-status {
  height: 100%;
  display: grid;
  place-items: center;
  color: var(--text-tertiary);
}

.live-loading {
  position: absolute;
  top: 6px;
  right: 10px;
  color: var(--text-tertiary);
  font-size: 12px;
}

.live-error, .live-warning {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  padding: 6px 10px;
  background: rgba(180, 40, 40, .12);
  color: #c0392b;
  font-size: 12px;
}
.live-warning {
  background: rgba(170, 110, 0, .12);
  color: #946000;
}
</style>
