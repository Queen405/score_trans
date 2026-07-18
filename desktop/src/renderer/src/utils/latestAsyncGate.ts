export class LatestAsyncGate {
  private generation = 0
  private current: Promise<boolean> = Promise.resolve(true)
  private changeSignal = createSignal()
  private readonly disposeSignal = createSignal()
  private disposed = false

  track(task: Promise<unknown>): void {
    if (this.disposed) return
    const previousChangeSignal = this.changeSignal
    this.changeSignal = createSignal()
    this.generation += 1
    this.current = task.then(
      () => true,
      () => false,
    )
    previousChangeSignal.resolve()
  }

  async waitForLatest(): Promise<boolean> {
    while (!this.disposed) {
      const generation = this.generation
      const current = this.current
      const outcome = await Promise.race([
        current.then((value) => ({ kind: 'settled' as const, value })),
        this.changeSignal.promise.then(() => ({ kind: 'changed' as const })),
        this.disposeSignal.promise.then(() => ({ kind: 'disposed' as const })),
      ])
      if (outcome.kind === 'disposed' || this.disposed) return false
      if (outcome.kind === 'changed' || generation !== this.generation) continue
      return outcome.value
    }
    return false
  }

  dispose(): void {
    if (this.disposed) return
    this.disposed = true
    this.generation += 1
    this.changeSignal.resolve()
    this.disposeSignal.resolve()
  }
}

interface Signal {
  promise: Promise<void>
  resolve: () => void
}

function createSignal(): Signal {
  let resolve = (): void => undefined
  const promise = new Promise<void>((resolvePromise) => {
    resolve = resolvePromise
  })
  return { promise, resolve }
}
