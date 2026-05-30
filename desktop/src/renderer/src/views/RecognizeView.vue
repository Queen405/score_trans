<template>
  <div class="recognize-view">
    <n-card class="upload-card" :bordered="false">
      <div class="panel-head">
        <div>
          <h3>智能识别入口</h3>
          <p>上传扫描页，快速得到 MusicXML 与简谱成果</p>
        </div>
        <div class="page-switcher" v-if="store.pageCount">
          <n-button size="small" secondary :disabled="!store.canPrevPage || store.isBusy" @click="store.prevPage()">
            上一页
          </n-button>
          <n-tag size="small" :bordered="false" round>
            第 {{ store.currentPageIndex + 1 }} / {{ store.pageCount }} 页
          </n-tag>
          <n-button size="small" secondary :disabled="!store.canNextPage || store.isBusy" @click="store.nextPage()">
            下一页
          </n-button>
        </div>
      </div>

      <div class="upload-section">
        <file-uploader :disabled="store.isBusy" @uploaded="onFileUploaded" />
      </div>

      <n-progress
        v-if="store.isBusy"
        type="line"
        :percentage="progressPercent"
        :indicator-placement="'inside'"
        processing
        class="process-progress"
      >
        {{ progressText }}
      </n-progress>

      <n-space class="action-bar" :size="10" wrap>
        <n-button
          class="action-btn"
          type="primary"
          @click="recognize"
          :loading="store.isBusy"
          :disabled="store.isBusy || !store.hasInput"
          size="large"
        >
          <template #icon><n-icon><ScanOutline /></n-icon></template>
          识别并自动填充对照编辑
        </n-button>
        <n-button
          class="action-btn"
          type="info"
          @click="recognizeAllPages"
          :loading="store.isBusy"
          :disabled="store.isBusy || !store.pageCount"
          size="large"
        >
          <template #icon><n-icon><FlashOutline /></n-icon></template>
          批量识别全部页面
        </n-button>
        <n-button class="action-btn" @click="openMusicXml" :disabled="store.isBusy" size="large" secondary>
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
          <n-tag v-if="store.currentPage?.status === 'failed'" type="error" round :bordered="false" size="medium">
            识别失败
          </n-tag>
          <n-tag v-else-if="store.currentPage?.status === 'completed'" type="info" round :bordered="false" size="medium">
            已生成简谱与渲染
          </n-tag>
        </div>
      </transition>
    </n-card>

    <transition name="slide-fade">
      <n-card
        v-if="store.musicxmlText"
        title="MusicXML 预览"
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
import { ref } from 'vue'
import { useTaskStore } from '../stores/task'
import { useLogStore } from '../stores/log'
import { useSettingsStore } from '../stores/settings'
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
import { NSpace, NButton, NTag, NCard, NCode, NIcon, NProgress, useMessage } from 'naive-ui'

const store = useTaskStore()
const log = useLogStore()
const settings = useSettingsStore()
const message = useMessage()
const progressPercent = ref(0)
const progressText = ref('等待开始')

async function onFileUploaded(fileId: string, fileName: string): Promise<void> {
  if (store.isBusy) return
  store.addInputPage(fileName, fileId)
  log.addLog(`已加入页面：${fileName}`)
}

function setProgress(percent: number, text: string): void {
  progressPercent.value = Math.max(0, Math.min(100, Math.round(percent)))
  progressText.value = text
}

async function runPipelineForPage(pageIndex: number): Promise<void> {
  const page = store.pages[pageIndex]
  if (!page?.inputFileId || !page.inputFileName) return

  store.selectPage(pageIndex)
  store.setCurrentPageStatus('processing')
  const sourceFileId = page.inputFileId
  const sourceFileName = page.inputFileName

  setProgress(8, `读取文件：${sourceFileName}`)
  const resp = await fetch(getFileURL(sourceFileId))
  const blob = await resp.blob()

  setProgress(24, '识别与转换中')
  const result = await pipelineApi.run(
    new File([blob], sourceFileName),
    settings.targetKey,
    settings.startMeasureNumber ?? undefined,
  )

  setProgress(82, '写入对照编辑结果')
  store.setMusicxml(result.musicxml_file_id, '')
  setRecognizedOriginal(sourceFileName, sourceFileId)
  store.setJianpu(result.jianpu_text)
  store.setSvg(result.svg_file_id)
  store.setCurrentPageStatus('completed')

  await saveHistory(sourceFileName, sourceFileId, result.musicxml_file_id, result.jianpu_text, result.svg_file_id)
  log.addLog(`识别完成：${sourceFileName}`)
}

