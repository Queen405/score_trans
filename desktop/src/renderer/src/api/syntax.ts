import { apiFetch, type ApiResult } from './client'
import type { SyntaxValidateRequest, SyntaxValidateResponse } from '../models/types'

export const syntaxApi = {
  async validate(
    req: SyntaxValidateRequest,
    signal?: AbortSignal,
  ): Promise<ApiResult<SyntaxValidateResponse>> {
    return apiFetch('/syntax/validate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
      signal,
    })
  },
}
