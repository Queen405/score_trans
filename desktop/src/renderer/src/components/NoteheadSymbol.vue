<template>
  <svg
    class="notehead-symbol"
    :class="{ 'transparent-hollow': !background }"
    viewBox="0 0 32 24"
    aria-hidden="true"
  >
    <rect
      v-if="kind === 'whole-rest'"
      x="7"
      y="11"
      width="18"
      height="6"
      rx="1"
    />
    <rect
      v-else-if="kind === 'half-rest'"
      x="7"
      y="7"
      width="18"
      height="6"
      rx="1"
    />
    <path
      v-else-if="kind === 'rest'"
      d="M16 2 12 9l6 3-5 4 5 6-1 2-5-6 4-5-6-3 4-7z"
    />
    <g v-else transform="rotate(-24 16 12)">
      <polygon
        v-if="kind === 'diamond'"
        points="16,3 27,12 16,21 5,12"
        :class="{ hollow: !filled }"
      />
      <polygon
        v-else-if="kind === 'triangle'"
        points="5,5 27,5 16,20"
        :class="{ hollow: !filled }"
      />
      <g v-else-if="kind === 'cross'">
        <path d="M7 5h18v5H7zM13 3h6v18h-6z" />
        <path
          v-if="!filled"
          d="M10 8h12v1H10zM15 6h2v12h-2z"
          class="cutout"
        />
      </g>
      <g v-else-if="kind === 'circle-x'">
        <circle
          cx="16"
          cy="12"
          r="9"
          :class="{ hollow: !filled }"
        />
        <path d="m10 7 12 10-2 2L8 9zM22 7 10 19l-2-2L20 5z" />
      </g>
      <ellipse
        v-else
        cx="16"
        cy="12"
        rx="11"
        ry="7"
        :class="{ hollow: !filled }"
      />
    </g>
  </svg>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(defineProps<{ shape: string; background?: boolean }>(), {
  background: true,
})
const kind = computed(() => {
  if (props.shape.includes('REST')) {
    if (props.shape.includes('WHOLE') || props.shape.includes('BREVE')) return 'whole-rest'
    if (props.shape.includes('HALF')) return 'half-rest'
    return 'rest'
  }
  if (props.shape.includes('DIAMOND')) return 'diamond'
  if (props.shape.includes('TRIANGLE')) return 'triangle'
  if (props.shape.includes('CIRCLE_X')) return 'circle-x'
  if (props.shape.includes('CROSS')) return 'cross'
  return 'oval'
})
const filled = computed(() => /BLACK|FILLED/.test(props.shape))
</script>

<style scoped>
.notehead-symbol {
  width: 30px;
  height: 24px;
  overflow: visible;
  color: currentColor;
}

ellipse,
polygon,
circle,
rect {
  fill: currentColor;
  stroke: currentColor;
  stroke-width: 2;
  stroke-linejoin: round;
}

.hollow {
  fill: var(--bg-elevated);
}

path {
  fill: currentColor;
}

.cutout {
  fill: var(--bg-elevated);
}

.transparent-hollow .hollow,
.transparent-hollow .cutout {
  fill: none;
}
</style>
