<template>
  <div class="original-preview">
    <div v-if="fileUrl && isPdf" class="pdf-frame">
      <iframe :src="pdfFitUrl" :title="fileName" />
    </div>
    <div v-else-if="fileUrl && isImage" class="image-frame">
      <img :src="fileUrl" :alt="fileName" />
    </div>
    <div v-else class="empty-hint">
      <n-icon size="48" :depth="3"><ImageOutline /></n-icon>
      <n-text depth="3" style="font-size: 13px">上传图片或 PDF 后在此对照原始五线谱</n-text>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { getFileURL } from '../api/client'
import { ImageOutline } from '@vicons/ionicons5'
import { NText, NIcon } from 'naive-ui'

const props = defineProps<{
  fileId: string
  fileName: string
}>()

const fileUrl = computed(() => (props.fileId ? getFileURL(props.fileId) : ''))
const pdfFitUrl = computed(() =>
  fileUrl.value ? `${fileUrl.value}#toolbar=0&navpanes=0&scrollbar=0&view=FitH` : '',
)
const extension = computed(() => props.fileName.split('.').pop()?.toLowerCase() ?? '')
const isPdf = computed(() => extension.value === 'pdf')
const isImage = computed(() => ['png', 'jpg', 'jpeg', 'tif', 'tiff', 'webp'].includes(extension.value))
</script>

<style scoped>
.original-preview {
  flex: 1;
  min-height: 0;
  display: flex;
}

.pdf-frame,
.image-frame {
  flex: 1;
  min-height: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  border: 1px solid rgba(129, 161, 193, 0.25);
  border-radius: 14px;
  background: linear-gradient(145deg, rgba(248, 250, 252, 0.82), rgba(236, 239, 244, 0.68));
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.5);
}

.pdf-frame iframe {
  width: 100%;
  height: 100%;
  border: 0;
}

.image-frame img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: contain;
  border-radius: 8px;
}

.empty-hint {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 40px 16px;
  text-align: center;
}

:global(body.n-theme-dark) .pdf-frame,
:global(body.n-theme-dark) .image-frame {
  border-color: rgba(129, 161, 193, 0.34);
  background: linear-gradient(145deg, rgba(46, 52, 64, 0.86), rgba(59, 66, 82, 0.74));
}
</style>
