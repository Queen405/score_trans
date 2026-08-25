<template>
  <div class="syntax-diagnostic-panel">
    <div
      v-if="syntaxStore.loading"
      class="syntax-diagnostic-state"
    >
      检查中…
    </div>
    <div
      v-else-if="syntaxStore.error"
      class="syntax-diagnostic-state error"
    >
      {{ syntaxStore.error }}
    </div>
    <div
      v-else-if="!syntaxStore.diagnostics.length"
      class="syntax-diagnostic-state"
    >
      未发现语法问题
    </div>
    <template v-else>
      <button
        v-for="diagnostic in syntaxStore.diagnostics"
        :key="diagnostic.id"
        type="button"
        class="syntax-diagnostic"
        :class="[{ active: diagnostic.id === syntaxStore.activeId }, diagnostic.severity]"
        @click="selectDiagnostic(diagnostic)"
        @keydown.enter.prevent="selectDiagnostic(diagnostic)"
        @keydown.space.prevent="selectDiagnostic(diagnostic)"
      >
        <span class="syntax-diagnostic-location">{{ diagnostic.line }}:{{ diagnostic.column }}</span>
        <span class="syntax-diagnostic-message">{{ diagnostic.message }}</span>
      </button>
    </template>
  </div>
</template>

<script setup lang="ts">
import { useSyntaxDiagnosticsStore } from '../stores/syntaxDiagnostics'
import type { SyntaxDiagnostic } from '../models/types'
const syntaxStore = useSyntaxDiagnosticsStore()

function selectDiagnostic(diagnostic: SyntaxDiagnostic): void {
  syntaxStore.setActive(diagnostic.id)
}
</script>

<style scoped>
.syntax-diagnostic-panel {
  height: 100%;
  overflow-y: auto;
  padding: 8px 12px;
  font-family: 'Cascadia Code', 'Consolas', monospace;
  font-size: 11.5px;
}

.syntax-diagnostic-state {
  padding: 10px 4px;
  color: var(--text-tertiary);
}

.syntax-diagnostic-state.error {
  color: var(--danger);
}

.syntax-diagnostic {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  width: 100%;
  padding: 5px 6px;
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
  flex: 0 0 42px;
  color: var(--danger);
  font-variant-numeric: tabular-nums;
}

.syntax-diagnostic.warning .syntax-diagnostic-location {
  color: var(--warning);
}

.syntax-diagnostic-message {
  min-width: 0;
  line-height: 1.5;
  overflow-wrap: anywhere;
}
</style>
