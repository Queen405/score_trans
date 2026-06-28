import { requireData } from '../api/client'
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { aiApi } from '../api/ai'
import type { AiChatMessage, AiChatSession } from '../models/types'

export const useAssistantStore = defineStore('assistant', () => {
  const sessions = ref<AiChatSession[]>([])
  const messages = ref<AiChatMessage[]>([])
  const currentSessionId = ref('')
  const loading = ref(false)
  const sending = ref(false)
  const error = ref('')

  async function loadSessions(): Promise<void> {
    loading.value = true
    error.value = ''
    try {
      sessions.value = await requireData(aiApi.listChatSessions())
      if (!currentSessionId.value && sessions.value.length) {
        await selectSession(sessions.value[0].id)
      }
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : String(e)
    } finally {
      loading.value = false
    }
  }

  async function selectSession(sessionId: string): Promise<void> {
    currentSessionId.value = sessionId
    loading.value = true
    error.value = ''
    try {
      messages.value = await requireData(aiApi.getChatMessages(sessionId))
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : String(e)
      messages.value = []
    } finally {
      loading.value = false
    }
  }

  async function createSession(): Promise<void> {
    loading.value = true
    error.value = ''
    try {
      const session = await requireData(aiApi.createChatSession())
      sessions.value = [session, ...sessions.value.filter((item) => item.id !== session.id)]
      currentSessionId.value = session.id
      messages.value = []
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : String(e)
    } finally {
      loading.value = false
    }
  }

  async function deleteSession(sessionId: string): Promise<void> {
    await requireData(aiApi.deleteChatSession(sessionId))
    sessions.value = sessions.value.filter((session) => session.id !== sessionId)
    if (currentSessionId.value === sessionId) {
      currentSessionId.value = ''
      messages.value = []
      if (sessions.value.length) await selectSession(sessions.value[0].id)
    }
  }

  async function send(message: string, jianpuText?: string, enableThinking?: boolean): Promise<void> {
    const text = message.trim()
    if (!text || sending.value) return

    const tempId = -Date.now()
    const tempAssistantId = tempId - 1
    messages.value.push({
      id: tempId,
      session_id: currentSessionId.value,
      role: 'user',
      content: text,
      created_at: '',
    })
    messages.value.push({
      id: tempAssistantId,
      session_id: currentSessionId.value,
      role: 'assistant',
      content: '',
      created_at: '',
    })
    sending.value = true
    error.value = ''
    try {
      await requireData(aiApi.streamChat(
        {
          message: text,
          session_id: currentSessionId.value || undefined,
          jianpu_text: jianpuText?.trim() || undefined,
          enable_thinking: enableThinking,
        },
        {
          onSession(sessionId) {
            currentSessionId.value = sessionId
            messages.value = messages.value.map((item) => (
              item.id < 0 ? { ...item, session_id: sessionId } : item
            ))
          },
          onDelta(content) {
            const target = messages.value.find((item) => item.id === tempAssistantId)
            if (target) target.content += content
          },
          onDone(response) {
            messages.value = response.messages
          },
        },
      ))
      sessions.value = await requireData(aiApi.listChatSessions())
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : String(e)
      messages.value = messages.value.filter((item) => item.id !== tempId && item.id !== tempAssistantId)
      throw e
    } finally {
      sending.value = false
    }
  }

  return {
    sessions,
    messages,
    currentSessionId,
    loading,
    sending,
    error,
    loadSessions,
    selectSession,
    createSession,
    deleteSession,
    send,
  }
})
