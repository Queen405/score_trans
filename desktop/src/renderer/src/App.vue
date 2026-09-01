<template>
  <n-config-provider
    :theme="naiveTheme"
    :theme-overrides="themeOverrides"
  >
    <n-message-provider>
      <div :class="['app-shell', effectiveDark ? 'theme-dark' : 'theme-light']">
        <div
          class="titlebar"
          role="banner"
        >
          <div class="titlebar-left">
            <img
              class="app-icon-img"
              src="./assets/icon.png"
              alt="Score Trans"
            >
            <span class="app-title">Score Trans</span>
          </div>
          <div class="titlebar-drag" />
          <div class="titlebar-right">
            <div
              class="window-controls"
              role="group"
              aria-label="窗口控制"
            >
              <button
                class="wc-btn"
                type="button"
                aria-label="最小化"
                @click="minimizeWindow"
              >
                <svg
                  width="10"
                  height="1"
                  viewBox="0 0 10 1"
                ><rect
                  width="10"
                  height="1"
                  fill="currentColor"
                /></svg>
              </button>
              <button
                class="wc-btn"
                type="button"
                :aria-label="isMaximized ? '还原' : '最大化'"
                @click="toggleMaximizeWindow"
              >
                <svg
                  v-if="!isMaximized"
                  width="10"
                  height="10"
                  viewBox="0 0 10 10"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="1.2"
                ><rect
                  x="0.6"
                  y="0.6"
                  width="8.8"
                  height="8.8"
                /></svg>
                <svg
                  v-else
                  width="10"
                  height="10"
                  viewBox="0 0 10 10"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="1.2"
                ><rect
                  x="2"
                  y="0"
                  width="8"
                  height="8"
                /><rect
                  x="0"
                  y="2"
                  width="8"
                  height="8"
                  fill="var(--bg-base)"
                /><rect
                  x="0"
                  y="2"
                  width="8"
                  height="8"
                /></svg>
              </button>
              <button
                class="wc-btn wc-close"
                type="button"
                aria-label="关闭"
                @click="closeWindow"
              >
                <svg
                  width="10"
                  height="10"
                  viewBox="0 0 10 10"
                  stroke="currentColor"
                  stroke-width="1.3"
                ><line
                  x1="0"
                  y1="0"
                  x2="10"
                  y2="10"
                /><line
                  x1="10"
                  y1="0"
                  x2="0"
                  y2="10"
                /></svg>
              </button>
            </div>
          </div>
        </div>

        <div class="app-body">
          <nav class="sidebar">
            <div class="sidebar-nav">
              <button
                v-for="item in navItems"
                :key="item.key"
                :class="['nav-btn', { active: activeTab === item.key }]"
                :title="item.label"
                @click="selectTab(item.key)"
              >
                <component :is="item.icon" />
              </button>
            </div>
            <div class="sidebar-footer">
              <div
                v-if="store.isBusy || store.backgroundTaskCount"
                class="busy-indicator"
                title="后台处理中…"
              />
            </div>
          </nav>

          <main class="main-area">
            <div :class="['main-content', { 'panel-active': activeTab === 'settings' || activeTab === 'syntax' }]">
              <recognize-view
                v-show="activeTab === 'recognize'"
                :active="activeTab === 'recognize'"
              />
              <convert-view
                v-show="activeTab === 'convert'"
                ref="convertViewRef"
              />
              <syntax-view v-show="activeTab === 'syntax'" />
              <settings-view
                v-show="activeTab === 'settings'"
                :active="activeTab === 'settings'"
                @close="leaveSettings"
              />
              <ai-assistant v-show="activeTab === 'convert'" />
            </div>
            <div :class="['log-drawer', { open: logOpen }]">
              <button
                class="log-toggle"
                @click="logOpen = !logOpen"
              >
                <svg
                  width="12"
                  height="12"
                  viewBox="0 0 12 12"
                  fill="currentColor"
                ><path d="M2 4l4 4 4-4" /></svg>
                <span>日志</span>
                <span
                  v-if="logStore.errorCount"
                  class="log-badge"
                >运行 {{ logStore.errorCount }}</span>
                <span
                  v-if="syntaxStore.errorCount"
                  class="log-badge"
                >语法报错{{ syntaxStore.errorCount }}</span>
                <span
                  v-if="syntaxStore.warningCount && !syntaxStore.hideWarnings"
                  class="log-badge syntax-badge"
                >时值警告{{ syntaxStore.warningCount }}</span>
              </button>
              <div class="log-body">
                <div class="log-columns">
                  <section class="log-column">
                    <div class="log-column-head">
                      <h3 class="log-column-title">
                        运行日志
                      </h3>
                      <button
                        class="log-clear-btn"
                        type="button"
                        :disabled="!logStore.entries.length"
                        title="清除运行日志"
                        @click="logStore.clear()"
                      >
                        清除
                      </button>
                    </div>
                    <log-panel />
                  </section>
                  <section class="log-column syntax-column">
                    <div class="log-column-head">
                      <h3 class="log-column-title">
                        语法检查
                      </h3>
                      <div
                        v-if="syntaxStore.errorCount || syntaxStore.warningCount"
                        class="syntax-summary"
                      >
                        <span
                          v-if="syntaxStore.errorCount"
                          class="syntax-summary-count error"
                        >{{ syntaxStore.errorCount }} 个错误</span>
                        <button
                          v-if="syntaxStore.warningCount"
                          type="button"
                          :aria-pressed="syntaxStore.hideWarnings"
                          :title="syntaxStore.hideWarnings ? '点击显示时值警告' : '点击隐藏时值警告'"
                          :class="['syntax-summary-count', 'warning', 'syntax-summary-toggle', { muted: syntaxStore.hideWarnings }]"
                          @click="syntaxStore.toggleHideWarnings()"
                        >
                          {{ syntaxStore.warningCount }} 个警告
                        </button>
                      </div>
                    </div>
                    <syntax-diagnostic-panel />
                  </section>
                </div>
              </div>
            </div>
          </main>
        </div>
      </div>

      <n-modal
        v-model:show="discardModalVisible"
        preset="card"
        class="discard-settings-modal"
        title="放弃未保存的更改？"
        :bordered="false"
        :mask-closable="false"
        :closable="false"
        @esc="continueEditingSettings"
      >
        <p class="discard-settings-copy">
          设置页中的修改还没有应用。放弃后，这些修改将无法恢复。
        </p>
        <template #footer>
          <div class="discard-settings-actions">
            <n-button @click="continueEditingSettings">
              继续编辑
            </n-button>
            <n-button
              type="error"
              secondary
              @click="discardSettingsChanges"
            >
              放弃更改
            </n-button>
          </div>
        </template>
      </n-modal>
      <n-modal
        v-model:show="closeConfirmVisible"
        preset="card"
        class="close-confirm-modal"
        :title="closeRequest?.intent === 'relaunch' ? '重启前保存更改？' : '关闭前保存更改？'"
        :bordered="false"
        :mask-closable="false"
        :closable="false"
        @esc="cancelCloseRequest"
      >
        <p class="close-confirm-copy">
          当前有更改尚未保存。
        </p>
        <p
          v-if="saveBeforeCloseBlocked"
          class="close-confirm-warning"
        >
          任务处理中，完成后可保存。
        </p>
        <p
          v-if="closeSaveError"
          class="close-confirm-error"
        >
          {{ closeSaveError }}
        </p>
        <template #footer>
          <div class="close-confirm-actions">
            <n-button @click="cancelCloseRequest">
              取消
            </n-button>
            <n-button
              type="error"
              secondary
              @click="discardAndClose"
            >
              {{ closeRequest?.intent === 'relaunch' ? '直接重启' : '直接关闭' }}
            </n-button>
            <n-button
              type="primary"
              :loading="closeSaving"
              :disabled="saveBeforeCloseBlocked"
              @click="saveAndClose"
            >
              {{ closeRequest?.intent === 'relaunch' ? '保存并重启' : '保存并关闭' }}
            </n-button>
          </div>
        </template>
      </n-modal>
    </n-message-provider>
  </n-config-provider>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import type { GlobalThemeOverrides } from 'naive-ui'
