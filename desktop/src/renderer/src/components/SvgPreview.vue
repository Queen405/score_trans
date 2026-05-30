<template>
  <div class="svg-preview" v-if="svgUrl">
    <img :src="svgUrl" class="svg-img" />
  </div>
  <div v-else class="svg-empty">
    <n-icon size="48" :depth="3"><ImageOutline /></n-icon>
    <n-text depth="3">暂无 SVG 预览</n-text>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { getFileURL } from '../api/client'
import { ImageOutline } from '@vicons/ionicons5'
import { NText, NIcon } from 'naive-ui'

const props = defineProps<{ svgFileId: string }>()
const svgUrl = computed(() => (props.svgFileId ? getFileURL(props.svgFileId) : ''))
</script>

<style scoped>
.svg-preview {
  flex: 1;
  min-height: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid rgba(129, 161, 193, 0.24);
  border-radius: 16px;
  background: linear-gradient(180deg, rgba(248, 250, 253, 0.84) 0%, rgba(236, 239, 244, 0.72) 100%);
  overflow: hidden;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.5);
}

.svg-img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: contain;
  border-radius: 10px;
}

.svg-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 48px 0;
  text-align: center;
}

:global(body.n-theme-dark) .svg-preview {
  border-color: rgba(129, 161, 193, 0.35);
  background: linear-gradient(180deg, rgba(46, 52, 64, 0.9) 0%, rgba(59, 66, 82, 0.82) 100%);
}
</style>
