<template>
  <div class="sv-form-row">
    <div class="sv-form-label">
      <label>{{ label }}</label>
      <span v-if="description">{{ description }}</span>
    </div>
    <div class="sv-form-control">
      <slot />
      <p
        v-if="hint"
        class="sv-form-hint"
      >
        {{ hint }}
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  label: string
  description?: string
  hint?: string
}>()
</script>
