import { execFile, type ChildProcess } from 'node:child_process'

function hasExited(child: ChildProcess): boolean {
  return child.exitCode !== null || child.signalCode !== null
}

function waitForExit(child: ChildProcess, timeoutMs: number): Promise<boolean> {
  if (hasExited(child)) return Promise.resolve(true)

  return new Promise((resolve) => {
    let settled = false
    const finish = (exited: boolean): void => {
      if (settled) return
      settled = true
      clearTimeout(timeout)
      child.removeListener('exit', onExit)
      resolve(exited)
    }
    const onExit = (): void => finish(true)
    const timeout = setTimeout(() => finish(hasExited(child)), timeoutMs)
    child.once('exit', onExit)
    if (hasExited(child)) finish(true)
  })
}

function killWindowsTree(pid: number, force: boolean): Promise<void> {
  return new Promise((resolve) => {
    const args = ['/T']
    if (force) args.push('/F')
    args.push('/PID', String(pid))
    execFile(
      'taskkill',
      args,
      { windowsHide: true },
      () => resolve(),
    )
  })
}

export async function terminateChildProcess(
  child: ChildProcess,
  timeoutMs: number,
): Promise<void> {
  if (hasExited(child)) return
  const pid = child.pid
  if (!pid) return

  if (process.platform === 'win32') {
    await killWindowsTree(pid, false)
  } else {
    try {
      child.kill('SIGTERM')
    } catch {
      // The process may have exited between the state check and signal.
    }
  }
  if (await waitForExit(child, timeoutMs)) return

  if (process.platform === 'win32') {
    await killWindowsTree(pid, true)
  } else {
    try {
      child.kill('SIGKILL')
    } catch {
      // The process may have exited before the force signal.
    }
  }

  if (!(await waitForExit(child, timeoutMs))) {
    throw new Error(`Backend process ${pid} did not exit after forced termination`)
  }
}
