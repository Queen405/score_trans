<template>
  <n-card title="操作日志" size="small">
    <template #header-extra>
      <n-button size="small" @click="logStore.clear()">清空</n-button>
    </template>
    <div class="log-container" ref="logContainer">
      <div v-for="(entry, i) in logStore.entries" :key="i" class="log-entry" :class="entry.level">
        <span class="time">[{{ entry.timestamp }}]</span>
        <span class="message">{{ entry.message }}</span>
      </div>
      <div v-if="!logStore.entries.length" class="log-entry info">
        <span class="message">暂无日志</span>
      </div>
    </div>
  </n-card>
</template>

<script setup lang="ts">
import { ref, watch, nextTick } from 'vue'
import { useLogStore } from '../stores/log'
import { NCard, NButton } from 'naive-ui'

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
.log-container {
  max-height: 150px;
  overflow-y: auto;
  font-family: 'Consolas', 'Courier New', monospace;
  font-size: 12px;
  line-height: 1.6;
}
.log-entry.error .message {
  color: #d03050;
}
.log-entry.warn .message {
  color: #f0a020;
}
.log-entry .time {
  color: #999;
  margin-right: 8px;
}
</style>
