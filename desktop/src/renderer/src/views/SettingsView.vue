<template>
  <div class="settings-view">
    <aside
      class="sv-sidebar"
      :aria-label="t('settings.view.categoriesAria')"
    >
      <div class="sv-sidebar-header">
        <span class="sv-sidebar-eyebrow">{{ t('settings.view.eyebrow') }}</span>
        <h2>{{ t('settings.view.title') }}</h2>
      </div>

      <nav class="sv-category-list">
        <button
          v-for="category in categories"
          :key="category.key"
          type="button"
          :class="['sv-category-button', { active: activeCategory === category.key }]"
          :aria-current="activeCategory === category.key ? 'page' : undefined"
          @click="activeCategory = category.key"
        >
          <n-icon size="18">
            <component :is="category.icon" />
          </n-icon>
          <span>{{ category.label }}</span>
        </button>
      </nav>
    </aside>

    <section class="sv-main">
      <header class="sv-page-header">
        <div>
          <h1>{{ activeCategoryMeta.label }}</h1>
        </div>
        <span
          v-if="settings.draftDirty"
          class="sv-dirty-indicator"
        >
          <span />
          {{ t('settings.view.dirtyIndicator') }}
        </span>
      </header>

      <div class="sv-page-body">
        <div
          v-if="settings.loading"
          class="sv-state-view"
        >
          <n-spin size="small" />
          <span>{{ t('settings.view.loading') }}</span>
        </div>

        <div
          v-else-if="settings.loadError || !settings.loaded"
          class="sv-state-view"
        >
          <n-alert
            type="error"
            :title="t('settings.view.loadFailed')"
          >
            {{ settings.loadError || t('settings.view.notLoaded') }}
          </n-alert>
          <n-button
            size="small"
            secondary
            @click="retryLoad"
          >
            {{ t('settings.view.reload') }}
          </n-button>
        </div>

        <div
          v-else-if="settings.draftReady"
          class="sv-panel-container"
        >
          <component :is="activePanel" />
        </div>
      </div>

      <footer class="sv-footer">
        <div
          class="sv-footer-status"
          role="status"
        >
          <span
            v-if="settings.saveError"
            class="is-error"
          >{{ settings.saveError }}</span>
          <span v-else-if="settings.draftDirty">{{ t('settings.view.statusUnsaved') }}</span>
          <span v-else-if="settings.storageRestartRequired">{{ t('settings.view.statusStorageRestart') }}</span>
          <span v-else>{{ t('settings.view.statusAllSaved') }}</span>
        </div>
        <div class="sv-footer-actions">
          <n-button
            :disabled="settings.saving"
            @click="cancel"
          >
            {{ t('common.action.cancel') }}
          </n-button>
          <n-button
            type="primary"
            :disabled="!settings.draftDirty || settings.saving"
            :loading="settings.saving"
            @click="save"
          >
            {{ t('settings.view.save') }}
          </n-button>
        </div>
      </footer>
    </section>

    <n-modal
      v-model:show="restartModalVisible"
      preset="card"
      class="sv-modal-card"
      :title="t('settings.view.restartTitle')"
      :bordered="false"
      :mask-closable="false"
    >
      <p class="sv-modal-copy">
        {{ t('settings.view.restartBody') }}
      </p>
      <template #footer>
        <div class="sv-modal-actions">
          <n-button @click="restartLater">
            {{ t('settings.view.restartLater') }}
          </n-button>
          <n-button
            type="primary"
            @click="restartNow"
          >
            {{ t('settings.view.restartNow') }}
          </n-button>
        </div>
      </template>
    </n-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch, type Component } from 'vue'
import {
  NAlert,
  NButton,
  NIcon,
  NModal,
  NSpin,
  useMessage,
} from 'naive-ui'
import {
  CloudOutline,
  ColorPaletteOutline,
  GridOutline,
  SettingsOutline,
  SwapHorizontalOutline,
} from '@vicons/ionicons5'
import { useLogStore } from '../stores/log'
import { useSettingsStore } from '../stores/settings'
import { t } from '../i18n'
import AppearanceSettingsPanel from '../components/settings/AppearanceSettingsPanel.vue'
import ConversionSettingsPanel from '../components/settings/ConversionSettingsPanel.vue'
import JianpuLayoutSettingsPanel from '../components/settings/JianpuLayoutSettingsPanel.vue'
import ServiceSettingsPanel from '../components/settings/ServiceSettingsPanel.vue'
import ToolStorageSettingsPanel from '../components/settings/ToolStorageSettingsPanel.vue'

