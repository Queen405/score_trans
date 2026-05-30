<template>
  <div class="original-preview">
    <div v-if="fileUrl && isPdf" class="pdf-frame">
      <iframe :src="fileUrl" :title="fileName" />
    </div>
    <div v-else-if="fileUrl && isImage" class="image-frame">
      <img :src="fileUrl" :alt="fileName" />
    </div>
    <div v-else class="empty-hint">
      <n-text depth="3">上传图片或 PDF 后在此对照原始五线谱</n-text>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { getFileURL } from '../api/client'
import { NText } from 'naive-ui'

const props = defineProps<{
  fileId: string
  fileName: string
}>()

const fileUrl = computed(() => (props.fileId ? getFileURL(props.fileId) : ''))
const extension = computed(() => props.fileName.split('.').pop()?.toLowerCase() ?? '')
const isPdf = computed(() => extension.value === 'pdf')
const isImage = computed(() => ['png', 'jpg', 'jpeg', 'tif', 'tiff', 'webp'].includes(extension.value))
</script>

<style scoped>
.original-preview {
  min-height: 260px;
}
.pdf-frame,
.image-frame {
  height: 360px;
  overflow: auto;
  border: 1px solid #e0e0e0;
  border-radius: 4px;
  background: #f7f7f7;
}
.pdf-frame iframe {
  width: 100%;
  height: 100%;
  border: 0;
}
.image-frame img {
  display: block;
  max-width: 100%;
  height: auto;
  margin: 0 auto;
}
.empty-hint {
  padding: 40px 16px;
  text-align: center;
}
</style>
