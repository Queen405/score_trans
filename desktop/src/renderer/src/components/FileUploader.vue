<template>
  <n-upload
    :custom-request="handleUpload"
    :show-file-list="false"
    :disabled="disabled"
    accept=".pdf,.png,.jpg,.jpeg,.tif,.tiff,.musicxml,.xml,.mxl,.txt"
    directory-dnd
    multiple
  >
    <n-upload-dragger class="upload-zone">
      <div class="upload-inner">
        <n-icon size="28"><CloudUploadOutline /></n-icon>
        <div class="upload-text">
          <span class="upload-title">点击或拖拽文件到此处</span>
          <span class="upload-hint">支持多选 · PDF / PNG / JPG / TIF / MusicXML</span>
        </div>
      </div>
    </n-upload-dragger>
  </n-upload>
</template>

<script setup lang="ts">
import { CloudUploadOutline } from '@vicons/ionicons5'
import { useFileUpload } from '../composables/useFileUpload'
import { useLogStore } from '../stores/log'
import { NUpload, NUploadDragger, NIcon } from 'naive-ui'

const emit = defineEmits<{
  uploaded: [fileId: string, fileName: string]
}>()

defineProps<{
  disabled?: boolean
}>()

const { upload } = useFileUpload()
const log = useLogStore()

async function handleUpload({ file }: { file: { file: File } }): Promise<void> {
  log.addLog(`正在上传：${file.file.name}`)
  const result = await upload(file.file)
  if (result) {
    log.addLog(`上传成功：${result.filename}`)
    emit('uploaded', result.file_id, result.filename)
  }
}
</script>

<style scoped>
.upload-zone {
  border-radius: var(--radius-lg) !important;
  border: 1.5px dashed var(--border) !important;
  background: var(--bg-elevated) !important;
  transition: border-color 0.2s ease, background-color 0.2s ease;
}

.upload-zone:hover {
  border-color: var(--accent) !important;
  background: var(--accent-light) !important;
}

.upload-inner {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 20px 24px;
  color: var(--text-tertiary);
}

.upload-zone:hover .upload-inner {
  color: var(--accent);
}

.upload-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.upload-title {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
}

.upload-hint {
  font-size: 12px;
  color: var(--text-tertiary);
}
</style>
