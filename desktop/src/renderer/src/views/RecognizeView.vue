<template>
  <n-space vertical :size="16">
    <!-- ── 图片/PDF 识别 ── -->
    <n-space>
      <file-uploader @uploaded="onFileUploaded" />
      <n-button
        type="primary"
        @click="recognize"
        :loading="store.isBusy"
        :disabled="!store.hasInput"
      >
        识别为 MusicXML
      </n-button>
      <n-button
        type="info"
        @click="recognizeAndExport"
        :loading="store.isBusy"
        :disabled="!store.hasInput"
      >
        识别并导出简谱
      </n-button>
      <n-button @click="openMusicXml" :disabled="store.isBusy">
        直接打开 MusicXML
      </n-button>
    </n-space>

    <n-space align="center" v-if="store.inputFileName">
      <n-tag type="success">已选择：{{ store.inputFileName }}</n-tag>
    </n-space>

    <!-- ── OCR 文字层 ── -->
    <n-card title="OCR 文字层" size="small">
      <n-space vertical :size="12">
        <n-space align="center">
          <n-text>上传页面图片用于 OCR 文字提取</n-text>
        </n-space>
        <n-space>
          <n-button @click="pickOcrImage" :disabled="store.isBusy">
            选择页面图片
          </n-button>
          <n-tag v-if="ocrImageName" type="info" closable @close="clearOcrImage">
            {{ ocrImageName }}
          </n-tag>
        </n-space>
        <n-button
          type="warning"
          @click="renderWithOcr"
          :loading="store.isBusy"
          :disabled="!store.hasMusicxml || !ocrImageFileId"
        >
          OCR + 渲染简谱 SVG（保持原页面布局）
        </n-button>
      </n-space>
    </n-card>

    <!-- ── MusicXML 预览 ── -->
    <n-card title="MusicXML 预览" v-if="store.musicxmlText">
      <n-code :code="store.musicxmlText" language="xml" word-wrap />
    </n-card>
  </n-space>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useTaskStore } from '../stores/task'
import { useLogStore } from '../stores/log'
import { useSettingsStore } from '../stores/settings'
import { recognizeApi } from '../api/recognize'
import { pipelineApi } from '../api/pipeline'
import { uploadFile, getFileURL, apiFetch } from '../api/client'
import FileUploader from '../components/FileUploader.vue'
import { NSpace, NButton, NTag, NCard, NCode, NText, useMessage } from 'naive-ui'

const store = useTaskStore()
const log = useLogStore()
const settings = useSettingsStore()
const message = useMessage()

const ocrImageFileId = ref('')
const ocrImageName = ref('')

async function onFileUploaded(fileId: string, fileName: string): Promise<void> {
  store.setInputFile(fileName, fileId)
}

async function recognize(): Promise<void> {
  store.setBusy(true)
  try {
    const resp = await fetch(getFileURL(store.inputFileId))
    const blob = await resp.blob()
    const result = await recognizeApi.recognize(
      new File([blob], store.inputFileName),
      settings.targetKey,
      settings.startMeasureNumber ?? undefined,
    )
    store.setMusicxml(result.musicxml_file_id, '')
    log.addLog(`OMR 完成：${result.musicxml_filename}`)
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e)
    log.addError(`识别失败：${msg}`)
    message.error(msg)
  } finally {
    store.setBusy(false)
  }
}

async function recognizeAndExport(): Promise<void> {
  store.setBusy(true)
  try {
    const resp = await fetch(getFileURL(store.inputFileId))
    const blob = await resp.blob()
    const result = await pipelineApi.run(
      new File([blob], store.inputFileName),
      settings.targetKey,
      settings.startMeasureNumber ?? undefined,
    )
    store.setMusicxml(result.musicxml_file_id, '')
    store.setJianpu(result.jianpu_text)
    store.setSvg(result.svg_file_id)
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

async function pickOcrImage(): Promise<void> {
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = '.pdf,.png,.jpg,.jpeg,.tif,.tiff'
  input.onchange = async () => {
    const file = input.files?.[0]
    if (!file) return
    try {
      const result = await uploadFile(file)
      ocrImageFileId.value = result.file_id
      ocrImageName.value = file.name
      log.addLog(`已上传 OCR 页面图：${file.name}`)
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e)
      log.addError(`OCR 图片上传失败：${msg}`)
    }
  }
  input.click()
}

function clearOcrImage(): void {
  ocrImageFileId.value = ''
  ocrImageName.value = ''
}

async function renderWithOcr(): Promise<void> {
  store.setBusy(true)
  try {
    const result = await apiFetch<{ svg_file_id: string }>('/render/preserving-layout', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        musicxml_file_id: store.musicxmlFileId,
        page_image_file_id: ocrImageFileId.value,
        target_key: settings.targetKey,
        start_measure_number: settings.startMeasureNumber ?? undefined,
      }),
    })
    store.setSvg(result.svg_file_id)
    log.addLog('OCR + 渲染完成')
    message.success('OCR 渲染完成，请到"简谱互转"页查看 SVG')
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e)
    log.addError(`OCR 渲染失败：${msg}`)
    message.error(msg)
  } finally {
    store.setBusy(false)
  }
}
</script>
