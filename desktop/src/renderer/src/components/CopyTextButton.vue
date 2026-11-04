<template>
  <button
    type="button"
    class="copy-text-button"
    :class="{ copied }"
    :aria-label="label"
    :title="label"
    @click.stop="copyText"
  >
    <n-icon :component="copied ? CheckmarkOutline : CopyOutline" />
  </button>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'
import { NIcon, useMessage } from 'naive-ui'
import { CheckmarkOutline, CopyOutline } from '@vicons/ionicons5'
import { t } from '../i18n'

const props = defineProps<{
  text: string
}>()

const message = useMessage()
const copied = ref(false)
let resetTimer: ReturnType<typeof setTimeout> | null = null
const label = computed(() =>
  copied.value ? t('common.action.copied') : t('common.action.copy'),
)

async function copyText(): Promise<void> {
  try {
    await window.navigator.clipboard.writeText(props.text)
    copied.value = true
    if (resetTimer) clearTimeout(resetTimer)
    resetTimer = setTimeout(() => {
      copied.value = false
    }, 1600)
  } catch {
    message.error(t('common.action.copyFailed'))
  }
}

onBeforeUnmount(() => {
  if (resetTimer) clearTimeout(resetTimer)
})
</script>

<style scoped>
.copy-text-button {
  display: inline-flex;
  flex: 0 0 auto;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  margin-left: auto;
  padding: 0;
  border: 0;
  border-radius: 4px;
  background: transparent;
  color: var(--text-tertiary);
  cursor: pointer;
  transition: color 0.15s ease, background 0.15s ease;
}

.copy-text-button:hover {
  background: var(--bg-hover, rgba(128, 128, 128, 0.12));
  color: var(--text-primary);
}

.copy-text-button.copied {
  color: var(--success);
}

.copy-text-button:focus-visible {
  outline: 2px solid var(--sv-accent, #5f739f);
  outline-offset: 1px;
}
</style>
