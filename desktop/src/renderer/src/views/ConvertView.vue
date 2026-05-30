<template>
  <n-space vertical :size="16">
    <n-space>
      <n-button
        type="primary"
        @click="musicxmlToJianpu"
        :loading="store.isBusy"
        :disabled="!store.hasMusicxml"
      >
        MusicXML → 简谱
      </n-button>
      <n-button
        @click="jianpuToMusicxml"
        :loading="store.isBusy"
        :disabled="!jianpuText"
      >
        简谱 → MusicXML
      </n-button>
      <n-button @click="saveJianpu" :disabled="!store.jianpuText"> 保存简谱 </n-button>
      <n-button
        type="info"
        @click="renderSvg"
        :loading="store.isBusy"
        :disabled="!store.hasMusicxml"
      >
        导出简谱谱面 SVG
      </n-button>
    </n-space>

    <div class="editor-layout">
      <!-- 左侧：五线谱预览 -->
      <div class="left-panel">
        <n-card
          :title="store.originalFileName ? `原始五线谱：${store.originalFileName}` : '原始五线谱对照'"
          size="small"
          class="preview-card"
        >
          <original-preview
            :file-id="store.originalFileId"
            :file-name="store.originalFileName"
          />
        </n-card>

        <n-card title="五线谱 (MusicXML)" size="small" class="preview-card">
          <div v-if="store.musicxmlText" class="xml-preview">
            <n-code :code="store.musicxmlText" language="xml" word-wrap />
          </div>
          <div v-else class="empty-hint">
            <n-text depth="3">请先识别或打开 MusicXML 文件</n-text>
          </div>
        </n-card>
      </div>

      <!-- 右侧：简谱编辑 -->
      <div class="right-panel">
        <n-card :title="isViewingFinal ? '最终渲染' : '简谱编辑'" size="small">
          <template #header-extra>
            <n-button
              size="small"
              @click="toggleFinalView"
              :loading="isRenderingFinal"
              :disabled="store.isBusy || (!store.hasMusicxml && !jianpuText)"
            >
              {{ isViewingFinal ? '切回编辑' : '查看渲染' }}
            </n-button>
          </template>

          <svg-preview
            v-if="isViewingFinal && finalSvgFileId"
            :svg-file-id="finalSvgFileId"
          />
          <div v-else-if="isViewingFinal" class="empty-hint">
            <n-text depth="3">暂无最终渲染结果</n-text>
          </div>
          <jianpu-editor v-else v-model="jianpuText" />
        </n-card>
      </div>
    </div>

    <svg-preview v-if="store.svgFileId && !isViewingFinal" :svg-file-id="store.svgFileId" />
  </n-space>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { useTaskStore } from '../stores/task'
import { useSettingsStore } from '../stores/settings'
import { useLogStore } from '../stores/log'
import { convertApi } from '../api/convert'
import { renderApi } from '../api/render'
import JianpuEditor from '../components/JianpuEditor.vue'
import OriginalPreview from '../components/OriginalPreview.vue'
import SvgPreview from '../components/SvgPreview.vue'
import { NSpace, NButton, NCard, NCode, NText, useMessage } from 'naive-ui'

const store = useTaskStore()
const settings = useSettingsStore()
const log = useLogStore()
const message = useMessage()

const jianpuText = ref(store.jianpuText)
const isViewingFinal = ref(false)
const isRenderingFinal = ref(false)
const finalSvgFileId = ref(store.svgFileId)

watch(() => store.jianpuText, (v) => { jianpuText.value = v })
watch(jianpuText, (v) => { store.setJianpu(v) })
watch(() => store.svgFileId, (v) => { finalSvgFileId.value = v })

async function musicxmlToJianpu(): Promise<void> {
  store.setBusy(true)
  try {
    const result = await convertApi.musicxmlToJianpu({
      musicxml_file_id: store.musicxmlFileId,
      target_key: settings.targetKey,
      start_measure_number: settings.startMeasureNumber ?? undefined,
    })
    store.setJianpu(result.jianpu_text)
    log.addLog('已转换为简谱')
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e)
    log.addError(`转换失败：${msg}`)
    message.error(msg)
  } finally {
    store.setBusy(false)
  }
}

async function jianpuToMusicxml(): Promise<void> {
  store.setBusy(true)
  try {
    const result = await convertApi.jianpuToMusicxml({ jianpu_text: jianpuText.value })
    store.setMusicxml(result.musicxml_file_id, result.musicxml_text)
    log.addLog('已生成 MusicXML')
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e)
    log.addError(`转换失败：${msg}`)
    message.error(msg)
  } finally {
    store.setBusy(false)
  }
}

function saveJianpu(): void {
  const blob = new Blob([store.jianpuText], { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'jianpu.txt'
  a.click()
  URL.revokeObjectURL(url)
  log.addLog('已保存简谱文本')
}

async function renderSvg(): Promise<void> {
  store.setBusy(true)
  try {
    const result = await renderApi.jianpuSvg({
      musicxml_file_id: store.musicxmlFileId,
      target_key: settings.targetKey,
      start_measure_number: settings.startMeasureNumber ?? undefined,
    })
    store.setSvg(result.svg_file_id)
    log.addLog('已渲染简谱 SVG')
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e)
    log.addError(`渲染失败：${msg}`)
    message.error(msg)
  } finally {
    store.setBusy(false)
  }
}

async function toggleFinalView(): Promise<void> {
  if (isViewingFinal.value) {
    isViewingFinal.value = false
    return
  }

  isRenderingFinal.value = true
  store.setBusy(true)
  try {
    const result = store.hasMusicxml
      ? await renderApi.finalOutput({
          musicxml_file_id: store.musicxmlFileId,
          page_image_file_id: store.originalFileId || undefined,
          target_key: settings.targetKey,
          start_measure_number: settings.startMeasureNumber ?? undefined,
        })
      : await renderApi.jianpuTextSvg({
          jianpu_text: jianpuText.value,
          title: '简谱',
        })

    finalSvgFileId.value = result.svg_file_id
    store.setSvg(result.svg_file_id)
    isViewingFinal.value = true
    log.addLog(store.hasMusicxml ? '已生成最终渲染 SVG' : '已从简谱文本渲染 SVG')
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e)
    log.addError(`最终渲染失败：${msg}`)
    message.error(msg)
  } finally {
    store.setBusy(false)
    isRenderingFinal.value = false
  }
}
</script>

<style scoped>
.editor-layout {
  display: flex;
  gap: 16px;
  min-height: 300px;
}
.left-panel {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.right-panel {
  flex: 1;
  min-width: 0;
}
.preview-card {
  height: 100%;
}
.xml-preview {
  max-height: 320px;
  overflow-y: auto;
  font-size: 12px;
}
.empty-hint {
  padding: 40px 0;
  text-align: center;
}
</style>
