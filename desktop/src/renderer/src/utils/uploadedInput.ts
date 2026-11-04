import type { UploadResponse, UploadedInputPage } from '../models/types'

export function uploadedInputPages(result: UploadResponse): UploadedInputPage[] {
  const sourceDocument = result.filename.toLowerCase().endsWith('.pdf')
    ? {
        sourceDocumentFileId: result.file_id,
        sourceDocumentName: result.filename,
      }
    : { sourceDocumentFileId: '', sourceDocumentName: '' }
  if (result.pages?.length) {
    return result.pages.map((page) => ({
      inputFileId: page.file_id,
      inputFileName: page.filename,
      ...sourceDocument,
      sourcePageIndex: page.page_index,
      sourceRotation: 0,
    }))
  }
  return [{
    inputFileId: result.file_id,
    inputFileName: result.filename,
    sourceDocumentFileId: '',
    sourceDocumentName: '',
    sourcePageIndex: -1,
    sourceRotation: 0,
  }]
}
