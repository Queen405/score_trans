<template>
  <div class="ai-assistant">
    <button
      v-show="showFab"
      :class="['ai-fab', { dragging: isFabDragging }, animationClass('fab')]"
      :style="fabStyle"
      type="button"
      title="AI 助手"
      @pointerdown="handleFabPointerDown"
      @pointermove="handleFabPointerMove"
      @pointerup="handleFabPointerUp"
      @pointercancel="handleFabPointerCancel"
    >
      <n-icon size="22"><ChatbubbleEllipsesOutline /></n-icon>
    </button>

    <div
      v-if="showPanel"
      :class="['ai-panel', { 'sessions-collapsed': !sessionsOpen }, animationClass('panel')]"
      :style="panelAnimStyle"
    >
      <aside :class="['ai-sessions', { hidden: !sessionsOpen }]">
        <div class="ai-sessions-head">
          <span>对话</span>
          <n-button size="tiny" quaternary :disabled="assistant.loading" @click="assistant.createSession()">
            <template #icon><n-icon><AddOutline /></n-icon></template>
          </n-button>
        </div>
        <div class="ai-session-list">
          <div
            v-for="session in assistant.sessions"
            :key="session.id"
            :class="['ai-session-item', { active: session.id === assistant.currentSessionId }]"
            role="button"
            tabindex="0"
            @click="assistant.selectSession(session.id)"
            @keydown.enter.prevent="assistant.selectSession(session.id)"
          >
            <span>{{ session.title }}</span>
            <n-popconfirm :show-icon="false" @positive-click="deleteSession(session.id)">
              <template #trigger>
                <button class="ai-session-delete" type="button" title="删除" @click.stop>
                  <n-icon size="13"><TrashOutline /></n-icon>
                </button>
              </template>
              删除这段对话？
            </n-popconfirm>
          </div>
          <div v-if="!assistant.sessions.length && !assistant.loading" class="ai-empty-small">暂无对话</div>
        </div>
      </aside>

      <section class="ai-chat">
        <header
          ref="panelHead"
          :class="['ai-head', { grabbing: isPanelDragging }]"
          @pointerdown="handlePanelPointerDown"
          @pointermove="handlePanelPointerMove"
          @pointerup="handlePanelPointerUp"
          @pointercancel="handlePanelPointerCancel"
        >
          <div class="ai-head-left">
            <button class="ai-icon-btn" type="button" title="历史" @click="sessionsOpen = !sessionsOpen">
              <n-icon><TimeOutline /></n-icon>
            </button>
            <span>AI 助手</span>
          </div>
          <div class="ai-head-actions">
            <label class="ai-think-master" title="关闭后请求会禁用深度思考">
              <input v-model="showThinking" type="checkbox" />
              <span>思考</span>
            </label>
            <button class="ai-icon-btn" type="button" title="收起" @click="closePanel">
              <n-icon><CloseOutline /></n-icon>
            </button>
          </div>
        </header>

        <div ref="messageBody" class="ai-messages" @scroll="handleMessagesScroll" @pointerdown.capture="handleMessagesPointerDown" @keydown.enter.capture="handleMessagesKeydown">
          <div v-if="assistant.loading" class="ai-center">
            <n-spin size="small" />
          </div>
          <div v-else-if="!assistant.messages.length" class="ai-empty">
            <n-icon size="32"><ChatbubbleEllipsesOutline /></n-icon>
            <span>可以问我简谱语法、转写修正或当前文本的问题。</span>
          </div>
          <div
            v-for="message in assistant.messages"
            v-else
            :key="message.id"
            :class="['ai-message', message.role]"
            :data-message-id="message.id"
          >
            <!-- eslint-disable-next-line vue/no-v-html -->
            <div v-if="message.role === 'assistant'" class="ai-message-content ai-md" v-html="renderAssistantMessage(message.content, message.id)" />
            <div v-else class="ai-message-content">{{ message.content }}</div>
          </div>
          <div v-if="showTyping" class="ai-message assistant pending">
            <div class="ai-typing"><span /><span /><span /></div>
          </div>
        </div>

        <div class="ai-compose">
          <label class="ai-context">
            <input v-model="includeCurrentJianpu" type="checkbox" />
            <span>附带当前简谱</span>
          </label>
          <div class="ai-input-row">
            <n-input
              v-model:value="draft"
              type="textarea"
              size="small"
              :autosize="{ minRows: 1, maxRows: 4 }"
              placeholder="问点什么..."
              :disabled="assistant.sending"
              @keydown.enter.exact.prevent="send"
            />
            <n-button type="primary" size="small" :loading="assistant.sending" :disabled="!draft.trim()" @click="send">
              <template #icon><n-icon><SendOutline /></n-icon></template>
            </n-button>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useMessage } from 'naive-ui'
