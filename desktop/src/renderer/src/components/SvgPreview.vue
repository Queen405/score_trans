<template>
  <div class="svg-preview" v-if="svgUrl">
    <img :src="svgUrl" class="svg-img" />
  </div>
  <div v-else class="svg-empty">
    <n-text depth="3">暂无 SVG 预览</n-text>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { getFileURL } from '../api/client'
import { NText } from 'naive-ui'

const props = defineProps<{ svgFileId: string }>()
const svgUrl = computed(() => (props.svgFileId ? getFileURL(props.svgFileId) : ''))
</script>

<style scoped>
.svg-img {
  width: 100%;
  border: 1px solid #e0e0e0;
  border-radius: 4px;
}
.svg-empty {
  padding: 40px;
  text-align: center;
}
</style>
