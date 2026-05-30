<template>
  <n-config-provider>
    <n-message-provider>
      <n-layout style="height: 100vh">
        <n-layout-header
          bordered
          style="
            padding: 8px 24px;
            display: flex;
            align-items: center;
            justify-content: space-between;
          "
        >
          <h2 style="margin: 0; font-size: 18px">Score Trans 五线谱 / 简谱互转</h2>
          <n-space>
            <n-tag :type="store.isBusy ? 'warning' : 'success'" size="small">
              {{ store.isBusy ? '处理中...' : '就绪' }}
            </n-tag>
          </n-space>
        </n-layout-header>
        <n-layout-content style="padding: 16px 24px; overflow-y: auto">
          <n-tabs type="line" animated>
            <n-tab-pane name="recognize" tab="图片/PDF 识别">
              <recognize-view />
            </n-tab-pane>
            <n-tab-pane name="convert" tab="简谱互转">
              <convert-view />
            </n-tab-pane>
            <n-tab-pane name="export" tab="导出">
              <export-view />
            </n-tab-pane>
            <n-tab-pane name="settings" tab="设置">
              <settings-view />
            </n-tab-pane>
          </n-tabs>
        </n-layout-content>
        <n-layout-footer bordered>
          <log-panel />
        </n-layout-footer>
      </n-layout>
    </n-message-provider>
  </n-config-provider>
</template>

<script setup lang="ts">
import { useTaskStore } from './stores/task'
import RecognizeView from './views/RecognizeView.vue'
import ConvertView from './views/ConvertView.vue'
import ExportView from './views/ExportView.vue'
import SettingsView from './views/SettingsView.vue'
import LogPanel from './components/LogPanel.vue'
import {
  NConfigProvider,
  NMessageProvider,
  NLayout,
  NLayoutHeader,
  NLayoutContent,
  NLayoutFooter,
  NTabs,
  NTabPane,
  NTag,
  NSpace,
} from 'naive-ui'

const store = useTaskStore()
</script>

<style>
body {
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Microsoft YaHei',
    sans-serif;
}
</style>
