<template>
  <div
    ref="logContainer"
    class="log-panel"
  >
    <div
      v-for="entry in logStore.entries"
      :key="entry.id"
      class="log-line"
      :class="entry.level"
    >
      <span
        class="log-dot"
        :class="entry.level"
      />
      <span class="log-ts">{{ entry.timestamp }}</span>
      <span class="log-msg">{{ entry.message }}</span>
    </div>
    <div
      v-if="!logStore.entries.length"
      class="log-line info"
    >
      <span class="log-dot info" />
      <span class="log-msg empty">暂无日志</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, nextTick } from 'vue'
import { useLogStore } from '../stores/log'

const logStore = useLogStore()
const logContainer = ref<HTMLDivElement>()

watch(
  () => logStore.entries.length,
  async () => {
    await nextTick()
    if (logContainer.value) {
      logContainer.value.scrollTop = logContainer.value.scrollHeight
    }
  },
)
</script>

<style scoped>
.log-panel {
  font-family: 'Cascadia Code', 'Consolas', monospace;
  font-size: 11.5px;
  line-height: 1.7;
}

.log-line {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 1px 0;
}

.log-dot {
  flex-shrink: 0;
  width: 5px;
  height: 5px;
  border-radius: 50%;
  margin-top: 7px;
  background: var(--text-tertiary);
}

.log-dot.info { background: var(--success); }
.log-dot.error { background: var(--danger); }
.log-dot.warn { background: var(--warning); }

.log-ts {
  flex-shrink: 0;
  font-size: 10px;
  color: var(--text-tertiary);
}

.log-msg {
  color: var(--text-secondary);
}

.log-msg.empty {
  color: var(--text-tertiary);
}

.log-line.error .log-msg {
  color: var(--danger);
}

.log-line.warn .log-msg {
  color: var(--warning);
}
</style>
