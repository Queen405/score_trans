import { ref } from 'vue'
import { uploadFile } from '../api/client'
import type { UploadResponse } from '../models/types'

export function useFileUpload() {
  const uploading = ref(false)
  const progress = ref(0)
  const error = ref<string | null>(null)

  async function upload(file: File): Promise<UploadResponse | null> {
    uploading.value = true
    error.value = null
    progress.value = 0
    try {
      const result = await uploadFile(file)
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

  return { uploading, progress, error, upload }
}