import { useWorkspaceStore } from './stores/workspace'
import { useLogStore } from './stores/log'
import { useSyntaxDiagnosticsStore } from './stores/syntaxDiagnostics'
import { useSettingsStore } from './stores/settings'
import { historyApi } from './api/history'
import { notifyHistoryUpdated } from './utils/historyEvents'
import { createWorkspacePersistence } from './utils/workspacePersistence'
import RecognizeView from './views/RecognizeView.vue'
import ConvertView from './views/ConvertView.vue'
import SyntaxView from './views/SyntaxView.vue'
import SettingsView from './views/SettingsView.vue'
import AiAssistant from './components/AiAssistant.vue'
import LogPanel from './components/LogPanel.vue'
import SyntaxDiagnosticPanel from './components/SyntaxDiagnosticPanel.vue'
import {
  BookOutline,
  ScanOutline,
  SyncOutline,
  SettingsOutline,
} from '@vicons/ionicons5'
import {
  darkTheme,
  NButton,
  NConfigProvider,
  NMessageProvider,
  NModal,
} from 'naive-ui'

type AppTab = 'recognize' | 'convert' | 'syntax' | 'settings'
type WorkspaceTab = Exclude<AppTab, 'settings'>
type PendingNavigation =
  | { kind: 'tab'; tab: AppTab }
  | { kind: 'close'; request: CloseRequest }
