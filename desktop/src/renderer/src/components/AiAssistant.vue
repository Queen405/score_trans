<template>
  <div class="ai-assistant">
    <button v-if="!open" class="ai-fab" type="button" title="AI 助手" @click="openPanel">
      <n-icon size="22"><ChatbubbleEllipsesOutline /></n-icon>
    </button>

    <div v-else :class="['ai-panel', { 'sessions-collapsed': !sessionsOpen }]">
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
        <header class="ai-head">
          <div class="ai-head-left">
            <button class="ai-icon-btn" type="button" title="历史" @click="sessionsOpen = !sessionsOpen">
              <n-icon><TimeOutline /></n-icon>
            </button>
            <span>AI 助手</span>
          </div>
          <button class="ai-icon-btn" type="button" title="收起" @click="open = false">
            <n-icon><CloseOutline /></n-icon>
          </button>
        </header>

        <div ref="messageBody" class="ai-messages">
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
          >
            <div class="ai-message-content">{{ message.content }}</div>
          </div>
          <div v-if="assistant.sending" class="ai-message assistant pending">
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
import { nextTick, onMounted, ref, watch } from 'vue'
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
const message = useMessage()

const open = ref(false)
const sessionsOpen = ref(true)
const draft = ref('')
const includeCurrentJianpu = ref(true)
const messageBody = ref<HTMLElement | null>(null)

onMounted(() => {
  assistant.loadSessions()
})

watch(
  () => [assistant.messages.length, assistant.sending, open.value],
  () => {
    nextTick(scrollToBottom)
  },
)

function openPanel(): void {
  open.value = true
  if (!assistant.sessions.length) assistant.loadSessions()
  nextTick(scrollToBottom)
}

async function send(): Promise<void> {
  const text = draft.value.trim()
  if (!text) return
  draft.value = ''
  try {
    await assistant.send(text, includeCurrentJianpu.value ? task.jianpuText : undefined)
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e)
    message.error(msg)
  }
}

async function deleteSession(sessionId: string): Promise<void> {
  try {
    await assistant.deleteSession(sessionId)
    message.success('已删除')
  } catch (e: unknown) {
    message.error(e instanceof Error ? e.message : String(e))
  }
}

function scrollToBottom(): void {
  const el = messageBody.value
  if (!el) return
  el.scrollTop = el.scrollHeight
}
</script>

<style scoped>
.ai-assistant {
  position: fixed;
  right: 24px;
  bottom: 48px;
  z-index: 30;
}

.ai-fab {
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
  transition: transform 0.15s ease, border-color 0.15s ease;
}

.ai-fab:hover {
  border-color: var(--accent);
  transform: translateY(-1px);
}

.ai-panel {
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
    right: 14px;
    bottom: 42px;
  }

  .ai-panel {
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
