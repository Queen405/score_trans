<template>
  <div class="efficiency-dashboard">
    <n-spin
      v-if="loading"
      size="small"
      class="ed-loading"
    />
    <div
      v-else-if="!entries.length"
      class="ed-empty"
    >
      <n-icon
        size="32"
        :depth="3"
      >
        <BarChartOutline />
      </n-icon>
      <span class="ed-empty-text">暂无处理数据</span>
      <span class="ed-empty-hint">完成识别后这里会展示效率统计</span>
    </div>
    <template v-else>
      <div class="ed-stats">
        <div class="ed-stat">
          <span class="ed-stat-value">{{ todayBatchCount }}</span>
          <span class="ed-stat-label">今日批次</span>
        </div>
        <div class="ed-stat">
          <span class="ed-stat-value">{{ todayPageCount }}</span>
          <span class="ed-stat-label">今日页数</span>
        </div>
        <div class="ed-stat">
          <span class="ed-stat-value">{{ successRateText }}</span>
          <span class="ed-stat-label">成功率</span>
        </div>
        <div class="ed-stat">
          <span class="ed-stat-value">{{ avgDurationText }}</span>
          <span class="ed-stat-label">平均耗时</span>
        </div>
      </div>
      <div class="ed-chart">
        <div class="ed-chart-title">
          最近 14 天
        </div>
        <div class="ed-bars">
          <div
            v-for="day in chartDays"
            :key="day.key"
            class="ed-bar-col"
          >
            <div class="ed-bar-track">
              <div
                class="ed-bar"
                :class="{ today: day.isToday }"
                :style="{ height: day.heightPercent + '%' }"
                :title="`${day.label}：${day.count} 个批次`"
              />
            </div>
            <span
              v-if="day.showLabel"
              class="ed-bar-label"
            >{{ day.shortLabel }}</span>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { NIcon, NSpin } from 'naive-ui'
import { BarChartOutline } from '@vicons/ionicons5'
import { historyApi } from '../api/history'
import { listenHistoryUpdated } from '../utils/historyEvents'
import type { HistoryBatchListItem } from '../models/types'

const RANGE_DAYS = 14
const RECENT_LIMIT = 200

const entries = ref<HistoryBatchListItem[]>([])
const loading = ref(false)
let stopListener: (() => void) | null = null

onMounted(() => {
  void load()
  stopListener = listenHistoryUpdated(() => void load(false))
})

onUnmounted(() => {
  stopListener?.()
  stopListener = null
})

async function load(showLoading = true): Promise<void> {
  if (showLoading) loading.value = true
  const { data, error } = await historyApi.list()
  if (error) {
    loading.value = false
    return
  }
  entries.value = (data ?? []).slice(0, RECENT_LIMIT)
  loading.value = false
}

function parseHistoryDate(iso: string): Date | null {
  if (!iso) return null
  const d = new Date(iso.replace(' ', 'T'))
  return isNaN(d.getTime()) ? null : d
}

function isSameDay(a: Date, b: Date): boolean {
  return a.getFullYear() === b.getFullYear()
  && a.getMonth() === b.getMonth()
  && a.getDate() === b.getDate()
}

function startOfDay(d: Date): Date {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate())
}

const todayBatchCount = computed(() => {
  const now = new Date()
  return entries.value.filter((e) => {
    const d = parseHistoryDate(e.created_at)
    return d && isSameDay(d, now)
  }).length
})

const todayPageCount = computed(() => {
  const now = new Date()
  return entries.value
    .filter((e) => {
      const d = parseHistoryDate(e.created_at)
      return d && isSameDay(d, now)
    })
    .reduce((sum, e) => sum + e.page_count, 0)
})

const recentEntries = computed(() => {
  const cutoff = startOfDay(new Date())
  cutoff.setDate(cutoff.getDate() - (RANGE_DAYS - 1))
  return entries.value.filter((e) => {
    const d = parseHistoryDate(e.created_at)
    return d && d >= cutoff
  })
})

const successRateText = computed(() => {
  const list = recentEntries.value
  if (!list.length) return '—'
  const completed = list.filter((e) => e.status === 'completed').length
  return Math.round((completed / list.length) * 100) + '%'
})

