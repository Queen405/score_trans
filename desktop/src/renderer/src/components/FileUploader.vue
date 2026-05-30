<template>
  <n-upload
    :custom-request="handleUpload"
    :show-file-list="false"
    :disabled="disabled"
    accept=".pdf,.png,.jpg,.jpeg,.tif,.tiff,.musicxml,.xml,.mxl,.txt"
    directory-dnd
    multiple
  >
    <n-upload-dragger class="upload-dragger">
      <div class="upload-content">
        <div class="upload-icon-ring">
          <n-icon size="30">
            <CloudUploadOutline />
          </n-icon>
        </div>
        <n-text class="upload-title">
          点击或拖拽文件到此处（支持多选）
        </n-text>
        <n-text depth="3" class="upload-subtitle">
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
  border-radius: 18px !important;
  border: 1px dashed rgba(94, 129, 172, 0.5) !important;
  transition: all 0.28s ease;
  background: linear-gradient(145deg, rgba(236, 239, 244, 0.4), rgba(216, 222, 233, 0.24)) !important;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.45);
}

.upload-dragger:hover {
  border-color: rgba(94, 129, 172, 0.88) !important;
  background: linear-gradient(145deg, rgba(229, 240, 249, 0.55), rgba(216, 222, 233, 0.35)) !important;
  transform: translateY(-1px);
}

.upload-content {
  padding: 26px 16px;
  text-align: center;
}

.upload-icon-ring {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 62px;
  height: 62px;
  border-radius: 17px;
  color: #2e3440;
  background: linear-gradient(140deg, rgba(136, 192, 208, 0.35), rgba(94, 129, 172, 0.28));
  border: 1px solid rgba(94, 129, 172, 0.42);
  box-shadow: 0 18px 36px -26px rgba(59, 66, 82, 0.7);
}

.upload-title {
  font-size: 16px;
  font-weight: 640;
  display: block;
  margin-top: 14px;
  color: #2e3440;
}

.upload-subtitle {
  font-size: 13px;
  display: block;
  margin-top: 8px;
}

:global(body.n-theme-dark) .upload-dragger {
  border-color: rgba(136, 192, 208, 0.55) !important;
  background: linear-gradient(145deg, rgba(46, 52, 64, 0.72), rgba(59, 66, 82, 0.6)) !important;
  box-shadow: inset 0 1px 0 rgba(236, 239, 244, 0.08);
}

:global(body.n-theme-dark) .upload-dragger:hover {
  border-color: rgba(136, 192, 208, 0.95) !important;
  background: linear-gradient(145deg, rgba(46, 52, 64, 0.84), rgba(67, 76, 94, 0.7)) !important;
}

:global(body.n-theme-dark) .upload-title {
  color: #eceff4;
}
</style>
