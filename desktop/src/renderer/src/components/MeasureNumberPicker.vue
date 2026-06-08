<template>
  <n-modal
    :show="show"
    preset="dialog"
    title="选择起始小节号"
    positive-text="确定"
    negative-text="取消"
    :show-icon="false"
    @positive-click="handleConfirm"
    @negative-click="handleCancel"
    @update:show="$emit('update:show', $event)"
  >
    <div class="picker-shell">
      <p class="picker-desc">识别到本页以下小节号，请选择本页的起始小节号：</p>
      <n-radio-group v-model:value="selectedValue" class="picker-options">
        <n-space vertical>
          <n-radio
            v-for="num in options"
            :key="num"
            :value="num"
          >
            第 {{ num }} 小节
          </n-radio>
          <n-radio :value="-1">
            <n-space align="center">
              <span>自定义</span>
              <n-input-number
                v-model:value="customValue"
                :disabled="selectedValue !== -1"
                placeholder="输入数字"
                :min="1"
                size="small"
                style="width: 120px"
              />
            </n-space>
          </n-radio>
        </n-space>
      </n-radio-group>
    </div>
  </n-modal>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { NModal, NRadio, NRadioGroup, NSpace, NInputNumber } from 'naive-ui'

const props = defineProps<{
  show: boolean
  options: number[]
}>()

const emit = defineEmits<{
  'update:show': [value: boolean]
  confirm: [value: number]
  cancel: []
}>()

const selectedValue = ref<number>(0)
const customValue = ref<number | null>(null)

watch(
  () => props.show,
  (visible) => {
    if (visible && props.options.length) {
      selectedValue.value = props.options[0]
      customValue.value = null
    }
  },
  { immediate: true },
)

function handleConfirm(): void {
  if (selectedValue.value === -1) {
    if (customValue.value != null && customValue.value >= 1) {
      emit('confirm', customValue.value)
    }
  } else {
    emit('confirm', selectedValue.value)
  }
  emit('update:show', false)
}

function handleCancel(): void {
  emit('cancel')
  emit('update:show', false)
}
</script>

<style scoped>
.picker-shell {
  padding: 4px 0;
}

.picker-desc {
  margin: 0 0 12px;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.6;
}

.picker-options {
  --n-gap: 8px;
}
</style>
