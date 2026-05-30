<template>
  <div class="convert-view">
    <section class="toolbar panel">
      <div class="panel-head">
        <div>
          <h3>对照编辑工作区</h3>
          <p>从识别到回转，统一在同一画布完成</p>
        </div>
        <div class="page-switcher" v-if="store.pageCount">
          <n-button size="small" secondary :disabled="!store.canPrevPage || store.isBusy" @click="store.prevPage()">
            上一页
          </n-button>
          <n-tag size="small" round :bordered="false" type="info">
            第 {{ store.currentPageIndex + 1 }} / {{ store.pageCount }} 页
          </n-tag>
          <n-button size="small" secondary :disabled="!store.canNextPage || store.isBusy" @click="store.nextPage()">
            下一页
          </n-button>
        </div>
      </div>
      <n-space :size="10" wrap class="toolbar-actions">
        <n-button
          class="tool-btn"
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
          class="tool-btn"
          @click="jianpuToMusicxml"
          :loading="store.isBusy"
          :disabled="!jianpuText"
          size="large"
          secondary
        >
          <template #icon><n-icon><ArrowBackOutline /></n-icon></template>
          简谱 → MusicXML
        </n-button>
        <n-button
          class="tool-btn"
          @click="saveJianpu"
          :disabled="!store.jianpuText && !store.pages.some((p) => !!p.jianpuText)"
          size="large"
          secondary
        >
          <template #icon><n-icon><DownloadOutline /></n-icon></template>
          {{ store.pageCount > 1 ? '保存全部简谱' : '保存简谱' }}
        </n-button>
        <n-button
          class="tool-btn"
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
    </section>

    <section class="editor-layout">
      <article class="left-panel">
        <n-card
          :title="store.originalFileName ? `原始五线谱 · ${store.originalFileName}` : '原始五线谱'"
          size="small"
          class="panel-card"
          :bordered="false"
        >
          <original-preview
            :file-id="store.originalFileId"
            :file-name="store.originalFileName"
          />
          <template #footer>
            <span class="panel-footnote">原图按容器自动缩放，完整可见</span>
          </template>
        </n-card>

      </article>

      <article class="right-panel">
        <n-card
          :title="isViewingFinal ? '最终渲染' : '简谱编辑'"
          size="small"
          class="panel-card"
          :bordered="false"
        >
          <template #header-extra>
            <n-button
              size="small"
              class="toggle-btn"
              @click="toggleFinalView"
              :loading="isRenderingFinal"
              :disabled="store.isBusy || (!store.hasMusicxml && !jianpuText)"
              secondary
              round
            >
              {{ isViewingFinal ? '编辑' : '渲染' }}
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
          <template #footer>
            <span class="panel-footnote">{{ isViewingFinal ? '渲染结果自动适配，无需滚动' : '编辑区按工作区高度自动铺满' }}</span>
          </template>
        </n-card>
      </article>
    </section>

  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { useTaskStore } from '../stores/task'
import { useSettingsStore } from '../stores/settings'
import { useLogStore } from '../stores/log'
import { convertApi } from '../api/convert'
import { renderApi } from '../api/render'
import { ApiError } from '../api/client'
import JianpuEditor from '../components/JianpuEditor.vue'
import OriginalPreview from '../components/OriginalPreview.vue'
import SvgPreview from '../components/SvgPreview.vue'
import {
  ArrowForwardOutline,
  ArrowBackOutline,
  DownloadOutline,
  ImageOutline,
} from '@vicons/ionicons5'
import { NSpace, NButton, NCard, NIcon, useMessage } from 'naive-ui'

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

function resolveMissingFileId(message: string): string | null {
  const match = message.match(/文件不存在[:：]\s*([A-Za-z0-9_-]+)/)
  return match?.[1] ?? null
}