async function recognize(): Promise<void> {
  const pageIndex = store.currentPageIndex
  if (pageIndex < 0 || !store.hasInput) return

  store.setBusy(true)
  try {
    setProgress(0, '准备识别')
    await runPipelineForPage(pageIndex)
    setProgress(100, '识别完成')
    message.success('已自动填充对照编辑并完成渲染')
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e)
    store.setCurrentPageStatus('failed', msg)
    log.addError(`识别失败：${msg}`)
    message.error(msg)
  } finally {
    store.setBusy(false)
  }
}

async function recognizeAllPages(): Promise<void> {
  const indexes = store.pages
    .map((page, index) => ({ page, index }))
    .filter((entry) => !!entry.page.inputFileId)
    .map((entry) => entry.index)
  if (!indexes.length) return

  store.setBusy(true)
  try {
    setProgress(0, '准备批量识别')
    for (let i = 0; i < indexes.length; i += 1) {
      const pageIndex = indexes[i]
      const start = (i / indexes.length) * 100
      const end = ((i + 1) / indexes.length) * 100
      setProgress(start, `处理第 ${i + 1} / ${indexes.length} 页`)
      try {
        await runPipelineForPage(pageIndex)
      } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : String(e)
        store.selectPage(pageIndex)
        store.setCurrentPageStatus('failed', msg)
        log.addError(`第 ${i + 1} 页失败：${msg}`)
      }
      setProgress(end, `已完成 ${i + 1} / ${indexes.length} 页`)
    }
    setProgress(100, '批量识别完成')
    message.success('批量识别完成，请在对照编辑中翻页查看')
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e)
    log.addError(`批量识别失败：${msg}`)
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
      const idx = store.addInputPage(file.name, result.file_id)
      store.selectPage(idx)
      store.setMusicxml(result.file_id, '')
      store.setCurrentPageStatus('completed')
      store.clearOriginalFile()
      log.addLog(`已打开 MusicXML：${file.name}`)
      message.success('已加入新页面')
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e)
      log.addError(`打开失败：${msg}`)
      message.error(msg)
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
    log.addLog('历史记录保存失败（不影响结果）')
  }
}
</script>

<style scoped>
.recognize-view {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.upload-card {
  border-radius: 18px;
  border: 1px solid rgba(129, 161, 193, 0.24);
  background: linear-gradient(150deg, rgba(255, 255, 255, 0.76), rgba(236, 239, 244, 0.68));
  box-shadow: 0 30px 64px -54px rgba(46, 52, 64, 0.95);
  backdrop-filter: blur(10px);
}

.panel-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 14px;
}

.page-switcher {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.panel-head h3 {
  margin: 0;
  font-size: 19px;
  color: #2e3440;
}

.panel-head p {
  margin: 5px 0 0;
  font-size: 13px;
  color: #5f6879;
}

.upload-section {
  margin-bottom: 18px;
}

.action-bar {
  margin-bottom: 10px;
}

.process-progress {
  margin: 8px 0 14px;
}

.action-btn {
  border-radius: 12px;
  min-width: 168px;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.action-btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 18px 34px -28px rgba(46, 52, 64, 0.9);
}

.file-tag {
  margin-top: 6px;
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.preview-card {
  border-radius: 18px;
  border: 1px solid rgba(129, 161, 193, 0.24);
  background: linear-gradient(150deg, rgba(255, 255, 255, 0.74), rgba(236, 239, 244, 0.64));
  box-shadow: 0 30px 64px -54px rgba(46, 52, 64, 0.95);
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

:global(body.n-theme-dark) .upload-card,
:global(body.n-theme-dark) .preview-card {
  border-color: rgba(129, 161, 193, 0.35);
  background: linear-gradient(150deg, rgba(46, 52, 64, 0.9), rgba(59, 66, 82, 0.8));
  box-shadow: 0 34px 70px -56px rgba(0, 0, 0, 0.95);
}

:global(body.n-theme-dark) .panel-head h3 {
  color: #eceff4;
}

:global(body.n-theme-dark) .panel-head p {
  color: #c7cfdd;
}

@media (max-width: 920px) {
  .action-btn {
    min-width: 100%;
  }
}
</style>