import { useAssistantStore } from '../stores/assistant'
import { useTaskStore } from '../stores/task'
import {
  AddOutline,
  ChatbubbleEllipsesOutline,
  CloseOutline,
  SendOutline,
  TimeOutline,
  TrashOutline,
} from '@vicons/ionicons5'
import { NButton, NIcon, NInput, NPopconfirm, NSpin } from 'naive-ui'

const assistant = useAssistantStore()
const task = useTaskStore()
const notification = useMessage()

const open = computed(() => animPhase.value === 'open' || animPhase.value === 'opening')
const sessionsOpen = ref(true)
const draft = ref('')
const includeCurrentJianpu = ref(true)
const messageBody = ref<HTMLElement | null>(null)
const autoScrollEnabled = ref(true)
const showThinking = ref(true)
const openThinkMessageIds = ref<Set<number>>(new Set())
const isFabDragging = ref(false)
const isPanelDragging = ref(false)
const panelWasDragged = ref(false)
const fabLeft = ref(0)
const fabTop = ref(0)
const panelLeft = ref(24)
const panelTop = ref(48)
const panelHead = ref<HTMLElement | null>(null)
const showTyping = computed(() => (
  assistant.sending &&
  !assistant.messages.some((item) => item.role === 'assistant' && item.id < 0 && item.content.trim())
))
const fabStyle = computed(() => ({
  left: `${fabLeft.value}px`,
  top: `${fabTop.value}px`,
}))
const panelStyle = computed(() => ({
  left: `${panelLeft.value}px`,
  top: `${panelTop.value}px`,
  right: 'auto',
  bottom: 'auto',
}))

// Transition state — single source of truth
type AnimPhase = 'idle' | 'opening' | 'open' | 'closing'
const ANIM_MS = 280
const animPhase = ref<AnimPhase>('idle')
const showPanel = ref(false)
const animOrigin = ref({ x: 0, y: 0 })

/** FAB is visible when not in the 'open' phase (i.e. idle, opening, closing). */
const showFab = computed(() => animPhase.value !== 'open')

/** Panel is mounted during 'opening', 'open', 'closing'. */
watch(animPhase, (phase) => {
  if (phase === 'opening' || phase === 'closing') {
    showPanel.value = true
  }
})

/** Compute transform-origin for the panel based on the FAB's current position. */
const panelAnimStyle = computed(() => {
  const base = { ...panelStyle.value }
  if (animPhase.value === 'opening' || animPhase.value === 'closing') {
    base.transformOrigin = `${animOrigin.value.x}px ${animOrigin.value.y}px`
  }
  return base
})

function animationClass(target: 'fab' | 'panel'): string {
  switch (animPhase.value) {
    case 'opening': return target === 'fab' ? 'anim-fab-exit' : 'anim-panel-enter'
    case 'closing': return target === 'fab' ? 'anim-fab-enter' : 'anim-panel-exit'
    default: return ''
  }
}

function finishAnim(phase: AnimPhase): void {
  if (animPhase.value !== phase) return // user clicked during animation
  if (phase === 'opening') {
    animPhase.value = 'open'
  } else {
    showPanel.value = false
    animPhase.value = 'idle'
  }
}

function openPanel(): void {
  panelWasDragged.value = false
  positionPanelNearFab()
  animOrigin.value = {
    x: fabLeft.value + FAB_SIZE / 2 - panelLeft.value,
    y: fabTop.value + FAB_SIZE / 2 - panelTop.value,
  }
  animPhase.value = 'opening'
  autoScrollEnabled.value = true
  if (!assistant.sessions.length) assistant.loadSessions()
  nextTick(scrollToBottom)
  setTimeout(() => finishAnim('opening'), ANIM_MS)
}

function closePanel(): void {
  if (panelWasDragged.value) {
    anchorFabToPanel()
  }
  animOrigin.value = {
    x: fabLeft.value + FAB_SIZE / 2 - panelLeft.value,
    y: fabTop.value + FAB_SIZE / 2 - panelTop.value,
  }
  animPhase.value = 'closing'
  setTimeout(() => finishAnim('closing'), ANIM_MS)
}

