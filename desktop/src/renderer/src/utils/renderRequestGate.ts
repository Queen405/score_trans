export class RenderRequestGate {
  private generation = 0
  private controller: AbortController | null = null
  private disposed = false

  async current<T>(request: (signal: AbortSignal) => Promise<T>): Promise<T> {
    if (this.disposed) throw new DOMException('aborted', 'AbortError')

    this.controller?.abort()
    const controller = new AbortController()
    this.controller = controller
    const generation = ++this.generation
    const result = await request(controller.signal)

    if (this.disposed || generation !== this.generation) {
      throw new DOMException('渲染请求已过期', 'AbortError')
    }
    return result
  }

  cancel(): void {
    this.controller?.abort()
  }

  dispose(): void {
    if (this.disposed) return
    this.disposed = true
    this.generation += 1
    this.controller?.abort()
    this.controller = null
  }
}