interface CloseRequest {
  requestId: number
  intent: 'close' | 'relaunch'
}

const store = useWorkspaceStore()
const logStore = useLogStore()
const syntaxStore = useSyntaxDiagnosticsStore()
const settings = useSettingsStore()
const workspacePersistence = createWorkspacePersistence(historyApi, notifyHistoryUpdated)

const activeTab = ref<AppTab>('recognize')
const previousWorkspaceTab = ref<WorkspaceTab>('recognize')
const discardModalVisible = ref(false)
const pendingNavigation = ref<PendingNavigation | null>(null)
const closeRequest = ref<CloseRequest | null>(null)
const convertViewRef = ref<{ flushPendingEdits: () => Promise<void> } | null>(null)
const closeConfirmVisible = ref(false)
const closeSaving = ref(false)
const closeSaveError = ref('')
const logOpen = ref(false)
const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
const systemPrefersDark = ref(mediaQuery.matches)
const isMaximized = ref(false)
let removeMaximizedListener: (() => void) | null = null
let removeCloseRequestedListener: (() => void) | null = null
const saveBeforeCloseBlocked = computed(() =>
  !closeSaving.value && (store.isBusy || store.backgroundTaskCount > 0),
)

const navItems = [
  { key: 'recognize' as const, label: '识别', icon: ScanOutline },
  { key: 'convert' as const, label: '工作台', icon: SyncOutline },
  { key: 'syntax' as const, label: '语法', icon: BookOutline },
  { key: 'settings' as const, label: '设置', icon: SettingsOutline },
]

const effectiveDark = computed(() => {
  if (settings.themeMode === 'system') return systemPrefersDark.value
  return settings.themeMode === 'dark'
})

function handleThemeChange(event: MediaQueryListEvent): void {
  systemPrefersDark.value = event.matches
}

onMounted(() => {
  if (typeof mediaQuery.addEventListener === 'function') {
    mediaQuery.addEventListener('change', handleThemeChange)
  } else {
    mediaQuery.addListener(handleThemeChange)
  }

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
  removeCloseRequestedListener = window.api.onCloseRequested(handleCloseRequested)
  void window.api.notifyCloseListenerReady()
})

