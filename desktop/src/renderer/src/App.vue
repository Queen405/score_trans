<template>
  <n-config-provider :theme="naiveTheme" :theme-overrides="themeOverrides">
    <n-message-provider>
      <n-layout style="height: 100vh" :class="['app-shell', prefersDark ? 'theme-dark' : 'theme-light']">
        <div class="aurora-layer" aria-hidden="true">
          <span class="aurora-orb orb-1"></span>
          <span class="aurora-orb orb-2"></span>
          <span class="aurora-grid"></span>
        </div>

        <n-layout-header bordered class="app-header">
          <div class="titlebar" role="banner">
            <div class="titlebar-drag-region">
              <div class="header-brand">
                <div class="brand-glyph" aria-hidden="true">♪</div>
                <div class="brand-copy">
                  <h2 class="brand-title">Score Trans</h2>
                  <p class="brand-subtitle">Nord Echo Workspace</p>
                </div>
                <n-tag :bordered="false" size="small" type="info" round>五线谱 / 简谱</n-tag>
              </div>
            </div>
            <div class="titlebar-actions">
              <n-space align="center" :size="10" class="status-strip">
                <n-tag :bordered="false" size="small" round class="active-view-tag">
                  当前：{{ currentTabLabel }}
                </n-tag>
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

              <div class="window-controls" role="group" aria-label="窗口控制">
                <button class="window-control-btn" type="button" aria-label="最小化" @click="minimizeWindow">
                  <RemoveOutline />
                </button>
                <button
                  class="window-control-btn"
                  type="button"
                  :aria-label="isMaximized ? '还原' : '最大化'"
                  @click="toggleMaximizeWindow"
                >
                  <ExpandOutline v-if="!isMaximized" />
                  <ContractOutline v-else />
                </button>
                <button class="window-control-btn close-btn" type="button" aria-label="关闭" @click="closeWindow">
                  <CloseOutline />
                </button>
              </div>
            </div>
          </div>
        </n-layout-header>

        <n-layout-content class="app-content">
          <div class="content-shell">
            <n-tabs
              v-model:value="activeTab"
              type="line"
              animated
              size="large"
              class="main-tabs"
              @update:value="onTabChange"
            >
              <n-tab-pane name="recognize">
                <template #tab>
                  <span class="tab-label"><n-icon><ScanOutline /></n-icon><span>识别</span></span>
                </template>
              <recognize-view />
            </n-tab-pane>
              <n-tab-pane name="convert">
                <template #tab>
                  <span class="tab-label"><n-icon><SyncOutline /></n-icon><span>对照编辑</span></span>
                </template>
              <convert-view />
            </n-tab-pane>
              <n-tab-pane name="export">
                <template #tab>
                  <span class="tab-label"><n-icon><DownloadOutline /></n-icon><span>导出</span></span>
                </template>
              <export-view />
            </n-tab-pane>
              <n-tab-pane name="history">
                <template #tab>
                  <span class="tab-label"><n-icon><TimeOutline /></n-icon><span>历史</span></span>
                </template>
              <history-view />
            </n-tab-pane>
              <n-tab-pane name="settings">
                <template #tab>
                  <span class="tab-label"><n-icon><SettingsOutline /></n-icon><span>设置</span></span>
                </template>
              <settings-view />
            </n-tab-pane>
            </n-tabs>
          </div>
        </n-layout-content>

        <n-layout-footer bordered class="app-footer">
          <log-panel />
        </n-layout-footer>
      </n-layout>
    </n-message-provider>
  </n-config-provider>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import type { GlobalThemeOverrides } from 'naive-ui'
