<template>
  <div class="recognize-view">
    <!-- Upload area -->
    <n-card class="upload-card" :bordered="false">
      <div class="upload-section">
        <file-uploader :disabled="store.isBusy" @uploaded="onFileUploaded" />
      </div>

      <n-space class="action-bar" :size="10" wrap>
        <n-button
          type="primary"
          @click="recognize"
          :loading="store.isBusy"
          :disabled="store.isBusy || !store.hasInput"
          size="large"
        >
          <template #icon><n-icon><ScanOutline /></n-icon></template>
          识别为 MusicXML
        </n-button>
        <n-button
          type="info"
          @click="recognizeAndExport"
          :loading="store.isBusy"
          :disabled="store.isBusy || !store.hasInput"
          size="large"
        >
          <template #icon><n-icon><FlashOutline /></n-icon></template>
          一键识别并导出简谱
        </n-button>
        <n-button @click="openMusicXml" :disabled="store.isBusy" size="large" secondary>
          <template #icon><n-icon><DocumentAttachOutline /></n-icon></template>
          打开 MusicXML
        </n-button>
      </n-space>

      <transition name="fade">
        <div v-if="store.inputFileName" class="file-tag">
          <n-tag type="success" round :bordered="false" size="medium">
            <template #icon><n-icon><CheckmarkCircleOutline /></n-icon></template>
            已选择：{{ store.inputFileName }}
          </n-tag>
        </div>
      </transition>
    </n-card>

    <!-- MusicXML Preview -->
    <transition name="slide-fade">
      <n-card
        v-if="store.musicxmlText"
        title="📄 MusicXML 预览"
        class="preview-card"
        :bordered="false"
      >
        <template #header-extra>
          <n-tag size="small" :bordered="false" type="info">XML</n-tag>
        </template>
        <n-code :code="store.musicxmlText" language="xml" word-wrap />
      </n-card>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { useTaskStore } from '../stores/task'
import { useLogStore } from '../stores/log'
import { useSettingsStore } from '../stores/settings'
import { recognizeApi } from '../api/recognize'
import { pipelineApi } from '../api/pipeline'
import { historyApi } from '../api/history'
import { uploadFile, getFileURL } from '../api/client'
import FileUploader from '../components/FileUploader.vue'
import {
  ScanOutline,
  FlashOutline,
  DocumentAttachOutline,
  CheckmarkCircleOutline,
} from '@vicons/ionicons5'
import { NSpace, NButton, NTag, NCard, NCode, NIcon, useMessage } from 'naive-ui'

const store = useTaskStore()
const log = useLogStore()
const settings = useSettingsStore()
const message = useMessage()

async function onFileUploaded(fileId: string, fileName: string): Promise<void> {
  if (store.isBusy) return
  store.setInputFile(fileName, fileId)
}

async function recognize(): Promise<void> {
  const sourceFileId = store.inputFileId
  const sourceFileName = store.inputFileName
  if (!sourceFileId || !sourceFileName) return

  store.setBusy(true)
  try {
    const resp = await fetch(getFileURL(sourceFileId))
    const blob = await resp.blob()
    const result = await recognizeApi.recognize(
      new File([blob], sourceFileName),
      settings.targetKey,
      settings.startMeasureNumber ?? undefined,
    )
    store.setMusicxml(result.musicxml_file_id, '')
    setRecognizedOriginal(sourceFileName, sourceFileId)
    // Save to history
    await saveHistory(sourceFileName, sourceFileId, result.musicxml_file_id, '', '')
    log.addLog(`OMR 完成：${result.musicxml_filename}`)
    message.success('识别完成')
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e)
    log.addError(`识别失败：${msg}`)
    message.error(msg)
  } finally {
    store.setBusy(false)
  }
}

async function recognizeAndExport(): Promise<void> {
  const sourceFileId = store.inputFileId
  const sourceFileName = store.inputFileName
  if (!sourceFileId || !sourceFileName) return

  store.setBusy(true)
  try {
    const resp = await fetch(getFileURL(sourceFileId))
    const blob = await resp.blob()
    const result = await pipelineApi.run(
      new File([blob], sourceFileName),
      settings.targetKey,
      settings.startMeasureNumber ?? undefined,
    )
    store.setMusicxml(result.musicxml_file_id, '')
    setRecognizedOriginal(sourceFileName, sourceFileId)
    store.setJianpu(result.jianpu_text)
    store.setSvg(result.svg_file_id)
    // Save to history
    await saveHistory(sourceFileName, sourceFileId, result.musicxml_file_id, result.jianpu_text, result.svg_file_id)
    log.addLog('流水线完成')
    message.success('识别并导出完成')
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e)
    log.addError(`流水线失败：${msg}`)
    message.error(msg)
  } finally {
    store.setBusy(false)
  }
}

async function openMusicXml(): Promise<void> {
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = '.musicxml,.xml,.mxl'
  input.onchange = async () => {
    const file = input.files?.[0]
    if (!file) return
    store.setBusy(true)
    try {
      const result = await uploadFile(file)
      store.setInputFile(file.name, result.file_id)
      store.setMusicxml(result.file_id, '')
      store.clearOriginalFile()
      log.addLog(`已打开 MusicXML：${file.name}`)
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e)
      log.addError(`打开失败：${msg}`)
    } finally {
      store.setBusy(false)
    }
  }
  input.click()
}

function isPreviewableOriginal(fileName: string): boolean {
  return /\.(pdf|png|jpe?g|tiff?|webp)$/i.test(fileName)
}

function setRecognizedOriginal(fileName: string, fileId: string): void {
  if (isPreviewableOriginal(fileName)) {
    store.setOriginalFile(fileName, fileId)
  } else {
    store.clearOriginalFile()
  }
}

async function saveHistory(
  inputFileName: string,
  inputFileId: string,
  musicxmlFileId: string,
  jianpuText: string,
  svgFileId: string,
): Promise<void> {
  try {
    await historyApi.create({
      input_file_name: inputFileName,
      input_file_id: inputFileId,
      musicxml_file_id: musicxmlFileId,
      jianpu_text: jianpuText,
      svg_file_id: svgFileId,
      status: 'completed',
    })
  } catch {
    // Non-critical — don't block the user flow
    log.addLog('历史记录保存失败（不影响结果）')
  }
}
</script>

<style scoped>
.recognize-view {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.upload-card {
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
}

.upload-section {
  margin-bottom: 16px;
}

.action-bar {
  margin-bottom: 12px;
}

.file-tag {
  margin-top: 4px;
}

.preview-card {
  border-radius: 12px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
}

/* Transitions */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.slide-fade-enter-active {
  transition: all 0.35s ease-out;
}
.slide-fade-leave-active {
  transition: all 0.2s ease-in;
}
.slide-fade-enter-from {
  transform: translateY(10px);
  opacity: 0;
}
.slide-fade-leave-to {
  opacity: 0;
}
</style>