onUnmounted(() => {
  if (typeof mediaQuery.removeEventListener === 'function') {
    mediaQuery.removeEventListener('change', handleThemeChange)
  } else {
    mediaQuery.removeListener(handleThemeChange)
  }

  if (removeMaximizedListener) {
    removeMaximizedListener()
    removeMaximizedListener = null
  }
  if (removeCloseRequestedListener) {
    removeCloseRequestedListener()
    removeCloseRequestedListener = null
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

function handleCloseRequested(request: CloseRequest): void {
  if (closeRequest.value) return
  if (settings.draftDirty) {
    pendingNavigation.value = { kind: 'close', request }
    discardModalVisible.value = true
    return
  }
  processCloseRequest(request)
}

function processCloseRequest(request: CloseRequest): void {
  if (!store.hasUnsavedChanges) {
    window.api.resolveCloseRequest(request.requestId, 'proceed')
    return
  }
  closeRequest.value = request
  closeSaveError.value = ''
  closeConfirmVisible.value = true
}

function cancelCloseRequest(): void {
  const request = closeRequest.value
  closeRequest.value = null
  closeConfirmVisible.value = false
  closeSaveError.value = ''
  if (request) window.api.resolveCloseRequest(request.requestId, 'cancel')
}

function discardAndClose(): void {
  const request = closeRequest.value
  if (!request) return
  closeConfirmVisible.value = false
  window.api.resolveCloseRequest(request.requestId, 'proceed')
}

async function saveAndClose(): Promise<void> {
  const request = closeRequest.value
  if (!request || saveBeforeCloseBlocked.value) return
  closeSaving.value = true
  closeSaveError.value = ''
  store.setBusy(true)
  try {
    // 先兑现待执行的异步编辑（自动转调），否则它会在保存的 await 窗口里
    // 把批次重新标脏，导致 saveAllUnsavedBatches 报「保存期间又改了」。
    await convertViewRef.value?.flushPendingEdits()
    await workspacePersistence.saveAllUnsavedBatches(store)
    closeConfirmVisible.value = false
    window.api.resolveCloseRequest(request.requestId, 'proceed')
  } catch (error: unknown) {
    const detail = error instanceof Error ? error.message : String(error)
    closeSaveError.value = `保存失败，已取消${request.intent === 'relaunch' ? '重启' : '关闭'}：${detail}`
    logStore.addError(closeSaveError.value)
  } finally {
    store.setBusy(false)
    closeSaving.value = false
  }
}

function selectTab(tab: AppTab): void {
  if (tab === activeTab.value) return
  if (activeTab.value === 'settings' && settings.draftDirty) {
    pendingNavigation.value = { kind: 'tab', tab }
    discardModalVisible.value = true
    return
  }
  activateTab(tab)
}

function activateTab(tab: AppTab): void {
  if (tab === 'settings') {
    if (activeTab.value !== 'settings') {
      previousWorkspaceTab.value = activeTab.value as WorkspaceTab
    }
  } else {
    previousWorkspaceTab.value = tab
  }
  activeTab.value = tab
}

function leaveSettings(): void {
  activateTab(previousWorkspaceTab.value)
}

function continueEditingSettings(): void {
  const navigation = pendingNavigation.value
  pendingNavigation.value = null
  discardModalVisible.value = false
  if (navigation?.kind === 'close') {
    window.api.resolveCloseRequest(navigation.request.requestId, 'cancel')
  }
}

function discardSettingsChanges(): void {
  const navigation = pendingNavigation.value
  settings.discardDraft()
  pendingNavigation.value = null
  discardModalVisible.value = false
  if (!navigation) return
  if (navigation.kind === 'close') {
    processCloseRequest(navigation.request)
    return
  }
  activateTab(navigation.tab)
}

const naiveTheme = computed(() => (effectiveDark.value ? darkTheme : null))

const lightThemeOverrides: GlobalThemeOverrides = {
  common: {
    primaryColor: '#4c6ef5',
    primaryColorHover: '#5c7aff',
    primaryColorPressed: '#3b5bdb',
    primaryColorSuppl: '#4c6ef5',
    borderColor: '#e9ecef',
    borderRadius: '8px',
    borderRadiusSmall: '6px',
    fontFamily: "'Segoe UI Variable Text', 'PingFang SC', 'Microsoft YaHei', sans-serif",
  },
  Card: {
    borderRadius: '10px',
    color: '#ffffff',
    borderColor: '#e9ecef',
    boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
  },
  Input: {
    borderRadius: '8px',
    color: '#f8f9fa',
    borderHover: '#4c6ef5',
    borderFocus: '#4c6ef5',
    boxShadowFocus: '0 0 0 2px rgba(76,110,245,0.15)',
  },
  Button: {
    borderRadiusMedium: '8px',
    borderRadiusSmall: '6px',
  },
  Tag: {
    borderRadius: '6px',
  },
  Tabs: {
    tabTextColorLine: '#868e96',
    tabTextColorActiveLine: '#212529',
    tabTextColorHoverLine: '#4c6ef5',
    barColor: '#4c6ef5',
  },
}

const darkThemeOverrides: GlobalThemeOverrides = {
  common: {
    primaryColor: '#748ffc',
    primaryColorHover: '#91a7ff',
    primaryColorPressed: '#5c7cfa',
    primaryColorSuppl: '#748ffc',
    borderColor: '#363a3f',
    borderRadius: '8px',
    borderRadiusSmall: '6px',
    fontFamily: "'Segoe UI Variable Text', 'PingFang SC', 'Microsoft YaHei', sans-serif",
  },
  Card: {
    borderRadius: '10px',
    color: '#1e2028',
    borderColor: '#2c2f36',
    boxShadow: '0 1px 3px rgba(0,0,0,0.2)',
  },
  Input: {
    borderRadius: '8px',
    color: '#25282e',
    borderHover: '#748ffc',
    borderFocus: '#748ffc',
    boxShadowFocus: '0 0 0 2px rgba(116,143,252,0.2)',
  },
  Button: {
    borderRadiusMedium: '8px',
    borderRadiusSmall: '6px',
  },
  Tag: {
    borderRadius: '6px',
  },
  Tabs: {
    tabTextColorLine: '#868e96',
    tabTextColorActiveLine: '#e9ecef',
    tabTextColorHoverLine: '#748ffc',
    barColor: '#748ffc',
  },
}

const themeOverrides = computed(() => (effectiveDark.value ? darkThemeOverrides : lightThemeOverrides))
</script>

<style>
*,
*::before,
*::after {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

body {
  overflow: hidden;
  font-family: 'Segoe UI Variable Text', 'PingFang SC', 'Microsoft YaHei', sans-serif;
}

::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}

::-webkit-scrollbar-track {
  background: transparent;
}

::-webkit-scrollbar-thumb {
  background: rgba(0, 0, 0, 0.15);
  border-radius: 3px;
}

::-webkit-scrollbar-thumb:hover {
  background: rgba(0, 0, 0, 0.25);
}

.app-shell {
  height: 100vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  --bg-base: #ffffff;
  --bg-surface: #f8f9fa;
  --bg-elevated: #ffffff;
  --bg-sidebar: #1a1d23;
  --border: #e9ecef;
  --border-light: #f1f3f5;
  --text-primary: #212529;
  --text-secondary: #495057;
  --text-tertiary: #868e96;
  --text-sidebar: #adb5bd;
  --text-sidebar-active: #ffffff;
  --accent: #4c6ef5;
  --accent-light: rgba(76, 110, 245, 0.08);
  --danger: #fa5252;
  --success: #40c057;
  --warning: #fab005;
  --radius-sm: 6px;
  --radius-md: 8px;
  --radius-lg: 10px;
}

.app-shell.theme-dark {
  --bg-base: #111318;
  --bg-surface: #181a20;
  --bg-elevated: #1e2028;
  --bg-sidebar: #0e1014;
  --border: #2c2f36;
  --border-light: #23262c;
  --text-primary: #e9ecef;
  --text-secondary: #adb5bd;
  --text-tertiary: #6c7278;
  --text-sidebar: #6c7278;
  --text-sidebar-active: #e9ecef;
  --accent: #748ffc;
  --accent-light: rgba(116, 143, 252, 0.1);
  --danger: #ff6b6b;
  --success: #51cf66;
  --warning: #fcc419;
}

.app-shell.theme-dark ::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.12);
}

.app-shell.theme-dark ::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.22);
}