import { useTaskStore } from './stores/task'
import RecognizeView from './views/RecognizeView.vue'
import ConvertView from './views/ConvertView.vue'
import ExportView from './views/ExportView.vue'
import HistoryView from './views/HistoryView.vue'
import SettingsView from './views/SettingsView.vue'
import LogPanel from './components/LogPanel.vue'
import {
  CheckmarkCircleOutline,
  CloseOutline,
  ContractOutline,
  DownloadOutline,
  ExpandOutline,
  RemoveOutline,
  ScanOutline,
  SettingsOutline,
  SyncOutline,
  TimeOutline,
} from '@vicons/ionicons5'
import {
  darkTheme,
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
const activeTab = ref<'recognize' | 'convert' | 'export' | 'history' | 'settings'>('recognize')
const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
const prefersDark = ref(mediaQuery.matches)
const isMaximized = ref(false)
let removeMaximizedListener: (() => void) | null = null

function handleThemeChange(event: MediaQueryListEvent): void {
  prefersDark.value = event.matches
}

onMounted(() => {
  if (typeof mediaQuery.addEventListener === 'function') {
    mediaQuery.addEventListener('change', handleThemeChange)
    return
  }
  mediaQuery.addListener(handleThemeChange)

  window.api
    .isMaximized()
    .then((value) => {
      isMaximized.value = value
    })
    .catch(() => {
      isMaximized.value = false
    })
  removeMaximizedListener = window.api.onMaximizedChanged((value) => {
    isMaximized.value = value
  })
})

onUnmounted(() => {
  if (typeof mediaQuery.removeEventListener === 'function') {
    mediaQuery.removeEventListener('change', handleThemeChange)
    return
  }
  mediaQuery.removeListener(handleThemeChange)

  if (removeMaximizedListener) {
    removeMaximizedListener()
    removeMaximizedListener = null
  }
})

function minimizeWindow(): void {
  void window.api.minimizeWindow()
}

function toggleMaximizeWindow(): void {
  void window.api.toggleMaximizeWindow().then((value) => {
    isMaximized.value = value
  })
}

function closeWindow(): void {
  void window.api.closeWindow()
}

const naiveTheme = computed(() => (prefersDark.value ? darkTheme : null))
const currentTabLabel = computed(() => {
  const labels = {
    recognize: '识别',
    convert: '对照编辑',
    export: '导出',
    history: '历史',
    settings: '设置',
  }
  return labels[activeTab.value]
})

function onTabChange(_name: string): void {
  activeTab.value = _name as typeof activeTab.value
}

const lightThemeOverrides: GlobalThemeOverrides = {
  common: {
    primaryColor: '#5e81ac',
    primaryColorHover: '#6c92c1',
    primaryColorPressed: '#4b6c95',
    primaryColorSuppl: '#5e81ac',
    borderColor: '#d8dee9',
    borderRadius: '14px',
    borderRadiusSmall: '10px',
    fontFamily:
      "'Segoe UI Variable Text', 'PingFang SC', 'Microsoft YaHei', 'Noto Sans SC', sans-serif",
  },
  Layout: {
    color: 'transparent',
    textColor: '#2e3440',
    siderColor: 'transparent',
    headerColor: 'transparent',
    footerColor: 'transparent',
  },
  Button: {
    borderRadiusMedium: '12px',
    borderRadiusSmall: '10px',
    textColorHoverPrimary: '#ffffff',
    textColorPressedPrimary: '#ffffff',
  },
  Card: {
    borderRadius: '18px',
    color: '#ffffffcc',
    borderColor: '#d8dee999',
    boxShadow: '0 28px 60px -44px rgba(46, 52, 64, 0.6)',
  },
  Tag: {
    borderRadius: '999px',
  },
  Input: {
    borderRadius: '12px',
    color: '#f6f8fc',
  },
  Tabs: {
    tabTextColorLine: '#4c566a',
    tabTextColorActiveLine: '#2e3440',
    tabTextColorHoverLine: '#5e81ac',
    barColor: '#88c0d0',
  },
}

const darkThemeOverrides: GlobalThemeOverrides = {
  common: {
    primaryColor: '#88c0d0',
    primaryColorHover: '#9dd2e2',
    primaryColorPressed: '#6ea9bb',
    primaryColorSuppl: '#88c0d0',
    borderColor: '#3b4252',
    borderRadius: '14px',
    borderRadiusSmall: '10px',
    fontFamily:
      "'Segoe UI Variable Text', 'PingFang SC', 'Microsoft YaHei', 'Noto Sans SC', sans-serif",
  },
  Layout: {
    color: 'transparent',
    textColor: '#eceff4',
    siderColor: 'transparent',
    headerColor: 'transparent',
    footerColor: 'transparent',
  },
  Card: {
    borderRadius: '18px',
    color: '#2e3440d1',
    borderColor: '#434c5e',
    boxShadow: '0 32px 65px -52px rgba(0, 0, 0, 0.9)',
  },
  Input: {
    borderRadius: '12px',
    color: '#3b4252',
  },
  Tabs: {
    tabTextColorLine: '#d8dee9',
    tabTextColorActiveLine: '#eceff4',
    tabTextColorHoverLine: '#88c0d0',
    barColor: '#88c0d0',
  },
}

const themeOverrides = computed(() => (prefersDark.value ? darkThemeOverrides : lightThemeOverrides))
</script>

<style>
body {
  margin: 0;
  font-family: 'Segoe UI Variable Text', 'PingFang SC', 'Microsoft YaHei', 'Noto Sans SC', sans-serif;
}

.app-shell {
  position: relative;
  overflow: hidden;
  isolation: isolate;
}

.app-shell.theme-light {
  --shell-bg: radial-gradient(circle at 10% 12%, #f2f6ff 0%, #dfe8f2 35%, #d8dee9 100%);
  --panel-bg: linear-gradient(148deg, rgba(255, 255, 255, 0.78) 4%, rgba(236, 239, 244, 0.86) 96%);
  --panel-border: rgba(216, 222, 233, 0.95);
  --text-main: #2e3440;
  --text-soft: #4c566a;
  --header-bg: linear-gradient(140deg, rgba(250, 252, 255, 0.82), rgba(237, 242, 248, 0.9));
  --header-border: rgba(216, 222, 233, 0.95);
  --footer-bg: rgba(236, 239, 244, 0.82);
  --glow-1: rgba(136, 192, 208, 0.34);
  --glow-2: rgba(94, 129, 172, 0.2);
  --accent: #5e81ac;
}

.app-shell.theme-dark {
  --shell-bg: radial-gradient(circle at 12% 10%, #293140 0%, #252d3b 32%, #232731 100%);
  --panel-bg: linear-gradient(148deg, rgba(46, 52, 64, 0.82) 2%, rgba(59, 66, 82, 0.9) 98%);
  --panel-border: rgba(76, 86, 106, 0.9);
  --text-main: #eceff4;
  --text-soft: #d8dee9;
  --header-bg: linear-gradient(140deg, rgba(35, 40, 49, 0.9), rgba(46, 52, 64, 0.86));
  --header-border: rgba(67, 76, 94, 0.9);
  --footer-bg: rgba(35, 40, 49, 0.85);
  --glow-1: rgba(136, 192, 208, 0.24);
  --glow-2: rgba(129, 161, 193, 0.2);
  --accent: #88c0d0;
}

.aurora-layer {
  position: absolute;
  inset: 0;
  background: var(--shell-bg);
  z-index: -2;
}

.aurora-orb {
  position: absolute;
  display: block;
  border-radius: 999px;
  filter: blur(14px);
  opacity: 0.95;
  animation: drift 20s ease-in-out infinite;
}

.aurora-layer .orb-1 {
  width: 520px;
  height: 520px;
  top: -180px;
  right: -140px;
  background: var(--glow-1);
}

.aurora-layer .orb-2 {
  width: 420px;
  height: 420px;
  left: -120px;
  bottom: -170px;
  background: var(--glow-2);
  animation-delay: -7s;
}

.aurora-grid {
  position: absolute;
  inset: 0;
  background-image: linear-gradient(rgba(94, 129, 172, 0.04) 1px, transparent 1px),
    linear-gradient(90deg, rgba(94, 129, 172, 0.04) 1px, transparent 1px);
  background-size: 34px 34px;
  mask-image: radial-gradient(circle at center, black 32%, transparent 92%);
}

.app-shell :is(.n-layout-header, .n-layout-content, .n-layout-footer) {
  position: relative;
  z-index: 1;
}

.app-header {
  margin: 16px 18px 12px;
  padding: 10px 16px;
  display: flex;
  align-items: center;
  justify-content: stretch;
  background: var(--header-bg);
  border: 1px solid var(--header-border) !important;
  backdrop-filter: blur(16px);
  border-radius: 18px;
  min-height: 74px;
  box-sizing: border-box;
  box-shadow: 0 26px 58px -44px rgba(46, 52, 64, 0.65);
}

.titlebar {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 14px;
}

.titlebar-drag-region {
  flex: 1;
  min-width: 0;
  -webkit-app-region: drag;
  app-region: drag;
}

.titlebar-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  -webkit-app-region: no-drag;
  app-region: no-drag;
}

.header-brand {
  display: flex;
  align-items: center;
  gap: 12px;
}

.brand-glyph {
  width: 44px;
  height: 44px;
  border-radius: 14px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, rgba(136, 192, 208, 0.26), rgba(94, 129, 172, 0.34));
  color: var(--text-main);
  font-size: 23px;
  border: 1px solid color-mix(in srgb, var(--panel-border) 86%, transparent);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.3);
}

