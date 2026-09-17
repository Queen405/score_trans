import type zhApp from '../zh-CN/app'

const app: typeof zhApp = {
  window: {
    controls: 'Window controls',
    minimize: 'Minimize',
    maximize: 'Maximize',
    restore: 'Restore',
    close: 'Close',
  },
  nav: {
    recognize: 'Recognize',
    convert: 'Convert',
    syntax: 'Syntax',
    settings: 'Settings',
  },
  log: {
    title: 'Logs',
    backgroundProcessing: 'Processing in background…',
    runErrors: 'Run {count}',
    syntaxErrors: 'Syntax Errors {count}',
    durationWarnings: 'Duration Warnings {count}',
    runLog: 'Run Log',
    syntaxCheck: 'Syntax Check',
    errorsCount: '{count} errors',
    warningsCount: '{count} warnings',
    showDurationWarnings: 'Show duration warnings',
    hideDurationWarnings: 'Hide duration warnings',
  },
  update: {
    check: 'Check for updates',
    found: 'New version v{version} available — click to download',
    upToDate: 'Up to date',
    failed: 'Failed to check for updates: {error}',
  },
  discard: {
    title: 'Discard unsaved changes?',
    message: 'Changes in Settings have not been applied. Discarding them cannot be undone.',
    continue: 'Keep editing',
    confirm: 'Discard changes',
  },
  close: {
    titleRelaunch: 'Save changes before restart?',
    titleClose: 'Save changes before closing?',
    message: 'You have unsaved changes.',
    blocked: 'A task is in progress. You can save once it finishes.',
    discardRelaunch: 'Restart anyway',
    discardClose: 'Close anyway',
    saveRelaunch: 'Save and Restart',
    saveClose: 'Save and Close',
    relaunchAction: 'restart',
    closeAction: 'close',
    saveFailed: 'Save failed; {action} cancelled: {detail}',
  },
}

export default app