.titlebar {
  height: 38px;
  display: flex;
  align-items: center;
  background: var(--bg-sidebar);
  color: #ced4da;
  font-size: 12px;
  -webkit-app-region: drag;
  app-region: drag;
  flex-shrink: 0;
  user-select: none;
  position: relative;
  z-index: 35;
}

.titlebar-left {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 12px;
  flex-shrink: 0;
}

.app-icon-img {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  object-fit: cover;
}

.app-title {
  font-weight: 600;
  font-size: 12px;
  color: #ced4da;
  letter-spacing: -0.2px;
}

.titlebar-drag {
  flex: 1;
  height: 100%;
}

.titlebar-right {
  flex-shrink: 0;
  -webkit-app-region: no-drag;
  app-region: no-drag;
}

.window-controls {
  display: flex;
  height: 38px;
}

.wc-btn {
  width: 46px;
  height: 38px;
  border: 0;
  background: transparent;
  color: #ced4da;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: background-color 0.12s ease;
}

.wc-btn:hover {
  background: rgba(255, 255, 255, 0.08);
  color: #fff;
}

.wc-close:hover {
  background: var(--danger);
  color: #fff;
}

.app-body {
  flex: 1;
  display: flex;
  min-height: 0;
  overflow: hidden;
}

.sidebar {
  width: 52px;
  background: var(--bg-sidebar);
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  flex-shrink: 0;
  border-right: 1px solid rgba(255, 255, 255, 0.04);
  position: relative;
  z-index: 35;
}

