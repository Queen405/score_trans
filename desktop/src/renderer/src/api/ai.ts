import {
  ApiError,
  authenticatedFetch,
  apiFailure,
  apiFetch,
  apiSuccess,
  BASE_URL,
  type ApiResult,
} from './client'
import type {
  AiChatMessage,
  AiChatRequest,
  AiChatResponse,
  AiChatSession,
  AiTranscribeRequest,
  TaskSubmitResponse,
} from '../models/types'

interface ChatStreamHandlers {
  onSession?: (sessionId: string) => void
  onDelta?: (content: string) => void
  onDone?: (response: AiChatResponse) => void
}

export const aiApi = {
  transcribe(req: AiTranscribeRequest): Promise<ApiResult<TaskSubmitResponse>> {
    return apiFetch('/ai/transcribe', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    })
  },

  listChatSessions(): Promise<ApiResult<AiChatSession[]>> {
    return apiFetch('/ai/chat/sessions')
  },

  createChatSession(title?: string): Promise<ApiResult<AiChatSession>> {
    return apiFetch('/ai/chat/sessions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title }),
    })
  },

  getChatMessages(sessionId: string): Promise<ApiResult<AiChatMessage[]>> {
    return apiFetch(`/ai/chat/sessions/${sessionId}/messages`)
  },

  deleteChatSession(sessionId: string): Promise<ApiResult<{ ok: boolean }>> {
    return apiFetch(`/ai/chat/sessions/${sessionId}`, { method: 'DELETE' })
  },

  chat(req: AiChatRequest): Promise<ApiResult<AiChatResponse>> {
    return apiFetch('/ai/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    })
  },

  async streamChat(
    req: AiChatRequest,
    handlers: ChatStreamHandlers,
  ): Promise<ApiResult<void>> {
    try {
      const response = await authenticatedFetch(`${BASE_URL()}/ai/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(req),
      })

      if (!response.ok) {
        const payload = await response.json().catch(() => ({} as Record<string, unknown>))
        const rawMessage = payload.error ?? payload.detail
        throw new ApiError(typeof rawMessage === 'string' ? rawMessage : `HTTP ${response.status}`)
      }
      if (!response.body) throw new ApiError('浏览器不支持流式响应')

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const blocks = buffer.split('\n\n')
        buffer = blocks.pop() ?? ''
        for (const block of blocks) {
          handleSseBlock(block, handlers)
        }
      }
      if (buffer.trim()) handleSseBlock(buffer, handlers)
      return apiSuccess(undefined)
    } catch (error) {
      return apiFailure(error)
    }
  },
}

function handleSseBlock(block: string, handlers: ChatStreamHandlers): void {
  const parsed = parseSseBlock(block)
  if (!parsed) return
  if (parsed.event === 'session') {
    const sessionId = typeof parsed.data.session_id === 'string' ? parsed.data.session_id : ''
    if (sessionId) handlers.onSession?.(sessionId)
    return
  }
  if (parsed.event === 'delta') {
    const content = typeof parsed.data.content === 'string' ? parsed.data.content : ''
    if (content) handlers.onDelta?.(content)
    return
  }
  if (parsed.event === 'done') {
    handlers.onDone?.(parsed.data as AiChatResponse)
    return
  }
  if (parsed.event === 'error') {
    const error = typeof parsed.data.error === 'string' ? parsed.data.error : 'AI 响应中断'
    throw new ApiError(error)
  }
}

function parseSseBlock(block: string): { event: string; data: Record<string, unknown> } | null {
  let event = 'message'
  const dataLines: string[] = []
  for (const line of block.split(/\r?\n/)) {
    if (line.startsWith('event:')) event = line.slice(6).trim()
    if (line.startsWith('data:')) dataLines.push(line.slice(5).trim())
  }
  if (!dataLines.length) return null
  try {
    return { event, data: JSON.parse(dataLines.join('\n')) as Record<string, unknown> }
  } catch {
    return null
  }
}