.brand-copy {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.brand-title {
  margin: 0;
  font-size: 22px;
  font-weight: 760;
  color: var(--text-main);
  letter-spacing: -0.4px;
}

.brand-subtitle {
  margin: 0;
  font-size: 11px;
  letter-spacing: 1.7px;
  text-transform: uppercase;
  color: color-mix(in srgb, var(--text-soft) 78%, transparent);
}

.status-strip {
  padding: 6px 8px;
  border-radius: 999px;
  border: 1px solid color-mix(in srgb, var(--panel-border) 92%, transparent);
  background: color-mix(in srgb, var(--panel-bg) 96%, transparent);
}

.window-controls {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 3px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--panel-bg) 98%, transparent);
  border: 1px solid color-mix(in srgb, var(--panel-border) 96%, transparent);
}

.window-control-btn {
  width: 30px;
  height: 30px;
  border: 0;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: var(--text-main);
  background: transparent;
  transition: background-color 0.18s ease, color 0.18s ease, transform 0.18s ease;
}

.window-control-btn:hover {
  background: color-mix(in srgb, var(--accent) 20%, transparent);
  transform: translateY(-1px);
}

.window-control-btn:active {
  transform: translateY(0);
}

.window-control-btn.close-btn:hover {
  background: rgba(208, 48, 80, 0.92);
  color: #ffffff;
}