type SettingsCategory = 'services' | 'tools-storage' | 'conversion' | 'jianpu-layout' | 'appearance'

interface CategoryDefinition {
  key: SettingsCategory
  label: string
  icon: Component
  panel: Component
}

const props = defineProps<{
  active: boolean
}>()

const emit = defineEmits<{
  close: []
}>()

const settings = useSettingsStore()
const log = useLogStore()
const message = useMessage()
const activeCategory = ref<SettingsCategory>('services')
const restartModalVisible = ref(false)

const categories = computed<CategoryDefinition[]>(() => [
  {
    key: 'services',
    label: t('settings.category.services'),
    icon: CloudOutline,
    panel: ServiceSettingsPanel,
  },
  {
    key: 'tools-storage',
    label: t('settings.category.toolsStorage'),
    icon: SettingsOutline,
    panel: ToolStorageSettingsPanel,
  },
  {
    key: 'conversion',
    label: t('settings.category.conversion'),
    icon: SwapHorizontalOutline,
    panel: ConversionSettingsPanel,
  },
  {
    key: 'jianpu-layout',
    label: t('settings.category.jianpuLayout'),
    icon: GridOutline,
    panel: JianpuLayoutSettingsPanel,
  },
  {
    key: 'appearance',
    label: t('settings.category.appearance'),
    icon: ColorPaletteOutline,
    panel: AppearanceSettingsPanel,
  },
])

const activeCategoryMeta = computed(
  () => categories.value.find((category) => category.key === activeCategory.value) ?? categories.value[0],
)
const activePanel = computed(() => activeCategoryMeta.value.panel)

watch(
  () => props.active,
  (active) => {
    if (active) void prepareSettings()
  },
  { immediate: true },
)

watch(
  () => settings.loaded,
  (loaded) => {
    if (props.active && loaded && !settings.draftReady) {
      settings.beginEdit()
    }
  },
)

watch(
  () => settings.pendingSettingsCategory,
  (category) => {
    if (!category) return
    if (categories.value.some((c) => c.key === category)) {
      activeCategory.value = category as SettingsCategory
    }
    settings.pendingSettingsCategory = null
  },
)

async function prepareSettings(): Promise<void> {
  if (!settings.loaded) await settings.load()
  if (settings.loaded && (!settings.draftReady || !settings.draftDirty)) {
    settings.beginEdit()
  }
}

async function retryLoad(): Promise<void> {
  await settings.load()
  if (settings.loaded) settings.beginEdit()
}

function cancel(): void {
  settings.discardDraft()
  emit('close')
}

async function save(): Promise<void> {
  try {
    const restartNeeded = await settings.applyDraft()
    log.addLog(t('settings.view.saved'))
    message.success(restartNeeded ? t('settings.view.savedRestart') : t('settings.view.saved'))
    if (restartNeeded) {
      restartModalVisible.value = true
    }
  } catch (error: unknown) {
    const text = error instanceof Error ? error.message : String(error)
    log.addError(t('settings.view.saveFailed', { text }))
    message.error(text)
  }
}

function restartLater(): void {
  restartModalVisible.value = false
}

async function restartNow(): Promise<void> {
  await settings.relaunchApp()
}
</script>

<style>
.settings-view {
  --sv-accent: #5f739f;
  --sv-accent-soft: rgba(95, 115, 159, 0.12);
  --sv-accent-border: rgba(95, 115, 159, 0.28);
  display: grid;
  grid-template-columns: 232px minmax(0, 1fr);
  flex: 1;
  width: 100%;
  height: auto;
  min-height: 0;
  overflow: hidden;
  color: var(--text-primary);
  background: var(--bg-surface);
}