.sidebar-nav {
  display: flex;
  flex-direction: column;
  padding: 8px 6px;
  gap: 2px;
}

.sidebar-footer {
  padding: 8px 6px;
  display: flex;
  justify-content: center;
}

.busy-indicator {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--warning);
  animation: pulse 1.2s ease-in-out infinite;
}

.nav-btn {
  width: 40px;
  height: 40px;
  border: 0;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--text-sidebar);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.15s ease;
  font-size: 18px;
  position: relative;
}

.nav-btn:hover {
  background: rgba(255, 255, 255, 0.06);
  color: var(--text-sidebar-active);
}

.nav-btn.active {
  background: rgba(255, 255, 255, 0.1);
  color: var(--text-sidebar-active);
}

.nav-btn.active::before {
  content: '';
  position: absolute;
  left: -6px;
  top: 50%;
  transform: translateY(-50%);
  width: 3px;
  height: 18px;
  border-radius: 0 3px 3px 0;
  background: var(--accent);
}

.nav-btn svg {
  width: 20px;
  height: 20px;
}

.main-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  background: var(--bg-surface);
}

.main-content {
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding: 20px 24px;
}

.main-content.panel-active {
  display: flex;
  overflow: hidden;
  padding: 0;
}

.discard-settings-modal {
  width: min(440px, calc(100vw - 48px));
}

.close-confirm-modal {
  width: min(440px, calc(100vw - 48px));
}

.discard-settings-copy {
  margin: 0;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.7;
}

.discard-settings-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.close-confirm-copy,
.close-confirm-warning,
.close-confirm-error {
  margin: 0;
  font-size: 13px;
  line-height: 1.7;
}

.close-confirm-copy {
  color: var(--text-secondary);
}

.close-confirm-warning {
  margin-top: 8px;
  color: var(--warning);
}