const avgDurationText = computed(() => {
  const durations: number[] = []
  for (const e of recentEntries.value) {
    if (!e.last_completed_at) continue
    const start = parseHistoryDate(e.created_at)
    const end = parseHistoryDate(e.last_completed_at)
    if (!start || !end) continue
    const diff = end.getTime() - start.getTime()
    if (diff >= 0) durations.push(diff)
  }
  if (!durations.length) return '—'
  const avgMs = durations.reduce((s, d) => s + d, 0) / durations.length
  return formatDuration(avgMs)
})

function formatDuration(ms: number): string {
  const totalSec = Math.round(ms / 1000)
  if (totalSec < 60) return `${totalSec}秒`
  const min = Math.floor(totalSec / 60)
  const sec = totalSec % 60
  if (min < 60) return sec ? `${min}分${sec}秒` : `${min}分`
  const hour = Math.floor(min / 60)
  return `${hour}时${min % 60}分`
}

const chartDays = computed(() => {
  const today = startOfDay(new Date())
  const days: { key: string; label: string; shortLabel: string; count: number; isToday: boolean; showLabel: boolean; heightPercent: number }[] = []
  const counts = new Map<string, number>()
  for (let i = 0; i < RANGE_DAYS; i++) {
    const d = new Date(today)
    d.setDate(d.getDate() - (RANGE_DAYS - 1 - i))
    counts.set(dateKey(d), 0)
  }
  for (const e of entries.value) {
    const d = parseHistoryDate(e.created_at)
    if (!d) continue
    const key = dateKey(d)
    if (counts.has(key)) counts.set(key, (counts.get(key) ?? 0) + 1)
  }
  const maxCount = Math.max(1, ...counts.values())
  for (let i = 0; i < RANGE_DAYS; i++) {
    const d = new Date(today)
    d.setDate(d.getDate() - (RANGE_DAYS - 1 - i))
    const key = dateKey(d)
    const count = counts.get(key) ?? 0
    const showLabel = i % 2 === 0
    days.push({
      key,
      label: `${d.getMonth() + 1}/${d.getDate()}`,
      shortLabel: showLabel ? `${d.getMonth() + 1}/${d.getDate()}` : '',
      count,
      isToday: i === RANGE_DAYS - 1,
      showLabel,
      heightPercent: count === 0 ? 0 : Math.max(6, Math.round((count / maxCount) * 100)),
    })
  }
  return days
})

function dateKey(d: Date): string {
  return `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`
}
</script>

<style scoped>
.efficiency-dashboard {
  display: flex;
  flex-direction: column;
  gap: 16px;
  flex: 1;
  min-height: 0;
}

.ed-loading {
  align-self: center;
  margin-top: 24px;
}

.ed-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  flex: 1;
  color: var(--text-tertiary);
}

.ed-empty-text {
  font-size: 13px;
  color: var(--text-secondary);
}

.ed-empty-hint {
  font-size: 11px;
}

.ed-stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
  flex-shrink: 0;
}

.ed-stat {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 10px 4px;
  background: var(--bg-surface);
  border-radius: var(--radius-md);
}

.ed-stat-value {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1.1;
}

.ed-stat-label {
  font-size: 11px;
  color: var(--text-tertiary);
}

.ed-chart {
  display: flex;
  flex-direction: column;
  gap: 8px;
  flex: 1;
  min-height: 0;
}

.ed-chart-title {
  font-size: 12px;
  color: var(--text-tertiary);
  font-weight: 500;
}

.ed-bars {
  display: flex;
  align-items: flex-end;
  gap: 4px;
  flex: 1;
  min-height: 80px;
  padding-top: 4px;
}

.ed-bar-col {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  height: 100%;
  min-width: 0;
}

.ed-bar-track {
  flex: 1;
  width: 100%;
  display: flex;
  align-items: flex-end;
  justify-content: center;
  min-height: 0;
}

.ed-bar {
  width: 70%;
  max-width: 18px;
  min-height: 2px;
  border-radius: 3px 3px 0 0;
  background: var(--accent-light);
  transition: height 0.3s ease;
}

.ed-bar.today {
  background: var(--accent);
}

.ed-bar:hover {
  filter: brightness(1.1);
}

.ed-bar-label {
  font-size: 9px;
  color: var(--text-tertiary);
  white-space: nowrap;
}
</style>
