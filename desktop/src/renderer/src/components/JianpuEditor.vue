<template>
  <n-input
    type="textarea"
    :value="modelValue"
    @update:value="$emit('update:modelValue', $event)"
    placeholder="key=C&#10;time=4/4&#10;1 2 3 4 | 5 6 7 1' |"
    :rows="12"
    font="monospace"
  />
</template>

<script setup lang="ts">
import { NInput } from 'naive-ui'

defineProps<{ modelValue: string }>()
defineEmits<{ 'update:modelValue': [value: string] }>()
</script>
