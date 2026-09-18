import fs from 'node:fs'
import path from 'node:path'
import ts from 'typescript'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const rendererRoot = path.resolve(here, '../../src/renderer/src')

function transpile(file) {
  return ts.transpileModule(fs.readFileSync(file, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.ES2022, target: ts.ScriptTarget.ES2022 },
    fileName: file,
  }).outputText
}

function url(code) {
  return `data:text/javascript;base64,${Buffer.from(code).toString('base64')}`
}

const zhCnLeaves = ['app', 'common', 'components', 'convert', 'recognize', 'runtime', 'settings', 'syntax']
const messages = {}
for (const name of zhCnLeaves) {
  const leafUrl = url(transpile(path.join(rendererRoot, `i18n/locales/zh-CN/${name}.ts`)))
  messages[name] = (await import(leafUrl)).default
}

const tSource = `
const MESSAGES = ${JSON.stringify(messages)};
function lookup(source, key) {
  let current = source
  for (const segment of key.split('.')) {
    if (typeof current !== 'object' || current === null) return undefined
    current = current[segment]
  }
  return current
}
export function t(key, vars) {
  const raw = lookup(MESSAGES, key)
  if (typeof raw !== 'string') return key
  if (!vars) return raw
  return raw.replace(/\\{(\\w+)\\}/g, (match, name) => (name in vars ? String(vars[name]) : match))
}
`

export const i18nStubUrl = url(tSource)
