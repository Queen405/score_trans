<template>
  <n-upload
    :custom-request="handleUpload"
    :show-file-list="false"
    accept=".pdf,.png,.jpg,.jpeg,.tif,.tiff,.musicxml,.xml,.mxl,.txt"
    directory-dnd
  >
    <n-upload-dragger>
      <div style="padding: 16px; text-align: center">
        <n-icon size="48" :depth="3">
          <CloudUploadOutline />
        </n-icon>
        <n-text style="font-size: 16px; display: block; margin-top: 8px">
          点击或拖拽文件到此处
        </n-text>
        <n-p depth="3" style="margin: 8px 0 0 0; font-size: 12px">
          支持 PDF、PNG、JPG、TIF、MusicXML、MXL
        </n-p>
      </div>
    </n-upload-dragger>
  </n-upload>
</template>

<script setup lang="ts">
import { CloudUploadOutline } from '@vicons/ionicons5'
import { useFileUpload } from '../composables/useFileUpload'
import { useLogStore } from '../stores/log'
import { NUpload, NUploadDragger, NIcon, NText, NP } from 'naive-ui'

const emit = defineEmits<{
  uploaded: [fileId: string, fileName: string]
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
