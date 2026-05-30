<template>
  <div class="original-preview">
    <div v-if="fileUrl && isPdf" ref="containerRef" class="preview-viewport">
      <div class="zp-content">
        <iframe :src="pdfFitUrl" :title="fileName" />
      </div>
    </div>
    <div v-else-if="fileUrl && isImage" ref="containerRef" class="preview-viewport">
      <div class="zp-content">
        <img :src="fileUrl" :alt="fileName" />
      </div>
    </div>
    <div v-else class="empty-hint">
      <n-icon size="32" :depth="3"><ImageOutline /></n-icon>
      <span>上传图片或 PDF 后对照原始五线谱</span>
    </div>
    <div v-if="fileUrl" class="zoom-bar">
      <span class="zoom-label">{{ Math.round(zp.scale.value * 100) }}%</span>
      <button class="zoom-btn" @click="zp.reset()" title="重置">1:1</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { getFileURL } from '../api/client'
import { ImageOutline } from '@vicons/ionicons5'
import { NIcon } from 'naive-ui'
import { useZoomPan } from '../composables/useZoomPan'

const props = defineProps<{
  fileId: string
  fileName: string
}>()

const containerRef = ref<HTMLElement>()
const zp = useZoomPan(containerRef)

const fileUrl = computed(() => (props.fileId ? getFileURL(props.fileId) : ''))
const pdfFitUrl = computed(() =>
  fileUrl.value ? `${fileUrl.value}#toolbar=0&navpanes=0&scrollbar=0&view=FitH` : '',
)
const extension = computed(() => props.fileName.split('.').pop()?.toLowerCase() ?? '')
const isPdf = computed(() => extension.value === 'pdf')
const isImage = computed(() => ['png', 'jpg', 'jpeg', 'tif', 'tiff', 'webp'].includes(extension.value))

onMounted(() => zp.bind())
onUnmounted(() => zp.unbind())
</script>

<style scoped>
.original-preview {
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

.preview-viewport .zp-content {
  display: inline-block;
  min-width: 100%;
  min-height: 100%;
}

.preview-viewport .zp-content iframe {
  width: 100%;
  height: 100%;
  border: 0;
  min-height: 500px;
}

.preview-viewport .zp-content img {
  display: block;
  max-width: none;
  max-height: none;
}

.empty-hint {
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