function handleMissingMusicxml(errorMessage: string): string {
  const missingId = resolveMissingFileId(errorMessage)
  if (!missingId || missingId !== store.musicxmlFileId) {
    return errorMessage
  }

  store.setMusicxml('', store.musicxmlText)
  finalSvgFileId.value = ''
  return '当前 MusicXML 引用已失效，请回到“识别”页重新识别或重新打开 MusicXML 文件。'
}

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
    const raw = e instanceof Error ? e.message : String(e)
    const msg = e instanceof ApiError ? handleMissingMusicxml(raw) : raw
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
  const allTexts = store.pages
    .map((page, index) => ({
      index,
      name: page.inputFileName || `page-${index + 1}`,
      text: page.jianpuText,
    }))
    .filter((entry) => entry.text.trim().length > 0)

  const payload =
    allTexts.length > 1
      ? allTexts
          .map(
            (entry) =>
              `# Page ${entry.index + 1}: ${entry.name}\n${entry.text.trim()}`,
          )
          .join('\n\n')
      : (store.jianpuText || allTexts[0]?.text || '').trim()

  if (!payload) {
    message.warning('暂无可保存的简谱内容')
    return
  }

  const blob = new Blob([payload], { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = allTexts.length > 1 ? 'jianpu_pages.txt' : 'jianpu.txt'
  a.click()
  URL.revokeObjectURL(url)
  log.addLog(allTexts.length > 1 ? `已保存 ${allTexts.length} 页简谱文本` : '已保存简谱文本')
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
    const raw = e instanceof Error ? e.message : String(e)
    const msg = e instanceof ApiError ? handleMissingMusicxml(raw) : raw
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
    const raw = e instanceof Error ? e.message : String(e)
    const msg = e instanceof ApiError ? handleMissingMusicxml(raw) : raw
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
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.panel {
  border: 1px solid rgba(129, 161, 193, 0.24);
  background: linear-gradient(150deg, rgba(255, 255, 255, 0.76), rgba(236, 239, 244, 0.68));
  box-shadow: 0 30px 64px -54px rgba(46, 52, 64, 0.95);
  border-radius: 18px;
  padding: 16px;
  backdrop-filter: blur(10px);
}

.panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}

.page-switcher {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.panel-head h3 {
  margin: 0;
  font-size: 18px;
  color: #2e3440;
}

.panel-head p {
  margin: 3px 0 0;
  font-size: 12px;
  color: #5f6879;
}

.toolbar-actions {
  width: 100%;
}

.tool-btn {
  min-width: 138px;
  border-radius: 12px;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.tool-btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 18px 34px -28px rgba(46, 52, 64, 0.9);
}

.editor-layout {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(380px, 1fr) minmax(380px, 1fr);
  gap: 16px;
}

.left-panel {
  min-width: 340px;
  display: flex;
}

.right-panel {
  min-width: 340px;
  display: flex;
}

.panel-card {
  height: 100%;
  min-height: 0;
  width: 100%;
  border-radius: 18px;
  border: 1px solid rgba(129, 161, 193, 0.24);
  background: linear-gradient(150deg, rgba(255, 255, 255, 0.74), rgba(236, 239, 244, 0.64));
  box-shadow: 0 30px 64px -54px rgba(46, 52, 64, 0.95);
}

.panel-card :deep(.n-card__content) {
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.panel-card :deep(.n-card__footer) {
  padding-top: 8px;
}

.panel-footnote {
  font-size: 12px;
  color: #5f6879;
}

.toggle-btn {
  border-radius: 999px;
}

.xml-preview {
  max-height: 320px;
  overflow-y: auto;
  font-size: 12px;
}

.empty-hint {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 40px 0;
  text-align: center;
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

:global(body.n-theme-dark) .panel,
:global(body.n-theme-dark) .panel-card {
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

:global(body.n-theme-dark) .panel-footnote {
  color: #c7cfdd;
}

@media (max-width: 1100px) {
  .editor-layout {
    grid-template-columns: 1fr;
    overflow-y: auto;
  }

  .left-panel,
  .right-panel {
    min-width: 0;
  }

  .panel-card {
    min-height: 360px;
  }
}

@media (max-width: 920px) {
  .panel-head {
    flex-direction: column;
    align-items: flex-start;
  }

  .page-switcher {
    width: 100%;
    justify-content: space-between;
  }

  .tool-btn {
    min-width: 100%;
  }
}
</style>
