<template>
  <div class="syntax-diagnostic-panel">
    <div
      v-if="syntaxStore.loading"
      class="syntax-diagnostic-state"
    >
      {{ t('components.syntaxDiagnosticPanel.checking') }}
    </div>
    <div
      v-else-if="syntaxStore.error"
      class="syntax-diagnostic-state error"
    >
      {{ syntaxStore.error }}
    </div>
    <div
      v-else-if="!syntaxStore.visibleDiagnostics.length"
      class="syntax-diagnostic-state"
    >
      {{ syntaxStore.hideWarnings && syntaxStore.warningCount ? t('components.syntaxDiagnosticPanel.noIssueWarningsHidden') : t('components.syntaxDiagnosticPanel.noIssue') }}
    </div>
    <template v-else>
      <div
        v-for="diagnostic in syntaxStore.visibleDiagnostics"
        :key="diagnostic.id"
        class="syntax-diagnostic"
        :class="[{ active: diagnostic.id === syntaxStore.activeId }, diagnostic.severity]"
        @click="selectDiagnostic(diagnostic)"
      >
        <button
          type="button"
          class="syntax-diagnostic-target"
        >
          <span class="syntax-diagnostic-location">{{ diagnostic.measure ? t('components.syntaxDiagnosticPanel.measureLabel', { n: diagnostic.measure }) : '—' }}</span>
          <span class="syntax-diagnostic-message">{{ diagnostic.message }}</span>
        </button>
        <copy-text-button :text="diagnosticCopyText(diagnostic)" />
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { useSyntaxDiagnosticsStore } from '../stores/syntaxDiagnostics'
import type { SyntaxDiagnostic } from '../models/types'
import { t } from '../i18n'
import CopyTextButton from './CopyTextButton.vue'
const syntaxStore = useSyntaxDiagnosticsStore()

function selectDiagnostic(diagnostic: SyntaxDiagnostic): void {
  syntaxStore.setActive(diagnostic.id)
}

function diagnosticCopyText(diagnostic: SyntaxDiagnostic): string {
  const location = diagnostic.measure
    ? t('components.syntaxDiagnosticPanel.measureLabel', { n: diagnostic.measure })
    : '—'
  return `${location} ${diagnostic.message}`
}
</script>

<style scoped>
.syntax-diagnostic-panel {
  height: 100%;
  overflow-y: auto;
  padding: 4px 16px 8px;
  font-family: 'Cascadia Code', 'Consolas', monospace;
  font-size: 11.5px;
  line-height: 1.7;
}

.syntax-diagnostic-state {
  padding: 1px 0;
  color: var(--text-tertiary);
}

.syntax-diagnostic-state.error {
  color: var(--danger);
}

.syntax-diagnostic {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  width: 100%;
  padding: 1px 0;
  border: 0;
  border-left: 2px solid transparent;
  background: transparent;
  color: var(--text-secondary);
  text-align: left;
  cursor: pointer;
}

.syntax-diagnostic.error:hover,
.syntax-diagnostic.error.active {
  background: rgba(220, 38, 38, 0.08);
}

.syntax-diagnostic.warning:hover,
.syntax-diagnostic.warning.active {
  background: rgba(250, 176, 5, 0.12);
}

.syntax-diagnostic.error.active {
  border-left-color: var(--danger);
}

.syntax-diagnostic.warning.active {
  border-left-color: var(--warning);
}

.syntax-diagnostic-location {
  flex: 0 0 auto;
  min-width: 42px;
  color: var(--danger);
  font-size: 10px;
  font-variant-numeric: tabular-nums;
  line-height: 1.7;
  white-space: nowrap;
}

.syntax-diagnostic.warning .syntax-diagnostic-location {
  color: var(--warning);
}

.syntax-diagnostic-target {
  display: flex;
  flex: 1;
  min-width: 0;
  align-items: flex-start;
  gap: 8px;
  padding: 0;
  border: 0;
  background: transparent;
  color: inherit;
  font: inherit;
  text-align: left;
  cursor: pointer;
}

.syntax-diagnostic-target:focus-visible {
  outline: 2px solid var(--sv-accent, #5f739f);
  outline-offset: 1px;
}

.syntax-diagnostic-message {
  min-width: 0;
  flex: 1;
  font-size: 11.5px;
  line-height: 1.7;
  overflow-wrap: anywhere;
}

.syntax-diagnostic :deep(.copy-text-button) {
  margin-top: -2px;
}
</style>
