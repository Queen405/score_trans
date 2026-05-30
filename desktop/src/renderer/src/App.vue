<template>
  <n-config-provider :theme-overrides="themeOverrides">
    <n-message-provider>
      <n-layout style="height: 100vh" class="app-shell">
        <!-- Header -->
        <n-layout-header bordered class="app-header">
          <div class="header-brand">
            <span class="brand-icon">🎵</span>
            <h2 class="brand-title">Score Trans</h2>
            <n-tag :bordered="false" size="small" type="info" round>五线谱 / 简谱</n-tag>
          </div>
          <n-space align="center" :size="12">
            <transition name="fade" mode="out-in">
              <n-tag
                v-if="store.isBusy"
                key="busy"
                type="warning"
                size="small"
                round
                :bordered="false"
              >
                <template #icon>
                  <n-icon><TimeOutline /></n-icon>
                </template>
                处理中…
              </n-tag>
              <n-tag
                v-else
                key="ready"
                type="success"
                size="small"
                round
                :bordered="false"
              >
                <template #icon>
                  <n-icon><CheckmarkCircleOutline /></n-icon>
                </template>
                就绪
              </n-tag>
            </transition>
          </n-space>
        </n-layout-header>

        <!-- Main content -->
        <n-layout-content class="app-content">
          <n-tabs
            type="line"
            animated
            size="large"
            class="main-tabs"
            @update:value="onTabChange"
          >
            <n-tab-pane name="recognize" tab="📷 识别">
              <recognize-view />
            </n-tab-pane>
            <n-tab-pane name="convert" tab="🔄 对照编辑">
              <convert-view />
            </n-tab-pane>
            <n-tab-pane name="export" tab="📤 导出">
              <export-view />
            </n-tab-pane>
            <n-tab-pane name="history" tab="📜 历史">
              <history-view />
            </n-tab-pane>
            <n-tab-pane name="settings" tab="⚙ 设置">
              <settings-view />
            </n-tab-pane>
          </n-tabs>
        </n-layout-content>

        <!-- Footer log -->
        <n-layout-footer bordered class="app-footer">
          <log-panel />
        </n-layout-footer>
      </n-layout>
    </n-message-provider>
  </n-config-provider>
</template>

<script setup lang="ts">
import type { GlobalThemeOverrides } from 'naive-ui'
import { useTaskStore } from './stores/task'
import RecognizeView from './views/RecognizeView.vue'
import ConvertView from './views/ConvertView.vue'
import ExportView from './views/ExportView.vue'
import HistoryView from './views/HistoryView.vue'
import SettingsView from './views/SettingsView.vue'
import LogPanel from './components/LogPanel.vue'
import { CheckmarkCircleOutline, TimeOutline } from '@vicons/ionicons5'
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
  NIcon,
} from 'naive-ui'

const store = useTaskStore()

function onTabChange(_name: string): void {
  // Future: lazy-load or refresh data on tab switch
}

const themeOverrides: GlobalThemeOverrides = {
  common: {
    primaryColor: '#4a9c6d',
    primaryColorHover: '#5cb87e',
    primaryColorPressed: '#3d8a5e',
    primaryColorSuppl: '#4a9c6d',
    borderRadius: '8px',
    borderRadiusSmall: '6px',
    fontFamily:
      "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'PingFang SC', 'Microsoft YaHei', sans-serif",
  },
  Button: {
    borderRadiusMedium: '8px',
    borderRadiusSmall: '6px',
  },
  Card: {
    borderRadius: '12px',
  },
  Tag: {
    borderRadius: '14px',
  },
  Input: {
    borderRadius: '8px',
  },
  Tabs: {
    tabTextColorLine: '#666',
    tabTextColorActiveLine: '#4a9c6d',
    tabTextColorHoverLine: '#5cb87e',
    barColor: '#4a9c6d',
  },
}
</script>

<style>
body {
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'PingFang SC',
    'Microsoft YaHei', sans-serif;
  background: #f5f7fa;
}

.app-shell {
  background: #f5f7fa;
}

.app-header {
  padding: 10px 28px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: linear-gradient(135deg, #ffffff 0%, #f0faf4 100%);
  border-bottom: 1px solid #e8efe9 !important;
  height: 56px;
  box-sizing: border-box;
}

.header-brand {
  display: flex;
  align-items: center;
  gap: 10px;
}

.brand-icon {
  font-size: 24px;
}

.brand-title {
  margin: 0;
  font-size: 20px;
  font-weight: 700;
  background: linear-gradient(135deg, #4a9c6d, #2d7d4f);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  letter-spacing: -0.5px;
}

.app-content {
  padding: 16px 28px 8px;
  overflow-y: auto;
}

.main-tabs {
  min-height: 0;
}

.main-tabs .n-tabs-pane-wrapper {
  padding-top: 8px;
}

.app-footer {
  border-top: 1px solid #e8efe9 !important;
  background: #fafcfb;
}

/* Transitions */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.25s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

/* Scrollbar */
::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}
::-webkit-scrollbar-track {
  background: transparent;
}
::-webkit-scrollbar-thumb {
  background: #c8d4cc;
  border-radius: 3px;
}
::-webkit-scrollbar-thumb:hover {
  background: #9db3a5;
}
</style>
