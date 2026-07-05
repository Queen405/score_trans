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

  let streamController: AbortController | null = null
  const streamSessionId = ref('')
  let savedStreamMessages: AiChatMessage[] | null = null

  function abortStream(): void {
    if (streamController) {
      streamController.abort()
      streamController = null
    }
  }

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
    if (sending.value && sessionId === streamSessionId.value) {
      currentSessionId.value = sessionId
      if (savedStreamMessages) {
        messages.value = savedStreamMessages
        savedStreamMessages = null
      }
      return
    }

    if (sending.value && currentSessionId.value === streamSessionId.value) {
      savedStreamMessages = [...messages.value]
    }

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
    if (sending.value && currentSessionId.value === streamSessionId.value) {
      savedStreamMessages = [...messages.value]
    }

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
    if (sending.value && sessionId === streamSessionId.value) {
      abortStream()
      savedStreamMessages = null
    }

    loading.value = true
    error.value = ''
    try {
      await requireData(aiApi.deleteChatSession(sessionId))
      sessions.value = sessions.value.filter((session) => session.id !== sessionId)
      if (currentSessionId.value === sessionId) {
        currentSessionId.value = ''
        messages.value = []
        if (sessions.value.length) await selectSession(sessions.value[0].id)
      }
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : String(e)
    } finally {
      loading.value = false
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
    const controller = new AbortController()
    streamController = controller
    streamSessionId.value = currentSessionId.value
    savedStreamMessages = null
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
            if (controller.signal.aborted) return
            const oldStreamSessionId = streamSessionId.value
            streamSessionId.value = sessionId
            const userOnStream = currentSessionId.value === oldStreamSessionId
            const updateFn = (item: AiChatMessage) => (
              item.id < 0 ? { ...item, session_id: sessionId } : item
            )
            if (userOnStream) {
              currentSessionId.value = sessionId
              messages.value = messages.value.map(updateFn)
            }
            if (savedStreamMessages) {
              savedStreamMessages = savedStreamMessages.map(updateFn)
            }
          },
          onDelta(content) {
            if (controller.signal.aborted) return
            const onStream = currentSessionId.value === streamSessionId.value
            if (onStream) {
              const targetIndex = messages.value.findIndex(
                (item) => item.id === tempAssistantId,
              )
              if (targetIndex >= 0) {
                const target = messages.value[targetIndex]
                messages.value[targetIndex] = {
                  ...target,
                  content: target.content + content,
                }
              }
            }
            if (savedStreamMessages) {
              const savedIndex = savedStreamMessages.findIndex(
                (item) => item.id === tempAssistantId,
              )
              if (savedIndex >= 0) {
                const saved = savedStreamMessages[savedIndex]
                savedStreamMessages[savedIndex] = {
                  ...saved,
                  content: saved.content + content,
                }
              }
            }
          },
          onDone(response) {
            if (controller.signal.aborted) return
            if (currentSessionId.value === streamSessionId.value) {
              messages.value = response.messages
            }
            savedStreamMessages = null
          },
        },
        controller.signal,
      ))
      if (controller.signal.aborted) return
      sessions.value = await requireData(aiApi.listChatSessions())
    } catch (e: unknown) {
      if (controller.signal.aborted) return
      if (currentSessionId.value === streamSessionId.value) {
        error.value = e instanceof Error ? e.message : String(e)
        messages.value = messages.value.filter((item) => item.id !== tempId && item.id !== tempAssistantId)
      }
      savedStreamMessages = null
      throw e
    } finally {
      if (streamController === controller) {
        streamController = null
      }
      streamSessionId.value = ''
      sending.value = false
    }
  }

  return {
    sessions,
    messages,
    currentSessionId,
    streamSessionId,
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
