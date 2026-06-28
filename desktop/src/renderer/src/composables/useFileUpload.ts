import { ref } from 'vue'
import { requireData, uploadFile, type UploadProgressCallback } from '../api/client'
import type { UploadResponse } from '../models/types'

export function useFileUpload() {
  const uploading = ref(false)
  const progress = ref(0)
  const phase = ref<'upload' | 'processing'>('upload')
  const error = ref<string | null>(null)

  async function upload(file: File): Promise<UploadResponse | null> {
    uploading.value = true
    error.value = null
    progress.value = 0
    phase.value = 'upload'
    try {
      const onProgress: UploadProgressCallback = (pct, p) => {
        progress.value = pct
        phase.value = p
      }
      const result = await requireData(uploadFile(file, onProgress))
      progress.value = 100
      return result
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e)
      error.value = msg
      return null
    } finally {
      uploading.value = false
    }
  }

  return { uploading, progress, phase, error, upload }
}
