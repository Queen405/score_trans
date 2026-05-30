<template>
  <div class="editor-shell">
    <div class="editor-meta">
      <span class="meta-badge">Jianpu</span>
      <span class="meta-hint">支持实时编辑与回转 MusicXML</span>
    </div>
    <n-input
      type="textarea"
      :value="modelValue"
      @update:value="$emit('update:modelValue', $event)"
      placeholder="key=C&#10;time=4/4&#10;1 2 3 4 | 5 6 7 1' |"
      :rows="14"
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
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.editor-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.meta-badge {
  display: inline-flex;
  align-items: center;
  padding: 4px 10px;
  border-radius: 999px;
  border: 1px solid rgba(94, 129, 172, 0.48);
  background: rgba(94, 129, 172, 0.15);
  color: #3b516f;
  font-size: 11px;
  font-weight: 640;
  letter-spacing: 0.6px;
  text-transform: uppercase;
}

.meta-hint {
  font-size: 12px;
  color: #6c7486;
}

.jianpu-input {
  font-size: 14px;
  line-height: 1.75;
}

.jianpu-input :deep(textarea) {
  border-radius: 14px !important;
  border: 1px solid rgba(129, 161, 193, 0.28) !important;
  background: linear-gradient(145deg, rgba(248, 250, 253, 0.88), rgba(236, 239, 244, 0.75)) !important;
  font-family: 'Cascadia Code', 'Consolas', 'Courier New', monospace !important;
  transition: border-color 0.2s ease, box-shadow 0.2s ease, transform 0.2s ease;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.52);
}

.jianpu-input :deep(textarea:focus) {
  border-color: rgba(94, 129, 172, 0.78) !important;
  box-shadow: 0 0 0 3px rgba(136, 192, 208, 0.28), 0 16px 36px -30px rgba(46, 52, 64, 0.9) !important;
  transform: translateY(-1px);
}

:global(body.n-theme-dark) .meta-badge {
  border-color: rgba(136, 192, 208, 0.52);
  background: rgba(136, 192, 208, 0.2);
  color: #e5eef8;
}

:global(body.n-theme-dark) .meta-hint {
  color: #c7cfdd;
}

:global(body.n-theme-dark) .jianpu-input :deep(textarea) {
  background: linear-gradient(145deg, rgba(46, 52, 64, 0.88), rgba(59, 66, 82, 0.82)) !important;
  border-color: rgba(129, 161, 193, 0.35) !important;
  color: #eceff4;
}

:global(body.n-theme-dark) .jianpu-input :deep(textarea:focus) {
  border-color: rgba(136, 192, 208, 0.95) !important;
  box-shadow: 0 0 0 3px rgba(136, 192, 208, 0.22), 0 18px 40px -30px rgba(0, 0, 0, 0.95) !important;
}
</style>
