<template>
  <div class="svg-preview" v-if="svgUrl">
    <div ref="containerRef" class="preview-viewport">
      <div class="zp-inner">
        <img :src="svgUrl" :width="imgW" :height="imgH" @load="onImgLoad" />
      </div>
    </div>
    <div class="zoom-bar">
      <span class="zoom-label">{{ Math.round(zp.scale.value * 100) }}%</span>
      <button class="zoom-btn" @click="zp.reset()" title="适应窗口">适应</button>
    </div>
  </div>
  <div v-else class="svg-empty">
    <n-icon size="32" :depth="3"><ImageOutline /></n-icon>
    <span>暂无 SVG</span>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch, nextTick } from 'vue'
import { getFileURL } from '../api/client'
import { ImageOutline } from '@vicons/ionicons5'
import { NIcon } from 'naive-ui'
import { useZoomPan } from '../composables/useZoomPan'

const props = defineProps<{ svgFileId: string }>()
const svgUrl = computed(() => (props.svgFileId ? getFileURL(props.svgFileId) : ''))

const containerRef = ref<HTMLElement>()
const zp = useZoomPan(containerRef)
const imgW = ref(0)
const imgH = ref(0)

function onImgLoad(e: Event) {
  const img = e.target as HTMLImageElement
  if (img.naturalWidth > 0 && img.naturalHeight > 0) {
    imgW.value = img.naturalWidth
    imgH.value = img.naturalHeight
  }
  requestAnimationFrame(() => zp.fitToView())
}

watch(svgUrl, async (url) => {
  if (url) {
    imgW.value = 0
    imgH.value = 0
    await nextTick()
    zp.unbind()
    zp.bind()
  }
})

onMounted(() => {
  if (svgUrl.value) zp.bind()
})
onUnmounted(() => zp.unbind())
</script>

<style scoped>
.svg-preview {
  flex: 1;
  min-height: 0;
  display: flex;
  position: relative;
}

.preview-viewport {
  flex: 1;
  min-height: 0;
  overflow: hidden;
  border-radius: var(--radius-sm);
  background: var(--bg-surface);
  cursor: default;
  position: relative;
}

.zp-inner {
  position: absolute;
  top: 0;
  left: 0;
  display: inline-block;
}

.zp-inner img {
  display: block;
  max-width: none;
  max-height: none;
}

.svg-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: var(--text-tertiary);
  font-size: 13px;
}

.zoom-bar {
  position: absolute;
  bottom: 8px;
  right: 8px;
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 3px 6px;
  border-radius: 6px;
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.08);
  z-index: 5;
}

.zoom-label {
  font-size: 11px;
  color: var(--text-tertiary);
  min-width: 32px;
  text-align: center;
  font-variant-numeric: tabular-nums;
}

.zoom-btn {
  border: 0;
  background: transparent;
  color: var(--text-secondary);
  font-size: 11px;
  cursor: pointer;
  padding: 2px 6px;
  border-radius: 4px;
}

.zoom-btn:hover {
  background: var(--accent-light);
  color: var(--accent);
}
</style>