.close-confirm-error {
  margin-top: 8px;
  color: var(--danger);
  overflow-wrap: anywhere;
}

.close-confirm-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  flex-wrap: wrap;
}

.log-drawer {
  flex-shrink: 0;
  border-top: 1px solid var(--border);
  background: var(--bg-elevated);
  max-height: 32px;
  overflow: hidden;
  transition: max-height 0.25s ease;
}

.log-drawer.open {
  max-height: 240px;
}

.log-toggle {
  display: flex;
  align-items: center;
  gap: 6px;
  width: 100%;
  height: 32px;
  padding: 0 16px;
  border: 0;
  background: transparent;
  color: var(--text-tertiary);
  font-size: 12px;
  cursor: pointer;
  transition: color 0.15s ease;
}

.log-toggle:hover {
  color: var(--text-secondary);
}

.log-drawer.open .log-toggle svg {
  transform: rotate(180deg);
}

.log-toggle svg {
  transition: transform 0.2s ease;
}

.log-badge {
  margin-left: 6px;
  background: var(--danger);
  color: #fff;
  font-size: 10px;
  font-weight: 600;
  padding: 1px 5px;
  border-radius: 9px;
  line-height: 1.3;
}

.syntax-badge {
  background: var(--warning);
}

.log-body {
  height: 208px;
  overflow-y: auto;
  border-top: 1px solid var(--border-light);
}

.log-columns {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  height: 100%;
}

.log-column {
  min-width: 0;
  overflow: hidden;
}

.syntax-column {
  border-left: 1px solid var(--border-light);
}

.syntax-column .log-column-head {
  padding-right: 4px;
}

.syntax-summary {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 2px 10px;
}

.syntax-summary-count {
  display: inline-flex;
  align-items: center;
  font-size: 11px;
  font-weight: 600;
  line-height: 1.5;
  padding: 2px 0;
}

.syntax-summary-count.error {
  color: var(--danger);
}

.syntax-summary-count.warning {
  color: var(--warning);
}

.syntax-summary-toggle {
  flex-shrink: 0;
  border: 0;
  background: transparent;
  padding: 2px 8px;
  border-radius: 4px;
  cursor: pointer;
  font-weight: 600;
  transition: background 0.15s ease;
}

.syntax-summary-toggle:hover:not(.muted) {
  background: var(--bg-hover, rgba(128, 128, 128, 0.12));
}

.syntax-summary-count.muted {
  opacity: 0.45;
}

.log-column-title {
  margin: 0;
  padding: 8px 16px 2px;
  color: var(--text-tertiary);
  font-size: 11px;
  font-weight: 600;
}

.log-column-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding-right: 8px;
}

.log-column-head .log-column-title {
  padding-right: 0;
}

.log-clear-btn {
  flex-shrink: 0;
  border: 0;
  background: transparent;
  color: var(--text-tertiary);
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 4px;
  cursor: pointer;
  transition: color 0.15s ease, background 0.15s ease;
}

.log-clear-btn:hover:not(:disabled) {
  color: var(--text-secondary);
  background: var(--bg-hover, rgba(128, 128, 128, 0.12));
}

.log-clear-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.log-column .log-panel {
  height: calc(100% - 28px);
  overflow-y: auto;
  padding: 4px 16px 8px;
}

.syntax-column :deep(.syntax-diagnostic-panel) {
  height: calc(100% - 28px);
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

@media (max-width: 768px) {
  .main-content {
    padding: 16px;
  }

  .log-body {
    height: 320px;
  }

  .log-drawer.open {
    max-height: 352px;
  }

  .log-columns {
    grid-template-columns: 1fr;
    grid-template-rows: minmax(0, 1fr) minmax(0, 1fr);
  }

  .syntax-column {
    border-left: 0;
    border-top: 1px solid var(--border-light);
  }

  .sidebar {
    width: 44px;
  }

  .nav-btn {
    width: 32px;
    height: 36px;
  }
}
</style>
