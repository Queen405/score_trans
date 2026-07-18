<template>
  <div class="upload-container">
    <n-upload
      ref="uploadRef"
      :custom-request="handleUpload"
      :show-file-list="false"
      :disabled="disabled || uploading"
      accept=".pdf,.png,.jpg,.jpeg,.tif,.tiff,.musicxml,.xml,.mxl,.txt"
      directory-dnd
      multiple
    >
      <n-upload-dragger class="upload-zone">
        <div class="upload-inner">
          <n-icon size="28">
            <CloudUploadOutline />
          </n-icon>
          <div class="upload-text">
            <span class="upload-title">{{ uploadStatusText }}</span>
            <span class="upload-hint">支持多选 · PDF / PNG / JPG / TIF / MusicXML</span>
          </div>
        </div>
      </n-upload-dragger>
    </n-upload>
    <n-progress
      v-if="uploading"
      type="line"
      :percentage="progress"
      :show-indicator="true"
      :indicator-placement="'inside'"
      :processing="phase === 'processing'"
      class="upload-progress"
    >
      {{ progress }}%
    </n-progress>
    <div
      v-if="uploadErrors.length"
      class="upload-errors"
      role="alert"
    >
      <div
        v-for="item in uploadErrors"
        :key="item"
      >
        {{ item }}
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { CloudUploadOutline } from '@vicons/ionicons5'
import { useFileUpload } from '../composables/useFileUpload'
import { useLogStore } from '../stores/log'
import { NUpload, NUploadDragger, NIcon, NProgress } from 'naive-ui'

const emit = defineEmits<{
  uploaded: [fileId: string, fileName: string]
}>()

defineProps<{
  disabled?: boolean
}>()

const { upload, uploading, progress, phase, error } = useFileUpload()
const log = useLogStore()
const uploadRef = ref<InstanceType<typeof NUpload> | null>(null)
const uploadErrors = ref<string[]>([])

const uploadQueue: File[] = []
let isProcessingQueue = false

const uploadStatusText = computed(() => {
  if (!uploading.value) return '点击或拖拽文件到此处'
  return phase.value === 'processing' ? '正在解析...' : '正在上传...'
})

async function handleUpload({ file }: { file: { file: File } }): Promise<void> {
  if (!isProcessingQueue && uploadQueue.length === 0) {
    uploadErrors.value = []
  }
  uploadQueue.push(file.file)
  if (isProcessingQueue) return
  await processUploadQueue()
}

async function processUploadQueue(): Promise<void> {
  isProcessingQueue = true
  try {
    while (uploadQueue.length > 0) {
      const currentFile = uploadQueue.shift()!
      log.addLog(`正在上传：${currentFile.name}`)
      const result = await upload(currentFile)
      if (result) {
        log.addLog(`上传成功：${result.filename}`)
        if (result.pages && result.pages.length > 0) {
          for (const page of result.pages) {
            emit('uploaded', page.file_id, page.filename)
          }
        } else {
          emit('uploaded', result.file_id, result.filename)
        }
      } else {
        const detail = error.value || '上传失败，请重试'
        const message = `${currentFile.name}：${detail}`
        uploadErrors.value = [...uploadErrors.value, message]
        log.addError(`上传失败：${message}`)
      }
    }
    uploadRef.value?.clear()
  } finally {
    isProcessingQueue = false
  }
}
</script>

<style scoped>
.upload-container {
  display: flex;
  flex-direction: column;
  gap: 4px;
  width: 100%;
  min-width: 0;
}

.upload-container :deep(.n-upload) {
  width: 100%;
}

.upload-zone {
  border-radius: var(--radius-lg) !important;
  border: 1.5px dashed var(--border) !important;
  background: var(--bg-elevated) !important;
  transition: border-color 0.2s ease, background-color 0.2s ease;
  min-height: 160px;
  display: flex !important;
  align-items: center;
  justify-content: center;
}

.upload-zone:hover {
  border-color: var(--accent) !important;
  background: var(--accent-light) !important;
}

.upload-inner {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-wrap: wrap;
  gap: 16px;
  width: 100%;
  min-width: 0;
  padding: 24px;
  color: var(--text-tertiary);
}

.upload-zone:hover .upload-inner {
  color: var(--accent);
}

.upload-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.upload-title {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
  line-height: 1.4;
}

.upload-hint {
  font-size: 12px;
  color: var(--text-tertiary);
  line-height: 1.4;
  white-space: normal;
}

.upload-progress {
  margin: 0;
}

.upload-errors {
  display: grid;
  gap: 2px;
  padding: 8px 10px;
  border: 1px solid var(--error-border, #dc2626);
  background: var(--error-light, #fef2f2);
  color: var(--error, #b91c1c);
  font-size: 12px;
  line-height: 1.4;
}

@media (max-width: 720px) {
  .upload-zone {
    min-height: 132px;
  }

  .upload-inner {
    flex-direction: column;
    gap: 8px;
    padding: 18px;
    text-align: center;
  }
}
</style>
