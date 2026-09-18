import assert from 'node:assert/strict'
import fs from 'node:fs'
import { promises as fsPromises } from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'

const here = path.dirname(fileURLToPath(import.meta.url))
const projectRoot = path.resolve(here, '..')
const electronStub = `data:text/javascript;base64,${Buffer.from("export const app = { getLocale: () => 'zh-CN', getPath: () => '/tmp' }; export const ipcMain = { handle() {} }").toString('base64')}`
const localeSourcePath = path.join(projectRoot, 'src/main/locale.ts')
const localeCompiled = ts.transpileModule(fs.readFileSync(localeSourcePath, 'utf8'), {
  compilerOptions: {
    module: ts.ModuleKind.ES2022,
    target: ts.ScriptTarget.ES2022,
  },
  fileName: localeSourcePath,
}).outputText.replace("from 'electron'", `from '${electronStub}'`)
const localeStubUrl = `data:text/javascript;base64,${Buffer.from(localeCompiled).toString('base64')}`
const sourcePath = path.join(projectRoot, 'src/main/exportSource.ts')
const source = fs.readFileSync(sourcePath, 'utf8')
const compiled = ts.transpileModule(source, {
  compilerOptions: {
    module: ts.ModuleKind.ES2022,
    target: ts.ScriptTarget.ES2022,
  },
  fileName: sourcePath,
}).outputText.replace("from './locale'", `from '${localeStubUrl}'`)
const exportSource = await import(
  `data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`
)

const exportPathSourcePath = path.join(projectRoot, 'src/main/exportPath.ts')
const exportPathSource = fs.readFileSync(exportPathSourcePath, 'utf8')
const exportPathCompiled = ts.transpileModule(exportPathSource, {
  compilerOptions: {
    module: ts.ModuleKind.ES2022,
    target: ts.ScriptTarget.ES2022,
  },
  fileName: exportPathSourcePath,
}).outputText.replace("from './locale'", `from '${localeStubUrl}'`)
const exportPath = await import(
  `data:text/javascript;base64,${Buffer.from(exportPathCompiled).toString('base64')}`
)

test('export IPC accepts an ArrayBuffer and preserves bytes', () => {
  const sourceBuffer = Uint8Array.from([0, 1, 127, 255]).buffer

  const result = exportSource.exportSourceBuffer({ buffer: sourceBuffer })

  assert.deepEqual([...result], [0, 1, 127, 255])
})

test('export IPC rejects renderer-provided URLs and fake buffers', () => {
  for (const source of [
    { url: 'http://127.0.0.1:19200/files/private' },
    { url: 'http://169.254.169.254/latest/meta-data/' },
    { url: 'file:///C:/Windows/win.ini' },
    { buffer: new Uint8Array([1, 2, 3]) },
    { buffer: 'not-bytes' },
    null,
  ]) {
    assert.throws(
      () => exportSource.exportSourceBuffer(source),
      /ArrayBuffer/,
    )
  }
})

test('main export handler has no network request primitive', () => {
  const handler = fs.readFileSync(
    path.join(projectRoot, 'src/main/files.ts'),
    'utf8',
  )

  assert.doesNotMatch(handler, /\bfetch\s*\(/)
  assert.doesNotMatch(handler, /\{\s*url:\s*string\s*\}/)
})

test('export filenames cannot become traversal or Windows device paths', () => {
  const cases = new Map([
    ['..', 'export'],
    ['../outside.txt', '_outside.txt'],
    ['CON.txt', '_CON.txt'],
    ['LPT9', '_LPT9'],
    ['report. ', 'report'],
    ['a/b:c?.pdf', 'a_b_c_.pdf'],
  ])

  for (const [input, expected] of cases) {
    assert.equal(exportPath.sanitizeExportFilename(input), expected)
  }
})

test('export writes stay in the canonical directory and remain unique', async () => {
  const root = await fsPromises.mkdtemp(path.join(process.cwd(), '.export-test-'))
  try {
    const outputDir = path.join(root, 'output')
    const first = await exportPath.writeUniqueExportFile(
      outputDir,
      '../score.pdf',
      Buffer.from('first'),
    )
    const second = await exportPath.writeUniqueExportFile(
      outputDir,
      '../score.pdf',
      Buffer.from('second'),
    )
    const canonicalDir = await fsPromises.realpath(outputDir)

    assert.equal(path.dirname(first), canonicalDir)
    assert.equal(path.dirname(second), canonicalDir)
    assert.equal(path.basename(first), '_score.pdf')
    assert.equal(path.basename(second), '_score(1).pdf')
    assert.equal(await fsPromises.readFile(first, 'utf8'), 'first')
    assert.equal(await fsPromises.readFile(second, 'utf8'), 'second')
    await assert.rejects(
      exportPath.writeUniqueExportFile(
        `${outputDir}${path.sep}..${path.sep}escaped`,
        'bad.txt',
        Buffer.from('bad'),
      ),
      /遍历/,
    )
  } finally {
    await fsPromises.rm(root, { recursive: true, force: true })
  }
})

test('export rejects a directory redirected through a symbolic link', async (t) => {
  const root = await fsPromises.mkdtemp(path.join(os.tmpdir(), 'score-trans-link-'))
  try {
    const outside = path.join(root, 'outside')
    const linked = path.join(root, 'linked')
    await fsPromises.mkdir(outside)
    try {
      await fsPromises.symlink(
        outside,
        linked,
        process.platform === 'win32' ? 'junction' : 'dir',
      )
    } catch {
      t.skip('symbolic links are unavailable in this environment')
      return
    }

    await assert.rejects(
      exportPath.writeUniqueExportFile(linked, 'score.pdf', Buffer.from('bad')),
      /符号链接|重解析点/,
    )
  } finally {
    await fsPromises.rm(root, { recursive: true, force: true })
  }
})
