<template>
  <div class="svg-preview" v-if="svgUrl">
    <div class="svg-scroll">
      <img :src="svgUrl" class="svg-img" />
    </div>
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
  border: 1px solid #e0e0e6;
  border-radius: 10px;
  background: linear-gradient(180deg, #f9f7f0 0%, #f4f1e8 100%);
  overflow: hidden;
}

.svg-scroll {
  max-height: 72vh;
  overflow: auto;
}

.svg-img {
  display: block;
  width: auto;
  min-width: 1200px;
  max-width: none;
}

.svg-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 48px 0;
  text-align: center;
}
</style>
