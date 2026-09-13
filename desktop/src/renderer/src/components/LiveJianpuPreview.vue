<template>
  <div class="live-preview">
    <div v-if="loading" class="live-status">????</div>
    <div v-else-if="!svg" class="live-status">???????????????</div>
    <div v-else class="live-svg" v-html="safeSvg" />
    <div v-if="error" class="live-error">{{ error }}</div>
  </div>
</template>
<script setup lang="ts">
import { computed } from "vue"
import { sanitizeSvg } from "../utils/svgSanitizer"
const props = defineProps<{ svg: string; loading?: boolean; error?: string }>()
const safeSvg = computed(() => sanitizeSvg(props.svg).outerHTML)
</script>
<style scoped>
.live-preview{position:relative;height:100%;overflow:auto;background:var(--panel-bg,#fff);padding:12px}.live-svg:deep(svg){display:block;max-width:100%;height:auto;margin:0 auto}.live-status{height:100%;display:grid;place-items:center;color:var(--text-tertiary)}.live-error{position:sticky;bottom:0;padding:6px 10px;background:rgba(180,40,40,.12);color:#c0392b;font-size:12px}
</style>

