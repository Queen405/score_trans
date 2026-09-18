import type zhRuntime from '../zh-CN/runtime'

const runtime: typeof zhRuntime = {
  history: {
    autoSavedBeforeRestore: 'Unsaved changes were auto-saved before restoring the history version',
    autoSaveFailed: 'Auto-save failed; history restore cancelled: {message}',
    saveFailed: 'Failed to save current changes; history restore cancelled: {message}',
    recognizingInProgress: 'A recognition task is in progress. Restore the history after it finishes.',
    loadDetailFailed: 'Failed to load history details: {message}',
    restoredPages: 'Restored {count} pages',
    missingMusicxmlOrText: 'The history entry lacks MusicXML or Jianpu text, so it cannot be rebuilt with the new renderer.',
    rebuiltPages: 'The history entry was rebuilt with the new publication renderer: {count} pages.',
    syntaxError: 'The history entry has a syntax error and cannot be re-rendered. Please fix it first.',
    rebuildFailed: 'Failed to rebuild the score layout: {message}',
    restoredNeedsRerender: 'History data restored, but the score layout needs re-rendering: {message}',
    originalFileExpired: 'Original file expired',
    musicxmlExpired: 'MusicXML expired',
    svgExpired: 'SVG expired',
    omrExpired: 'OMR project file expired',
    sourceMapExpired: 'Source map expired',
    continuousA4Expired: 'Some continuous A4 render pages expired',
    partialExpired: 'History restore partially expired: ',
    rerecognizeOrReupload: ', please re-recognize or re-upload.',
    validateFailed: 'Failed to validate history files: ',
    defaultLabel: 'History',
    scoreTitle: 'Jianpu',
  },
  preview: {
    liveFailed: 'Live preview failed',
  },
  render: {
    requestExpired: 'Render request expired',
  },
  api: {
    networkError: 'Network error',
    streamCancelled: 'Task progress stream cancelled',
    progressCallbackFailed: 'Task progress callback failed',
    taskFailed: 'Task failed',
    queryStatusUnavailable: 'Cannot query task status',
    statusQueryFailed: 'Task status query failed: {message}',
    streamUnsupported: 'This browser does not support streaming responses',
    streamInterrupted: 'Task progress stream interrupted, falling back to polling',
    aiInterrupted: 'AI response interrupted',
  },
}

export default runtime
