import { fetchFileBlob } from '../api/client'

type TextLoader = (fileId: string) => Promise<string>
type Waiter = (fileId: string, signal?: AbortSignal) => Promise<string>

function waitWithAbort<T>(promise: Promise<T>, signal?: AbortSignal): Promise<T> {
  if (!signal) return promise
  if (signal.aborted) return Promise.reject(new DOMException('Aborted', 'AbortError'))
  return new Promise<T>((resolve, reject) => {
    const onAbort = () => reject(new DOMException('Aborted', 'AbortError'))
    signal.addEventListener('abort', onAbort, { once: true })
    promise.then(resolve, reject).finally(() => {
      signal.removeEventListener('abort', onAbort)
    })
  })
}

export function createFileTextCache(
  loader: TextLoader,
  capacity = 32,
): Waiter {
  if (!Number.isInteger(capacity) || capacity < 1) {
    throw new RangeError('Cache capacity must be a positive integer')
  }
  const values = new Map<string, string>()
  const pending = new Map<string, Promise<string>>()

  return (fileId, signal) => {
    const cached = values.get(fileId)
    if (cached !== undefined) {
      values.delete(fileId)
      values.set(fileId, cached)
      return waitWithAbort(Promise.resolve(cached), signal)
    }
    let request = pending.get(fileId)
    if (!request) {
      request = loader(fileId)
      pending.set(fileId, request)
      request.then((text) => {
        pending.delete(fileId)
        values.set(fileId, text)
        if (values.size > capacity) {
          const oldest = values.keys().next().value
          if (oldest !== undefined) values.delete(oldest)
        }
      }, () => {
        pending.delete(fileId)
      })
    }
    return waitWithAbort(request, signal)
  }
}

const fileTextCache = createFileTextCache(async (fileId) => {
  const response = await fetchFileBlob(fileId)
  if (response.error) throw response.error
  return response.data.text()
})

export function fetchCachedFileText(fileId: string, signal?: AbortSignal): Promise<string> {
  return fileTextCache(fileId, signal)
}
