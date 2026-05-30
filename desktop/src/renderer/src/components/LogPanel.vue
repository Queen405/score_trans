<template>
  <div class="log-panel">
    <div class="log-header">
      <n-text strong style="font-size: 13px">操作日志</n-text>
      <n-button size="tiny" quaternary @click="logStore.clear()">清空</n-button>
    </div>
    <div class="log-container" ref="logContainer">
      <div v-for="(entry, i) in logStore.entries" :key="i" class="log-entry" :class="entry.level">
        <span class="log-dot" :class="entry.level"></span>
        <span class="time">{{ entry.timestamp }}</span>
        <span class="message">{{ entry.message }}</span>
      </div>
      <div v-if="!logStore.entries.length" class="log-entry info">
        <span class="log-dot info"></span>
        <span class="message" style="color: #999">暂无日志</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, nextTick } from 'vue'
import { useLogStore } from '../stores/log'
import { NText, NButton } from 'naive-ui'

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
  padding: 6px 2px;
}

.log-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}

.log-container {
  max-height: 128px;
  overflow-y: auto;
  font-family: 'Cascadia Code', 'Consolas', 'Courier New', monospace;
  font-size: 12px;
  line-height: 1.8;
  border: 1px solid rgba(94, 129, 172, 0.2);
  border-radius: 12px;
  background: linear-gradient(145deg, rgba(255, 255, 255, 0.7), rgba(236, 239, 244, 0.6));
  padding: 8px 10px;
}

.log-entry {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 2px 0;
}

.log-dot {
  flex-shrink: 0;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  margin-top: 7px;
  background: #c0c0c0;
}

.log-dot.info {
  background: #4a9c6d;
}

.log-dot.error {
  background: #d03050;
}

.log-dot.warn {
  background: #f0a020;
}

.log-entry.error .message {
  color: #d03050;
}

.log-entry.warn .message {
  color: #f0a020;
}

.log-entry .time {
  color: #7d8698;
  flex-shrink: 0;
  font-size: 11px;
}

:global(body.n-theme-dark) .log-container {
  border-color: rgba(129, 161, 193, 0.25);
  background: linear-gradient(145deg, rgba(46, 52, 64, 0.86), rgba(59, 66, 82, 0.78));
}

:global(body.n-theme-dark) .log-entry .time {
  color: #aeb8cb;
}

:global(body.n-theme-dark) .log-entry.error .message {
  color: #ff8f9e;
}

:global(body.n-theme-dark) .log-entry.warn .message {
  color: #ffd27f;
}
</style>