/** When closing the panel, move the FAB to the panel's current location so the bubble follows. */
function anchorFabToPanel(): void {
  const size = getPanelSize()
  const preferLeftSide = panelLeft.value + size.width / 2 < (SIDEBAR_WIDTH + window.innerWidth) / 2
  const nextLeft = preferLeftSide
    ? panelLeft.value
    : panelLeft.value + size.width - FAB_SIZE
  const nextTop = panelTop.value + size.height / 2 - FAB_SIZE / 2
  fabLeft.value = clamp(nextLeft, fabBoundsLeft(), fabBoundsRight())
  fabTop.value = clamp(nextTop, fabBoundsTop(), fabBoundsBottom())
  settleFabPosition()
}

const FAB_SIZE = 46
const FAB_MARGIN = 10
const FAB_SNAP_DISTANCE = 104
const FAB_POSITION_KEY = 'score-trans-ai-assistant-fab'
const PANEL_GAP = 10
const FAB_DOCK_REVEAL = FAB_SIZE / 2 // pixels visible when half-docked

/** Layout boundaries — FAB must stay inside the main content area (right of sidebar, below titlebar). */
const SIDEBAR_WIDTH = 52
const TITLEBAR_HEIGHT = 38

/** Fully inside left boundary. */
function fabBoundsLeft(): number {
  return SIDEBAR_WIDTH + FAB_MARGIN
}
/** Fully inside right boundary. */
function fabBoundsRight(): number {
  return window.innerWidth - FAB_SIZE - FAB_MARGIN
}
/** Fully inside top boundary. */
function fabBoundsTop(): number {
  return TITLEBAR_HEIGHT + FAB_MARGIN
}
/** Fully inside bottom boundary. */
function fabBoundsBottom(): number {
  return window.innerHeight - FAB_SIZE - FAB_MARGIN
}

/** Half-docked left (FAB peeks from left edge of main content). */
function dockLeft(): number {
  return SIDEBAR_WIDTH + FAB_DOCK_REVEAL - FAB_SIZE
}
/** Half-docked right. */
function dockRight(): number {
  return window.innerWidth - FAB_DOCK_REVEAL
}

let fabDrag:
  | {
      pointerId: number
      startX: number
      startY: number
      startLeft: number
      startTop: number
      moved: boolean
    }
  | null = null

let panelDrag:
  | {
      pointerId: number
      startX: number
      startY: number
      startLeft: number
      startTop: number
    }
  | null = null

onMounted(() => {
  initFabPosition()
  window.addEventListener('resize', handleWindowResize)
  assistant.loadSessions()
})

onUnmounted(() => {
  window.removeEventListener('resize', handleWindowResize)
})

watch(
  () => [assistant.messages.map((item) => `${item.id}:${item.content.length}`).join('|'), assistant.sending, open.value],
  () => {
    if (!open.value || !autoScrollEnabled.value) return
    nextTick(scrollToBottom)
  },
)

function handleFabPointerDown(event: PointerEvent): void {
  if (event.button !== 0) return
  const target = event.currentTarget as HTMLElement
  target.setPointerCapture(event.pointerId)
  isFabDragging.value = true
  fabDrag = {
    pointerId: event.pointerId,
    startX: event.clientX,
    startY: event.clientY,
    startLeft: fabLeft.value,
    startTop: fabTop.value,
    moved: false,
  }
}

function handleFabPointerMove(event: PointerEvent): void {
  if (!fabDrag || fabDrag.pointerId !== event.pointerId) return
  const dx = event.clientX - fabDrag.startX
  const dy = event.clientY - fabDrag.startY
  if (Math.abs(dx) > 4 || Math.abs(dy) > 4) fabDrag.moved = true
  fabLeft.value = clamp(fabDrag.startLeft + dx, dockLeft(), dockRight())
  fabTop.value = clamp(fabDrag.startTop + dy, fabBoundsTop(), fabBoundsBottom())
}

function handleFabPointerUp(event: PointerEvent): void {
  if (!fabDrag || fabDrag.pointerId !== event.pointerId) return
  const moved = fabDrag.moved
  endFabDrag(event)
  if (moved) {
    settleFabPosition()
  } else {
    openPanel()
  }
}

function handleFabPointerCancel(event: PointerEvent): void {
  endFabDrag(event)
  settleFabPosition()
}

function endFabDrag(event: PointerEvent): void {
  const target = event.currentTarget as HTMLElement
  if (target.hasPointerCapture(event.pointerId)) target.releasePointerCapture(event.pointerId)
  isFabDragging.value = false
  fabDrag = null
}

function handlePanelPointerDown(event: PointerEvent): void {
  if (event.button !== 0) return
  const target = event.target as HTMLElement | null
  if (target?.closest('button, label, input, a')) return
  panelHead.value?.setPointerCapture(event.pointerId)
  isPanelDragging.value = true
  panelDrag = {
    pointerId: event.pointerId,
    startX: event.clientX,
    startY: event.clientY,
    startLeft: panelLeft.value,
    startTop: panelTop.value,
  }
}