.theme-dark .settings-view {
  --sv-accent: #788db8;
  --sv-accent-soft: rgba(120, 141, 184, 0.14);
  --sv-accent-border: rgba(120, 141, 184, 0.3);
}

.sv-sidebar {
  display: flex;
  flex-direction: column;
  min-width: 0;
  padding: 30px 16px 18px;
  background: var(--bg-elevated);
  border-right: 1px solid var(--border);
}

.sv-sidebar-header {
  padding: 0 12px 24px;
}

.sv-sidebar-eyebrow {
  display: block;
  margin-bottom: 5px;
  color: var(--text-tertiary);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 1.4px;
}

.sv-sidebar-header h2 {
  margin: 0;
  font-size: 22px;
  font-weight: 650;
  letter-spacing: -0.4px;
}

.sv-category-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.sv-category-button {
  position: relative;
  display: grid;
  grid-template-columns: 22px minmax(0, 1fr);
  align-items: center;
  gap: 10px;
  width: 100%;
  min-height: 42px;
  padding: 0 12px;
  border: 1px solid transparent;
  border-radius: 6px;
  color: var(--text-secondary);
  background: transparent;
  font: inherit;
  font-size: 14px;
  text-align: left;
  cursor: pointer;
  transition:
    color 0.14s ease,
    background-color 0.14s ease,
    border-color 0.14s ease;
}

.sv-category-button:hover {
  color: var(--text-primary);
  background: rgba(127, 127, 127, 0.08);
}

.sv-category-button.active {
  color: var(--text-primary);
  background: var(--sv-accent-soft);
  border-color: var(--sv-accent-border);
}

.sv-category-button.active::before {
  position: absolute;
  left: -1px;
  top: 10px;
  bottom: 10px;
  width: 2px;
  border-radius: 0 2px 2px 0;
  background: var(--sv-accent);
  content: '';
}

.sv-category-button .n-icon {
  color: var(--text-tertiary);
}

.sv-category-button.active .n-icon {
  color: var(--sv-accent);
}

.sv-sidebar-note {
  margin-top: auto;
  padding: 18px 12px 0;
  border-top: 1px solid var(--border-light);
  color: var(--text-tertiary);
  font-size: 12px;
  line-height: 1.6;
}

.sv-main {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr) 68px;
  min-width: 0;
  min-height: 0;
  background: var(--bg-surface);
}

.sv-page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
  padding: 32px 48px 24px;
  border-bottom: 1px solid var(--border-light);
}

.sv-breadcrumb {
  margin-bottom: 8px;
  color: var(--text-tertiary);
  font-size: 12px;
}

.sv-page-header h1 {
  margin: 0;
  font-size: 25px;
  font-weight: 650;
  line-height: 1.2;
  letter-spacing: -0.5px;
}

.sv-page-header p {
  margin: 8px 0 0;
  color: var(--text-tertiary);
  font-size: 13px;
  line-height: 1.5;
}

.sv-dirty-indicator,
.sv-status {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  white-space: nowrap;
  font-size: 12px;
}

.sv-dirty-indicator {
  margin-top: 28px;
  color: var(--text-secondary);
}

.sv-dirty-indicator > span,
.sv-status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--warning);
}

.sv-page-body {
  min-height: 0;
  overflow-y: auto;
  padding: 30px 48px 48px;
}

.sv-panel-container {
  width: 100%;
  max-width: 920px;
  margin-inline: auto;
}

.sv-panel {
  width: 100%;
}

.sv-section {
  min-width: 0;
}

.sv-section-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
  margin-bottom: 24px;
}

.sv-section-heading h3 {
  margin: 0;
  color: var(--text-primary);
  font-size: 16px;
  font-weight: 650;
  line-height: 1.4;
}

.sv-section-heading p {
  margin: 5px 0 0;
  color: var(--text-tertiary);
  font-size: 12px;
  line-height: 1.55;
}

.sv-section-divider {
  width: 100%;
  height: 1px;
  margin: 28px 0;
  background: var(--border);
}

