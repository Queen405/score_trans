const SHA256 = 'SHA-256'

export async function hashJianpuText(text: string): Promise<string> {
  const bytes = new TextEncoder().encode(text)
  const digest = await globalThis.crypto.subtle.digest(SHA256, bytes)
  return [...new Uint8Array(digest)]
    .map((value) => value.toString(16).padStart(2, '0'))
    .join('')
}

export async function hasJianpuTextEdits(
  currentText: string,
  canonicalText: string,
  canonicalHash: string,
  dirty = false,
): Promise<boolean> {
  if (dirty || currentText !== canonicalText) return true
  if (!canonicalHash) return false
  if (!globalThis.crypto?.subtle) return false
  return (await hashJianpuText(currentText)) !== canonicalHash
}

export function preserveEditedJianpuText(
  currentText: string,
  generatedText: string,
  hasEdits: boolean,
): string {
  return hasEdits ? currentText : generatedText
}
