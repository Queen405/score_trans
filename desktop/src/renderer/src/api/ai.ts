import { apiFetch } from './client'
import type {
  AiChatMessage,
  AiChatRequest,
  AiChatResponse,
  AiChatSession,
  AiTranscribeRequest,
  TaskSubmitResponse,
} from '../models/types'

export const aiApi = {
  transcribe(req: AiTranscribeRequest): Promise<TaskSubmitResponse> {
    return apiFetch('/ai/transcribe', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    })
  },

  listChatSessions(): Promise<AiChatSession[]> {
    return apiFetch('/ai/chat/sessions')
  },

  createChatSession(title?: string): Promise<AiChatSession> {
    return apiFetch('/ai/chat/sessions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title }),
    })
  },

  getChatMessages(sessionId: string): Promise<AiChatMessage[]> {
    return apiFetch(`/ai/chat/sessions/${sessionId}/messages`)
  },

  deleteChatSession(sessionId: string): Promise<{ ok: boolean }> {
    return apiFetch(`/ai/chat/sessions/${sessionId}`, { method: 'DELETE' })
  },

  chat(req: AiChatRequest): Promise<AiChatResponse> {
    return apiFetch('/ai/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    })
  },
}
