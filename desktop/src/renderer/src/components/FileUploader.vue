<template>
  <n-upload
    :custom-request="handleUpload"
    :show-file-list="false"
    :disabled="disabled"
    accept=".pdf,.png,.jpg,.jpeg,.tif,.tiff,.musicxml,.xml,.mxl,.txt"
    directory-dnd
  >
    <n-upload-dragger class="upload-dragger">
      <div class="upload-content">
        <div class="upload-icon-ring">
          <n-icon size="32" color="#4a9c6d">
            <CloudUploadOutline />
          </n-icon>
        </div>
        <n-text class="upload-title" style="font-size: 16px; font-weight: 600; display: block; margin-top: 12px">
          点击或拖拽文件到此处
        </n-text>
        <n-text depth="3" style="font-size: 13px; display: block; margin-top: 6px">
          支持 PDF、PNG、JPG、TIF、MusicXML、MXL
        </n-text>
      </div>
    </n-upload-dragger>
  </n-upload>
</template>

<script setup lang="ts">
import { CloudUploadOutline } from '@vicons/ionicons5'
import { useFileUpload } from '../composables/useFileUpload'
import { useLogStore } from '../stores/log'
import { NUpload, NUploadDragger, NIcon, NText } from 'naive-ui'

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
.upload-dragger {
  border-radius: 12px !important;
  border: 2px dashed #c8d4cc !important;
  transition: all 0.25s ease;
  background: #f9fcfa !important;
}

.upload-dragger:hover {
  border-color: #4a9c6d !important;
  background: #f0faf4 !important;
}

.upload-content {
  padding: 24px 16px;
  text-align: center;
}

.upload-icon-ring {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 64px;
  height: 64px;
  border-radius: 50%;
  background: linear-gradient(135deg, #e8f5ed, #d4edde);
}
</style>
