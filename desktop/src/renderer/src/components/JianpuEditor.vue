<template>
  <div class="editor-shell">
    <n-input
      type="textarea"
      :value="modelValue"
      @update:value="$emit('update:modelValue', $event)"
      placeholder="key=C&#10;time=4/4&#10;1 2 3 4 | 5 6 7 1' |"
      :rows="8"
      font="monospace"
      class="jianpu-input"
    />
  </div>
</template>

<script setup lang="ts">
import { NInput } from 'naive-ui'

defineProps<{ modelValue: string }>()
defineEmits<{ 'update:modelValue': [value: string] }>()
</script>

<style scoped>
.editor-shell {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.jianpu-input {
  flex: 1;
  min-height: 0;
  font-size: 13px;
  line-height: 1.75;
}

.jianpu-input :deep(.n-input),
.jianpu-input :deep(.n-input-wrapper),
.jianpu-input :deep(.n-input__textarea),
.jianpu-input :deep(.n-input__textarea-el) {
  height: 100%;
  min-height: 0;
}

.jianpu-input :deep(textarea) {
  border-radius: var(--radius-sm) !important;
  font-family: 'Cascadia Code', 'Consolas', monospace !important;
}
</style>
