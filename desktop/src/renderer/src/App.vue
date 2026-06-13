<template>
  <n-config-provider :theme="naiveTheme" :theme-overrides="themeOverrides">
    <n-message-provider>
      <div :class="['app-shell', effectiveDark ? 'theme-dark' : 'theme-light']">
        <div class="titlebar" role="banner">
          <div class="titlebar-left">
            <img class="app-icon-img" src="./assets/icon.png" alt="Score Trans" />
            <span class="app-title">Score Trans</span>
          </div>
          <div class="titlebar-drag" />
          <div class="titlebar-right">
            <div class="window-controls" role="group" aria-label="窗口控制">
              <button class="wc-btn" type="button" aria-label="最小化" @click="minimizeWindow">
                <svg width="10" height="1" viewBox="0 0 10 1"><rect width="10" height="1" fill="currentColor" /></svg>
              </button>
              <button class="wc-btn" type="button" :aria-label="isMaximized ? '还原' : '最大化'" @click="toggleMaximizeWindow">
                <svg v-if="!isMaximized" width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor" stroke-width="1.2"><rect x="0.6" y="0.6" width="8.8" height="8.8" /></svg>
                <svg v-else width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor" stroke-width="1.2"><rect x="2" y="0" width="8" height="8" /><rect x="0" y="2" width="8" height="8" fill="var(--bg-base)" /><rect x="0" y="2" width="8" height="8" /></svg>
              </button>
              <button class="wc-btn wc-close" type="button" aria-label="关闭" @click="closeWindow">
                <svg width="10" height="10" viewBox="0 0 10 10" stroke="currentColor" stroke-width="1.3"><line x1="0" y1="0" x2="10" y2="10" /><line x1="10" y1="0" x2="0" y2="10" /></svg>
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
                @click="activeTab = item.key"
              >
                <component :is="item.icon" />
              </button>
            </div>
            <div class="sidebar-footer">
              <div v-if="store.isBusy || store.backgroundTaskCount" class="busy-indicator" title="后台处理中…" />
            </div>
          </nav>

          <main class="main-area">
            <div class="main-content">
              <recognize-view v-show="activeTab === 'recognize'" :active="activeTab === 'recognize'" />
              <convert-view v-show="activeTab === 'convert'" />
              <settings-view v-show="activeTab === 'settings'" />
              <ai-assistant v-if="activeTab === 'convert'" />
            </div>
            <div :class="['log-drawer', { open: logOpen }]">
              <button class="log-toggle" @click="logOpen = !logOpen">
                <svg width="12" height="12" viewBox="0 0 12 12" fill="currentColor"><path d="M2 4l4 4 4-4" /></svg>
                <span>日志</span>
                <span v-if="logStore.errorCount" class="log-badge">{{ logStore.errorCount }}</span>
              </button>
              <div class="log-body">
                <log-panel />
              </div>
            </div>
          </main>
        </div>
      </div>
    </n-message-provider>
  </n-config-provider>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import type { GlobalThemeOverrides } from 'naive-ui'
import { useTaskStore } from './stores/task'
import { useLogStore } from './stores/log'
import { useSettingsStore } from './stores/settings'
import RecognizeView from './views/RecognizeView.vue'
import ConvertView from './views/ConvertView.vue'
import SettingsView from './views/SettingsView.vue'
import AiAssistant from './components/AiAssistant.vue'
import LogPanel from './components/LogPanel.vue'
import {
  ScanOutline,
  SyncOutline,
  SettingsOutline,
} from '@vicons/ionicons5'
import { darkTheme, NConfigProvider, NMessageProvider } from 'naive-ui'

const store = useTaskStore()
const logStore = useLogStore()
const settings = useSettingsStore()

const activeTab = ref<'recognize' | 'convert' | 'settings'>('recognize')
const logOpen = ref(false)
const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
const systemPrefersDark = ref(mediaQuery.matches)
const isMaximized = ref(false)
let removeMaximizedListener: (() => void) | null = null

const navItems = [
  { key: 'recognize' as const, label: '识别', icon: ScanOutline },
  { key: 'convert' as const, label: '工作台', icon: SyncOutline },
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

.log-drawer {
  flex-shrink: 0;
  border-top: 1px solid var(--border);
  background: var(--bg-elevated);
  max-height: 32px;
  overflow: hidden;
  transition: max-height 0.25s ease;
}

.log-drawer.open {
  max-height: 200px;
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
  background: var(--danger);
  color: #fff;
  font-size: 10px;
  font-weight: 600;
  padding: 1px 5px;
  border-radius: 9px;
  line-height: 1.3;
}

.log-body {
  height: 168px;
  overflow-y: auto;
  border-top: 1px solid var(--border-light);
}

.log-body .log-panel {
  padding: 8px 16px;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

@media (max-width: 768px) {
  .main-content {
    padding: 16px;
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
