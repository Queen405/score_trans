export type CloseIntent = 'close' | 'relaunch'
export type CloseDecision = 'cancel' | 'proceed'

export interface CloseRequest {
  requestId: number
  intent: CloseIntent
}

export type CloseResolution =
  | { kind: 'stale' }
  | { kind: 'cancel' }
  | { kind: 'proceed'; intent: CloseIntent }

export class CloseCoordinator {
  private nextRequestId = 1
  private pending: CloseRequest | null = null

  get pendingRequest(): CloseRequest | null {
    return this.pending
  }

  request(intent: CloseIntent): { request: CloseRequest; isNew: boolean } {
    if (this.pending) return { request: this.pending, isNew: false }
    const request = { requestId: this.nextRequestId, intent }
    this.nextRequestId += 1
    this.pending = request
    return { request, isNew: true }
  }

  resolve(requestId: number, decision: CloseDecision): CloseResolution {
    if (!this.pending || this.pending.requestId !== requestId) return { kind: 'stale' }
    const intent = this.pending.intent
    this.pending = null
    return decision === 'cancel'
      ? { kind: 'cancel' }
      : { kind: 'proceed', intent }
  }
}
