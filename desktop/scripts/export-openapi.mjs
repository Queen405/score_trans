import { existsSync } from 'node:fs'
import path from 'node:path'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const projectRoot = path.resolve(here, '../..')
const schemaPath = path.join(projectRoot, 'build', 'openapi.json')
const pythonCandidates = process.platform === 'win32'
  ? [path.join(projectRoot, '.venv', 'Scripts', 'python.exe'), 'python']
  : [path.join(projectRoot, '.venv', 'bin', 'python'), 'python3', 'python']
const python = pythonCandidates.find((candidate) =>
  candidate === 'python' || candidate === 'python3' || existsSync(candidate),
)

const result = spawnSync(
  python,
  [path.join(projectRoot, 'scripts', 'export_openapi.py'), schemaPath],
  {
    cwd: projectRoot,
    env: {
      ...process.env,
      PYTHONPATH: [
        path.join(projectRoot, 'backend'),
        process.env.PYTHONPATH,
      ].filter(Boolean).join(path.delimiter),
    },
    stdio: 'inherit',
  },
)

if (result.error) throw result.error
process.exit(result.status ?? 1)
