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

const vueStub = url(
  'export const ref = (v) => ({ value: v }); export const computed = (f) => ({ get value() { return f() } })',
)
const naiveStub = url(
  'export const enUS = {}; export const zhCN = {}; export const dateEnUS = {}; export const dateZhCN = {}',
)
const enUsMessagesStub = url('export default {}')

const zhCnLeaves = ['app', 'common', 'components', 'convert', 'recognize', 'runtime', 'settings', 'syntax']
let zhCnBarrel = transpile(path.join(rendererRoot, 'i18n/locales/zh-CN.ts'))
for (const name of zhCnLeaves) {
  const leafUrl = url(transpile(path.join(rendererRoot, `i18n/locales/zh-CN/${name}.ts`)))
  zhCnBarrel = zhCnBarrel.replace(`from './zh-CN/${name}'`, `from '${leafUrl}'`)
}
const zhCnUrl = url(zhCnBarrel)

let i18nIndex = transpile(path.join(rendererRoot, 'i18n/index.ts'))
i18nIndex = i18nIndex.replace("from 'vue'", `from '${vueStub}'`)
i18nIndex = i18nIndex.replace("from 'naive-ui'", `from '${naiveStub}'`)
i18nIndex = i18nIndex.replace("from './locales/en-US'", `from '${enUsMessagesStub}'`)
i18nIndex = i18nIndex.replace("from './locales/zh-CN'", `from '${zhCnUrl}'`)

export const i18nStubUrl = url(i18nIndex)