.window-control-btn svg {
  width: 15px;
  height: 15px;
}

.active-view-tag {
  background: color-mix(in srgb, var(--accent) 15%, transparent) !important;
  color: var(--text-main) !important;
}

.app-content {
  padding: 2px 18px 10px;
  overflow-y: auto;
}

.content-shell {
  padding: 14px 18px 18px;
  border-radius: 24px;
  border: 1px solid var(--panel-border);
  background: var(--panel-bg);
  box-shadow: 0 32px 64px -50px rgba(32, 39, 50, 0.8), inset 0 1px 0 rgba(255, 255, 255, 0.35);
  backdrop-filter: blur(16px);
}

.main-tabs {
  min-height: 0;
}

.main-tabs .tab-label {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-weight: 580;
  letter-spacing: 0.1px;
}

.main-tabs .n-tabs-pane-wrapper {
  padding-top: 14px;
}

.app-footer {
  margin: 8px 18px 14px;
  padding: 4px 14px;
  border: 1px solid var(--panel-border) !important;
  border-radius: 18px;
  background: var(--footer-bg);
  backdrop-filter: blur(10px);
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.25s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}
::-webkit-scrollbar-track {
  background: transparent;
}

::-webkit-scrollbar-thumb {
  background: color-mix(in srgb, var(--accent) 45%, #a7b1c2);
  border-radius: 3px;
}

::-webkit-scrollbar-thumb:hover {
  background: color-mix(in srgb, var(--accent) 70%, #7d8898);
}

@media (max-width: 920px) {
  .app-header {
    height: auto;
    flex-direction: column;
    align-items: flex-start;
    gap: 10px;
  }

  .titlebar {
    flex-direction: column;
    align-items: stretch;
    gap: 8px;
  }

  .titlebar-drag-region {
    width: 100%;
  }

  .titlebar-actions {
    width: 100%;
    justify-content: space-between;
  }

  .status-strip {
    flex: 1;
  }

  .content-shell {
    padding: 12px 12px 16px;
    border-radius: 20px;
  }

  .app-content {
    padding: 2px 10px 8px;
  }

  .app-footer {
    margin: 8px 10px 12px;
  }
}

@keyframes drift {
  0%,
  100% {
    transform: translate3d(0, 0, 0) scale(1);
  }
  50% {
    transform: translate3d(0, 18px, 0) scale(1.03);
  }
}
</style>
