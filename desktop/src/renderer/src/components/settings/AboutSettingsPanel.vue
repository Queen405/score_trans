<template>
  <div class="sv-panel">
    <section class="sv-section">
      <div class="sv-section-heading">
        <h3>应用信息</h3>
      </div>
      <div class="sv-form-stack">
        <settings-form-row label="当前版本">
          <span class="about-version-value">v{{ currentVersion || '—' }}</span>
        </settings-form-row>
        <settings-form-row label="最新版本">
          <span class="about-version-value">
            {{ result?.latestVersion ? `v${result.latestVersion}` : '—' }}
          </span>
        </settings-form-row>
      </div>
    </section>

    <div class="sv-section-divider" />

    <section class="sv-section">
      <div class="sv-section-heading">
        <h3>检查更新</h3>
        <p>启动时已自动检查一次。如需立即重新检查，请点击下方按钮。</p>
      </div>
      <div class="about-update-body">
        <n-button
          size="small"
          type="primary"
          :loading="checking"
          :disabled="checking"
          @click="runCheck"
        >
          检查更新
        </n-button>
        <div
          v-if="checking"
          class="about-update-status"
        >
          <n-spin size="small" />
          <span>正在检查…</span>
        </div>
        <div
          v-else-if="result?.error"
          class="about-update-status is-error"
        >
          <n-alert
            type="error"
            :show-icon="false"
          >
            {{ result.error }}
          </n-alert>
        </div>
        <div
          v-else-if="result?.hasUpdate"
          class="about-update-status is-update"
        >
          <span class="about-update-text">发现新版本 v{{ result.latestVersion }}</span>
          <n-button
            size="small"
            type="primary"
            @click="openDownloadPage"
          >
            前往下载
          </n-button>
        </div>
        <div
          v-else-if="result && !result.hasUpdate"
          class="about-update-status is-current"
        >
          <span class="about-update-text">已是最新版本</span>
        </div>
        <div
          v-if="result?.notes"
          class="about-update-notes"
        >
          <div class="about-update-notes-title">
            更新说明
          </div>
          <p class="about-update-notes-body">
            {{ result.notes }}
          </p>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { NAlert, NButton, NSpin } from 'naive-ui'
import SettingsFormRow from './SettingsFormRow.vue'

type UpdateCheckResult = Awaited<ReturnType<typeof window.api.checkForUpdate>>

const checking = ref(false)
const result = ref<UpdateCheckResult | null>(null)
const currentVersion = ref('')

async function runCheck(): Promise<void> {
  checking.value = true
  try {
    result.value = await window.api.checkForUpdate()
    currentVersion.value = result.value.currentVersion
  } catch (err) {
    console.warn('[about] update check failed:', err)
  } finally {
    checking.value = false
  }
}

function openDownloadPage(): void {
  const url = result.value?.downloadUrl
  if (typeof url === 'string') void window.api.openExternal(url)
}

onMounted(() => {
  void runCheck()
})
</script>

<style scoped>
.about-version-value {
  display: inline-flex;
  align-items: center;
  min-height: 32px;
  color: var(--text-secondary);
  font-family: 'Cascadia Code', 'SFMono-Regular', Consolas, monospace;
  font-size: 13px;
}

.about-update-body {
  display: flex;
  flex-direction: column;
  gap: 16px;
  max-width: 560px;
}

.about-update-status {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 13px;
  color: var(--text-secondary);
}

.about-update-status.is-current .about-update-text {
  color: var(--success);
}

.about-update-status.is-update .about-update-text {
  color: var(--warning);
  font-weight: 600;
}

.about-update-status.is-error {
  align-items: stretch;
}

.about-update-notes {
  padding: 12px 14px;
  background: var(--bg-elevated);
  border-radius: 8px;
  border: 1px solid var(--border);
}

.about-update-notes-title {
  margin-bottom: 6px;
  color: var(--text-tertiary);
  font-size: 11px;
  font-weight: 600;
}

.about-update-notes-body {
  margin: 0;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.6;
  white-space: pre-wrap;
}
</style>