function handlePanelPointerMove(event: PointerEvent): void {
  if (!panelDrag || panelDrag.pointerId !== event.pointerId) return
  const dx = event.clientX - panelDrag.startX
  const dy = event.clientY - panelDrag.startY
  if (Math.abs(dx) > 4 || Math.abs(dy) > 4) panelWasDragged.value = true
  const size = getPanelSize()
  panelLeft.value = clamp(
    panelDrag.startLeft + dx,
    SIDEBAR_WIDTH + PANEL_GAP,
    window.innerWidth - size.width - PANEL_GAP,
  )
  panelTop.value = clamp(
    panelDrag.startTop + dy,
    TITLEBAR_HEIGHT + PANEL_GAP,
    window.innerHeight - size.height - PANEL_GAP,
  )
}

function handlePanelPointerUp(event: PointerEvent): void {
  if (!panelDrag || panelDrag.pointerId !== event.pointerId) return
  endPanelDrag(event)
}

function handlePanelPointerCancel(event: PointerEvent): void {
  endPanelDrag(event)
}

function endPanelDrag(event: PointerEvent): void {
  if (panelHead.value?.hasPointerCapture(event.pointerId)) {
    panelHead.value.releasePointerCapture(event.pointerId)
  }
  isPanelDragging.value = false
  panelDrag = null
}

function initFabPosition(): void {
  const saved = localStorage.getItem(FAB_POSITION_KEY)
  if (saved) {
    try {
      const parsed = JSON.parse(saved) as {
        relX?: number; relY?: number; left?: number; top?: number
        dock?: 'left' | 'right' | null
      }
      // Restore half-dock state if saved
      if (parsed.dock === 'left') {
        fabLeft.value = dockLeft()
        fabTop.value = clamp(
          parsed.relY !== undefined ? fromRelative(0, parsed.relY).top : fabBoundsTop(),
          fabBoundsTop(), fabBoundsBottom(),
        )
        return
      }
      if (parsed.dock === 'right') {
        fabLeft.value = dockRight()
        fabTop.value = clamp(
          parsed.relY !== undefined ? fromRelative(0, parsed.relY).top : fabBoundsTop(),
          fabBoundsTop(), fabBoundsBottom(),
        )
        return
      }

      let relX = parsed.relX
      let relY = parsed.relY

      // 兼容旧格式（绝对像素）
      if (relX === undefined && parsed.left !== undefined) {
        const maxW = Math.max(1, window.innerWidth - FAB_SIZE)
        relX = (parsed.left ?? 0) / maxW
      }
      if (relY === undefined && parsed.top !== undefined) {
        const maxH = Math.max(1, window.innerHeight - FAB_SIZE)
        relY = (parsed.top ?? 0) / maxH
      }

      const { left, top } = fromRelative(relX ?? 1, relY ?? 1)
      fabLeft.value = clamp(left, fabBoundsLeft(), fabBoundsRight())
      fabTop.value = clamp(top, fabBoundsTop(), fabBoundsBottom())
      return
    } catch {
      localStorage.removeItem(FAB_POSITION_KEY)
    }
  }
  fabLeft.value = defaultFabLeft()
  fabTop.value = defaultFabTop()
}

function handleWindowResize(): void {
  initFabPosition()
  if (open.value) positionPanelNearFab()
}

function settleFabPosition(): void {
  // Allow snapping to half-dock on left/right edges of main content
  const dockLeftEdge = fabBoundsLeft()
  const dockRightEdge = fabBoundsRight()

  let dock: 'left' | 'right' | null = null
  if (fabLeft.value - dockLeftEdge <= FAB_SNAP_DISTANCE) {
    fabLeft.value = dockLeft()
    dock = 'left'
  } else if (dockRightEdge - fabLeft.value <= FAB_SNAP_DISTANCE) {
    fabLeft.value = dockRight()
    dock = 'right'
  } else {
    fabLeft.value = clamp(fabLeft.value, fabBoundsLeft(), fabBoundsRight())
  }
  fabTop.value = clamp(fabTop.value, fabBoundsTop(), fabBoundsBottom())
  persistFabPosition(dock)
}

function persistFabPosition(dock?: 'left' | 'right' | null): void {
  const { relX, relY } = toRelative(fabLeft.value, fabTop.value)
  localStorage.setItem(FAB_POSITION_KEY, JSON.stringify({ relX, relY, dock: dock ?? null }))
}

