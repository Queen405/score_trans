<template>
  <div class="convert-view">
    <!-- Toolbar -->
    <div class="toolbar">
      <n-space :size="10" wrap>
        <n-button
          type="primary"
          @click="musicxmlToJianpu"
          :loading="store.isBusy"
          :disabled="!store.hasMusicxml"
          size="large"
        >
          <template #icon><n-icon><ArrowForwardOutline /></n-icon></template>
          MusicXML → 简谱
        </n-button>
        <n-button
          @click="jianpuToMusicxml"
          :loading="store.isBusy"
          :disabled="!jianpuText"
          size="large"
          secondary
        >
          <template #icon><n-icon><ArrowBackOutline /></n-icon></template>
          简谱 → MusicXML
        </n-button>
        <n-button @click="saveJianpu" :disabled="!store.jianpuText" size="large" secondary>
          <template #icon><n-icon><DownloadOutline /></n-icon></template>
          保存简谱
        </n-button>
        <n-button
          type="info"
          @click="renderSvg"
          :loading="store.isBusy"
          :disabled="!store.hasMusicxml"
          size="large"
          secondary
        >
          <template #icon><n-icon><ImageOutline /></n-icon></template>
          导出 SVG
        </n-button>
      </n-space>
    </div>

    <!-- Split view -->
    <div class="editor-layout">
      <!-- Left panel: score preview -->
      <div class="left-panel">
        <n-card
          :title="store.originalFileName ? `🎼 ${store.originalFileName}` : '🎼 原始五线谱'"
          size="small"
          class="panel-card"
          :bordered="false"
        >
          <original-preview
            :file-id="store.originalFileId"
            :file-name="store.originalFileName"
          />
        </n-card>

        <n-card title="📄 MusicXML" size="small" class="panel-card" :bordered="false">
          <div v-if="store.musicxmlText" class="xml-preview">
            <n-code :code="store.musicxmlText" language="xml" word-wrap />
          </div>
          <div v-else class="empty-hint">
            <n-icon size="40" :depth="3"><DocumentTextOutline /></n-icon>
            <n-text depth="3">请先识别或打开 MusicXML</n-text>
          </div>
        </n-card>
      </div>

      <!-- Right panel: jianpu editor -->
      <div class="right-panel">
        <n-card
          :title="isViewingFinal ? '🖼️ 最终渲染' : '📝 简谱编辑'"
          size="small"
          class="panel-card"
          :bordered="false"
        >
          <template #header-extra>
            <n-button
              size="small"
              @click="toggleFinalView"
              :loading="isRenderingFinal"
              :disabled="store.isBusy || (!store.hasMusicxml && !jianpuText)"
              secondary
              round
            >
              {{ isViewingFinal ? '📝 编辑' : '🖼️ 渲染' }}
            </n-button>
          </template>

          <svg-preview
            v-if="isViewingFinal && finalSvgFileId"
            :svg-file-id="finalSvgFileId"
          />
          <div v-else-if="isViewingFinal" class="empty-hint">
            <n-icon size="40" :depth="3"><ImageOutline /></n-icon>
            <n-text depth="3">暂无渲染结果</n-text>
          </div>
          <jianpu-editor v-else v-model="jianpuText" />
        </n-card>
      </div>
    </div>

    <!-- SVG preview below -->
    <transition name="slide-fade">
      <n-card
        v-if="store.svgFileId && !isViewingFinal"
        title="🖼️ 简谱谱面"
        class="svg-card"
        :bordered="false"
      >
        <svg-preview :svg-file-id="store.svgFileId" />
      </n-card>
    </transition>
  </div>
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
import {
  ArrowForwardOutline,
  ArrowBackOutline,
  DownloadOutline,
  ImageOutline,
  DocumentTextOutline,
} from '@vicons/ionicons5'
import { NSpace, NButton, NCard, NCode, NText, NIcon, useMessage } from 'naive-ui'

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
    message.success('转换完成')
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
    store.clearOriginalFile()
    log.addLog('已生成 MusicXML')
    message.success('转换完成')
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
  message.success('已保存')
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
    message.success('渲染完成')
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
.convert-view {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.toolbar {
  padding: 4px 0;
}

.editor-layout {
  display: flex;
  gap: 16px;
  min-height: 360px;
}

.left-panel {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.right-panel {
  flex: 1;
  min-width: 0;
}

.panel-card {
  border-radius: 12px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
  height: 100%;
}

.xml-preview {
  max-height: 320px;
  overflow-y: auto;
  font-size: 12px;
}

.empty-hint {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 40px 0;
  text-align: center;
}

.svg-card {
  border-radius: 12px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
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