.sv-form-stack {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.sv-form-row {
  display: grid;
  grid-template-columns: 132px minmax(0, 560px);
  align-items: start;
  column-gap: 24px;
  min-width: 0;
}

.sv-form-label {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
  padding-top: 7px;
}

.sv-form-label label {
  color: var(--text-secondary);
  font-size: 13px;
  font-weight: 500;
  line-height: 1.45;
}

.sv-form-label span {
  color: var(--text-tertiary);
  font-size: 11px;
  line-height: 1.4;
}

.sv-form-control {
  min-width: 0;
}

.sv-form-control > .n-input,
.sv-form-control > .n-select,
.sv-form-control > .n-radio-group {
  width: 100%;
  max-width: 560px;
}

.sv-form-control .n-input,
.sv-form-control .n-base-selection {
  font-size: 13px;
}

.sv-form-hint {
  margin: 7px 0 0;
  color: var(--text-tertiary);
  font-size: 11px;
  line-height: 1.45;
}

.sv-readonly-value {
  display: flex;
  align-items: center;
  min-height: 32px;
  color: var(--text-secondary);
  font-family: 'Cascadia Code', 'SFMono-Regular', Consolas, monospace;
  font-size: 12px;
  overflow-wrap: anywhere;
}

.sv-status {
  margin-top: 2px;
  color: var(--text-tertiary);
}

.sv-status.is-saved {
  color: var(--success);
}

.sv-status.is-pending {
  color: var(--warning);
}

.sv-status.is-error {
  color: var(--danger);
}

.sv-status.is-saved .sv-status-dot {
  background: var(--success);
}

.sv-status.is-pending .sv-status-dot {
  background: var(--warning);
}

.sv-status.is-error .sv-status-dot {
  background: var(--danger);
}

.sv-status.is-empty .sv-status-dot,
.sv-status.is-loading .sv-status-dot {
  background: var(--text-tertiary);
}

.sv-storage-summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  max-width: 716px;
  min-height: 58px;
  padding: 12px 0;
}

.sv-storage-summary > div {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.sv-storage-summary span {
  color: var(--text-tertiary);
  font-size: 12px;
}

.sv-storage-summary strong {
  color: var(--text-primary);
  font-size: 18px;
  font-weight: 600;
}

.sv-inline-alert {
  max-width: 716px;
  margin-top: 18px;
}

.sv-alert-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.sv-theme-options {
  width: auto !important;
}

.sv-state-view {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 16px;
  max-width: 680px;
  margin-inline: auto;
  padding-top: 16px;
  color: var(--text-tertiary);
  font-size: 13px;
}

.sv-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  padding: 0 32px 0 48px;
  border-top: 1px solid var(--border);
  background: var(--bg-elevated);
}

.sv-footer-status {
  min-width: 0;
  color: var(--text-tertiary);
  font-size: 12px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sv-footer-status .is-error {
  color: var(--danger);
}

.sv-footer-actions {
  display: flex;
  flex-shrink: 0;
  gap: 10px;
  margin-left: auto;
}

.sv-modal-card {
  width: min(440px, calc(100vw - 48px));
}

.sv-modal-copy {
  margin: 0;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.7;
}

.sv-modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

@media (max-width: 980px) {
  .settings-view {
    grid-template-columns: 204px minmax(0, 1fr);
  }

  .sv-page-header {
    padding: 28px 28px 22px;
  }

  .sv-page-body {
    padding: 26px 28px 40px;
  }

  .sv-footer {
    padding: 0 24px 0 28px;
  }
}

@media (max-width: 820px) {
  .settings-view {
    grid-template-columns: 184px minmax(0, 1fr);
  }

  .sv-sidebar {
    padding-inline: 10px;
  }

  .sv-sidebar-header,
  .sv-sidebar-note {
    padding-inline: 9px;
  }

  .sv-form-row {
    grid-template-columns: minmax(0, 1fr);
    row-gap: 7px;
  }

  .sv-form-label {
    padding-top: 0;
  }

  .sv-form-label span {
    display: none;
  }

  .sv-page-header {
    padding: 24px 20px 20px;
  }

  .sv-page-body {
    padding: 22px 20px 32px;
  }

  .sv-footer {
    padding: 0 16px 0 20px;
  }

  .sv-footer-status {
    display: none;
  }
}
</style>