function toRelative(left: number, top: number): { relX: number; relY: number } {
  const maxW = Math.max(1, window.innerWidth - FAB_SIZE)
  const maxH = Math.max(1, window.innerHeight - FAB_SIZE)
  return {
    relX: left / maxW,
    relY: top / maxH,
  }
}

function fromRelative(relX: number, relY: number): { left: number; top: number } {
  const maxW = Math.max(1, window.innerWidth - FAB_SIZE)
  const maxH = Math.max(1, window.innerHeight - FAB_SIZE)
  return {
    left: relX * maxW,
    top: relY * maxH,
  }
}

function defaultFabLeft(): number {
  return dockRight()
}

function defaultFabTop(): number {
  return fabBoundsBottom()
}

function clamp(value: number, min: number, max: number): number {
  if (max < min) return min
  return Math.min(max, Math.max(min, value))
}

function positionPanelNearFab(): void {
  const size = getPanelSize()
  const anchorCenterX = fabLeft.value + FAB_SIZE / 2
  const preferLeftSide = anchorCenterX < (SIDEBAR_WIDTH + window.innerWidth) / 2
  const nextLeft = preferLeftSide
    ? fabLeft.value
    : fabLeft.value + FAB_SIZE - size.width
  const nextTop = fabTop.value + FAB_SIZE / 2 - size.height / 2
  panelLeft.value = clamp(nextLeft, SIDEBAR_WIDTH + PANEL_GAP, window.innerWidth - size.width - PANEL_GAP)
  panelTop.value = clamp(nextTop, TITLEBAR_HEIGHT + PANEL_GAP, window.innerHeight - size.height - PANEL_GAP)
}

function getPanelSize(): { width: number; height: number } {
  if (window.innerWidth <= 760) {
    return {
      width: Math.max(0, window.innerWidth - 28),
      height: Math.max(0, window.innerHeight - 92),
    }
  }
  return {
    width: Math.min(760, window.innerWidth - 96),
    height: Math.min(620, window.innerHeight - 116),
  }
}

async function send(): Promise<void> {
  const text = draft.value.trim()
  if (!text) return
  draft.value = ''
  autoScrollEnabled.value = true
  try {
    await assistant.send(
      text,
      includeCurrentJianpu.value ? task.jianpuText : undefined,
      showThinking.value ? undefined : false,
    )
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e)
    notification.error(msg)
  }
}

async function deleteSession(sessionId: string): Promise<void> {
  try {
    await assistant.deleteSession(sessionId)
    notification.success('已删除')
  } catch (e: unknown) {
    notification.error(e instanceof Error ? e.message : String(e))
  }
}

function scrollToBottom(): void {
  const el = messageBody.value
  if (!el) return
  el.scrollTop = el.scrollHeight
}

function handleMessagesScroll(): void {
  const el = messageBody.value
  if (!el) return
  autoScrollEnabled.value = isNearBottom(el)
}

function handleMessagesPointerDown(event: PointerEvent): void {
  const target = event.target as HTMLElement | null
  const button = target?.closest('.ai-think-toggle') as HTMLButtonElement | null
  if (!button) return
  event.preventDefault()
  event.stopPropagation()
  toggleThinkButton(button)
}

function handleMessagesKeydown(event: KeyboardEvent): void {
  const target = event.target as HTMLElement | null
  const button = target?.closest('.ai-think-toggle') as HTMLButtonElement | null
  if (!button) return
  event.preventDefault()
  event.stopPropagation()
  toggleThinkButton(button)
}

function toggleThinkButton(button: HTMLButtonElement): void {
  const messageId = Number(button.dataset.messageId)
  if (!Number.isFinite(messageId)) return
  setThinkOpen(messageId, !openThinkMessageIds.value.has(messageId))
}

function isNearBottom(el: HTMLElement): boolean {
  return el.scrollHeight - el.scrollTop - el.clientHeight <= 48
}

function setThinkOpen(messageId: number, openValue: boolean): void {
  const next = new Set(openThinkMessageIds.value)
  if (openValue) next.add(messageId)
  else next.delete(messageId)
  openThinkMessageIds.value = next
}

