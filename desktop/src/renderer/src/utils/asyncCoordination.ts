export interface KeyedAsyncQueue<Key> {
  enqueue<Result>(key: Key, operation: () => Promise<Result>): Promise<Result>
}

export function createKeyedAsyncQueue<Key>(): KeyedAsyncQueue<Key> {
  const tails = new Map<Key, Promise<void>>()

  return {
    enqueue<Result>(key: Key, operation: () => Promise<Result>): Promise<Result> {
      const previous = tails.get(key) ?? Promise.resolve()
      const result = previous.then(operation, operation)
      const tail = result.then(
        () => undefined,
        () => undefined,
      )
      tails.set(key, tail)
      void tail.then(() => {
        if (tails.get(key) === tail) tails.delete(key)
      })
      return result
    },
  }
}

export interface RequestEpoch {
  begin(): number
  invalidate(): void
  isCurrent(token: number): boolean
}

export function createRequestEpoch(): RequestEpoch {
  let current = 0
  return {
    begin(): number {
      current += 1
      return current
    },
    invalidate(): void {
      current += 1
    },
    isCurrent(token: number): boolean {
      return token === current
    },
  }
}
