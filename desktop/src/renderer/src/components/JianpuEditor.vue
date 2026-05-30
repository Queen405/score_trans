<template>
  <n-input
    type="textarea"
    :value="modelValue"
    @update:value="$emit('update:modelValue', $event)"
    placeholder="key=C&#10;time=4/4&#10;1 2 3 4 | 5 6 7 1' |"
    :rows="14"
    font="monospace"
    class="jianpu-input"
  />
</template>

<script setup lang="ts">
import { NInput } from 'naive-ui'

defineProps<{ modelValue: string }>()
defineEmits<{ 'update:modelValue': [value: string] }>()
</script>

<style scoped>
.jianpu-input {
  font-size: 14px;
  line-height: 1.7;
}

.jianpu-input :deep(textarea) {
  border-radius: 8px !important;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

.jianpu-input :deep(textarea:focus) {
  box-shadow: 0 0 0 2px rgba(74, 156, 109, 0.2) !important;
}
</style>