function renderAssistantMessage(text: string, messageId: number): string {
  if (!text) return ''
  const parts: string[] = []
  const thinkRe = /<think>([\s\S]*?)(?:<\/think>|$)/gi
  let lastIndex = 0
  let match: RegExpExecArray | null
  const thinkOpen = openThinkMessageIds.value.has(messageId)
  while ((match = thinkRe.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(renderMarkdown(text.slice(lastIndex, match.index)))
    }
    if (showThinking.value) {
      const label = thinkOpen ? '收起深度思考' : '展开深度思考'
      parts.push(
        `<div class="ai-think ${thinkOpen ? 'open' : ''}">` +
          `<button class="ai-think-toggle" type="button" data-message-id="${messageId}" aria-expanded="${thinkOpen ? 'true' : 'false'}" tabindex="0">${label}</button>` +
          (thinkOpen ? `<div class="ai-think-body">${renderMarkdown(match[1] ?? '')}</div>` : '') +
        '</div>',
      )
    }
    lastIndex = thinkRe.lastIndex
  }
  if (lastIndex < text.length) parts.push(renderMarkdown(text.slice(lastIndex)))
  return parts.join('')
}

function renderMarkdown(source: string): string {
  if (!source.trim()) return ''
  const blocks: string[] = []
  const inlineCodes: string[] = []
  let text = source.replace(/```(\w*)\n?([\s\S]*?)(?:```|$)/g, (_match, lang: string, code: string) => {
    const cls = lang ? ` class="language-${escapeAttr(lang)}"` : ''
    blocks.push(`<pre><code${cls}>${escapeHtml(code.trimEnd())}</code></pre>`)
    return `@@AI_BLOCK_${blocks.length - 1}@@`
  })
  text = text.replace(/`([^`]+)`/g, (_match, code: string) => {
    inlineCodes.push(`<code>${escapeHtml(code)}</code>`)
    return `@@AI_INLINE_${inlineCodes.length - 1}@@`
  })
  text = escapeHtml(text)
  text = text
    .replace(/^### (.+)$/gm, '<h3>$1</h3>')
    .replace(/^## (.+)$/gm, '<h2>$1</h2>')
    .replace(/^# (.+)$/gm, '<h1>$1</h1>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noreferrer">$1</a>')
  text = text.replace(/@@AI_INLINE_(\d+)@@/g, (_match, index: string) => inlineCodes[Number(index)] ?? '')
  text = text.replace(/@@AI_BLOCK_(\d+)@@/g, (_match, index: string) => blocks[Number(index)] ?? '')
  text = renderMarkdownTables(text)
  return wrapMarkdownBlocks(text)
}

function renderMarkdownTables(text: string): string {
  return text.replace(/((?:^\|.*\|\s*$\n?){2,})/gm, (table: string) => {
    const lines = table.trim().split(/\r?\n/)
    if (lines.length < 2 || !/^\|[\s\-:|]+\|$/.test(lines[1].trim())) return table
    const headers = splitTableRow(lines[0])
    const rows = lines.slice(2).map(splitTableRow).filter((row) => row.length)
    if (!headers.length || !rows.length) return table
    return [
      '<div class="ai-table"><table><thead><tr>',
      headers.map((cell) => `<th>${cell}</th>`).join(''),
      '</tr></thead><tbody>',
      rows.map((row) => `<tr>${headers.map((_h, index) => `<td>${row[index] ?? ''}</td>`).join('')}</tr>`).join(''),
      '</tbody></table></div>',
    ].join('')
  })
}

function splitTableRow(line: string): string[] {
  return line.trim().replace(/^\|/, '').replace(/\|$/, '').split('|').map((cell) => cell.trim())
}

function wrapMarkdownBlocks(text: string): string {
  return text.split(/\n{2,}/).map((block) => {
    const trimmed = block.trim()
    if (!trimmed) return ''
    if (/^<(h[1-3]|pre|div class="ai-table")/.test(trimmed)) return trimmed
    const lines = trimmed.split(/\r?\n/)
    if (lines.every((line) => /^\s*[-*]\s+/.test(line))) {
      return `<ul>${lines.map((line) => `<li>${line.replace(/^\s*[-*]\s+/, '')}</li>`).join('')}</ul>`
    }
    if (lines.every((line) => /^\s*\d+\.\s+/.test(line))) {
      return `<ol>${lines.map((line) => `<li>${line.replace(/^\s*\d+\.\s+/, '')}</li>`).join('')}</ol>`
    }
    return `<p>${trimmed.replace(/\n/g, '<br>')}</p>`
  }).join('')
}

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

function escapeAttr(value: string): string {
  return value.replace(/[^a-zA-Z0-9_-]/g, '')
}
</script>

<style scoped>
.ai-assistant {
  position: fixed;
  inset: 0;
  z-index: 30;
  pointer-events: none;
}

.ai-fab {
  position: fixed;
  width: 46px;
  height: 46px;
  border: 1px solid var(--border);
  border-radius: 50%;
  background: var(--bg-elevated);
  color: var(--accent);
  box-shadow: 0 10px 28px rgba(20, 27, 45, 0.18);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  touch-action: none;
  pointer-events: auto;
  transition: left 0.22s cubic-bezier(0.16, 1, 0.3, 1), top 0.22s cubic-bezier(0.16, 1, 0.3, 1), transform 0.15s ease, border-color 0.15s ease;
}

.ai-fab:hover {
  border-color: var(--accent);
  transform: translateY(-1px);
}

.ai-fab.dragging {
  transition: transform 0.15s ease, border-color 0.15s ease;
  transform: scale(0.98);
}

/* ── Transition animations ── */

.ai-fab.anim-fab-exit {
  animation: fab-exit 280ms cubic-bezier(0.2, 0, 0, 1) forwards;
}

.ai-fab.anim-fab-enter {
  animation: fab-enter 280ms cubic-bezier(0.2, 0, 0, 1) forwards;
}

.ai-panel.anim-panel-enter {
  animation: panel-enter 280ms cubic-bezier(0.2, 0, 0, 1) forwards;
}

.ai-panel.anim-panel-exit {
  animation: panel-exit 280ms cubic-bezier(0.2, 0, 0, 1) forwards;
}

@keyframes fab-exit {
  0% { opacity: 1; transform: scale(1); }
  100% { opacity: 0; transform: scale(0.4); }
}

@keyframes fab-enter {
  0% { opacity: 0; transform: scale(0.4); }
  100% { opacity: 1; transform: scale(1); }
}

@keyframes panel-enter {
  0% { opacity: 0; transform: scale(0.3); }
  100% { opacity: 1; transform: scale(1); }
}

@keyframes panel-exit {
  0% { opacity: 1; transform: scale(1); }
  100% { opacity: 0; transform: scale(0.3); }
}

.ai-panel {
  position: fixed;
  right: 24px;
  bottom: 48px;
  width: min(760px, calc(100vw - 96px));
  height: min(620px, calc(100vh - 116px));
  min-height: 420px;
  display: grid;
  grid-template-columns: 210px 1fr;
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  background: var(--bg-elevated);
  box-shadow: 0 18px 56px rgba(20, 27, 45, 0.22);
  overflow: hidden;
  pointer-events: auto;
}

.ai-sessions {
  min-width: 0;
  display: flex;
  flex-direction: column;
  border-right: 1px solid var(--border);
  background: var(--bg-surface);
}

.ai-sessions.hidden {
  display: none;
}

.ai-panel.sessions-collapsed {
  grid-template-columns: 1fr;
}

.ai-sessions-head,
.ai-head {
  height: 42px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 10px;
  border-bottom: 1px solid var(--border);
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
  cursor: grab;
  user-select: none;
}

.ai-head.grabbing {
  cursor: grabbing;
}

.ai-session-list {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 8px;
}

.ai-session-item {
  width: 100%;
  min-height: 32px;
  display: flex;
  align-items: center;
  gap: 6px;
  border: 0;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--text-secondary);
  padding: 6px 8px;
  cursor: pointer;
  text-align: left;
}

.ai-session-item:hover,
.ai-session-item.active {
  background: var(--accent-light);
  color: var(--text-primary);
}

.ai-session-item span {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12px;
}

.ai-session-delete {
  width: 22px;
  height: 22px;
  flex-shrink: 0;
  border: 0;
  border-radius: 4px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: var(--text-tertiary);
  background: transparent;
  cursor: pointer;
}

.ai-session-delete:hover {
  color: var(--danger);
  background: rgba(220, 38, 38, 0.08);
}

.ai-chat {
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.ai-head-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.ai-head-actions {
  display: flex;
  align-items: center;
  gap: 6px;
}

.ai-think-master {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  color: var(--text-tertiary);
  font-size: 12px;
  font-weight: 500;
  user-select: none;
}

.ai-think-master input {
  margin: 0;
  accent-color: var(--accent);
}

.ai-icon-btn {
  width: 28px;
  height: 28px;
  border: 0;
  border-radius: var(--radius-sm);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: var(--text-tertiary);
  background: transparent;
  cursor: pointer;
}

.ai-icon-btn:hover {
  color: var(--text-primary);
  background: var(--accent-light);
}

.ai-messages {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.ai-center,
.ai-empty,
.ai-empty-small {
  color: var(--text-tertiary);
  font-size: 12px;
}

.ai-center,
.ai-empty {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

.ai-empty {
  flex-direction: column;
  gap: 8px;
}

.ai-empty-small {
  padding: 18px 4px;
  text-align: center;
}

.ai-message {
  max-width: 86%;
  border-radius: var(--radius-md);
  padding: 9px 11px;
  font-size: 13px;
  line-height: 1.55;
}

.ai-message.user {
  align-self: flex-end;
  color: #fff;
  background: var(--accent);
}

.ai-message.assistant {
  align-self: flex-start;
  color: var(--text-primary);
  background: var(--bg-surface);
  border: 1px solid var(--border);
}

.ai-message-content {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.ai-md {
  white-space: normal;
}

:deep(.ai-md p) {
  margin: 0 0 8px;
}

:deep(.ai-md p:last-child) {
  margin-bottom: 0;
}

:deep(.ai-md h1),
:deep(.ai-md h2),
:deep(.ai-md h3) {
  margin: 10px 0 6px;
  font-weight: 650;
  line-height: 1.35;
}

:deep(.ai-md h1) { font-size: 16px; }
:deep(.ai-md h2) { font-size: 15px; }
:deep(.ai-md h3) { font-size: 14px; }

:deep(.ai-md code) {
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
  font-size: 0.92em;
  background: rgba(127, 127, 127, 0.14);
  border-radius: 4px;
  padding: 1px 4px;
}

:deep(.ai-md pre) {
  margin: 8px 0;
  padding: 10px;
  border-radius: var(--radius-sm);
  background: #171a20;
  color: #e9ecef;
  overflow-x: auto;
}

:deep(.ai-md pre code) {
  padding: 0;
  background: transparent;
  color: inherit;
}

:deep(.ai-md ul),
:deep(.ai-md ol) {
  margin: 6px 0 8px;
  padding-left: 18px;
}

:deep(.ai-md li) {
  margin: 2px 0;
}

:deep(.ai-md a) {
  color: var(--accent);
  text-decoration: none;
}

:deep(.ai-md a:hover) {
  text-decoration: underline;
}

:deep(.ai-think) {
  margin: 0 0 10px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg-elevated);
}

:deep(.ai-think-toggle) {
  width: 100%;
  border: 0;
  background: transparent;
  cursor: pointer;
  user-select: none;
  padding: 7px 9px;
  color: var(--text-tertiary);
  font-size: 12px;
  font-weight: 600;
  text-align: left;
}

:deep(.ai-think-toggle::before) {
  content: '▸';
  display: inline-block;
  margin-right: 6px;
  transition: transform 0.15s ease;
}

:deep(.ai-think.open .ai-think-toggle::before) {
  transform: rotate(90deg);
}

:deep(.ai-think-body) {
  padding: 0 9px 9px;
  color: var(--text-secondary);
  border-top: 1px dashed var(--border);
}

:deep(.ai-table) {
  margin: 8px 0;
  overflow-x: auto;
}

:deep(.ai-table table) {
  width: 100%;
  border-collapse: collapse;
  white-space: nowrap;
}

:deep(.ai-table th),
:deep(.ai-table td) {
  border: 1px solid var(--border);
  padding: 5px 7px;
  text-align: left;
}

.ai-message.pending {
  min-width: 56px;
}

.ai-typing {
  height: 18px;
  display: flex;
  align-items: center;
  gap: 4px;
}

.ai-typing span {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--text-tertiary);
  animation: ai-bounce 1.2s infinite ease-in-out both;
}

.ai-typing span:nth-child(1) { animation-delay: -0.24s; }
.ai-typing span:nth-child(2) { animation-delay: -0.12s; }

.ai-compose {
  flex-shrink: 0;
  padding: 10px;
  border-top: 1px solid var(--border);
  background: var(--bg-elevated);
}

.ai-context {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 8px;
  color: var(--text-tertiary);
  font-size: 12px;
  user-select: none;
}

.ai-context input {
  margin: 0;
  accent-color: var(--accent);
}

.ai-input-row {
  display: grid;
  grid-template-columns: 1fr 34px;
  gap: 8px;
  align-items: end;
}

@keyframes ai-bounce {
  0%, 80%, 100% { transform: scale(0); opacity: 0.5; }
  40% { transform: scale(1); opacity: 1; }
}

@media (max-width: 760px) {
  .ai-assistant {
    inset: 0;
  }

  .ai-panel {
    right: 14px;
    bottom: 42px;
    width: calc(100vw - 28px);
    height: calc(100vh - 92px);
    min-height: 360px;
    grid-template-columns: 1fr;
  }

  .ai-sessions {
    position: absolute;
    width: min(260px, 82vw);
    inset: 0 auto 0 0;
    z-index: 1;
    box-shadow: 12px 0 24px rgba(20, 27, 45, 0.18);
  }
}
</style>
