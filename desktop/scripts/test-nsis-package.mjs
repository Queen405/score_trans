import assert from 'node:assert/strict'
import { mkdir, mkdtemp, readFile, realpath, rm, writeFile } from 'node:fs/promises'
import { createRequire } from 'node:module'
import { tmpdir } from 'node:os'
import { dirname, join } from 'node:path'
import test from 'node:test'

const require = createRequire(import.meta.url)
const fromBuilder = createRequire(require.resolve('electron-builder/package.json'))
// Initialize the public entrypoint before accessing the target (internal circular imports).
fromBuilder('app-builder-lib')
const fromLib = createRequire(fromBuilder.resolve('app-builder-lib/package.json'))
const { NsisTarget } = fromLib('./out/targets/nsis/NsisTarget.js')
const { Arch } = fromLib('builder-util')
const yaml = fromLib('js-yaml')

// A config-only assertion would miss electron-builder overriding the archive format.
// Exercise the locked builder with a tiny payload; no installer or app is launched.
test('the actual NSIS payload matches the configured installer decoder', async (t) => {
  const temporaryRoot = await realpath(tmpdir())
  const work = await mkdtemp(join(temporaryRoot, 'score-trans-nsis-'))
  t.after(async () => {
    assert.equal(dirname(work), temporaryRoot)
    await rm(work, { recursive: true, force: true })
  })
  const app = join(work, 'app')
  const out = join(work, 'out')
  await mkdir(app)
  await mkdir(out)
  await writeFile(join(app, 'payload.txt'), 'Score Trans archive compatibility check')
  const config = yaml.load(await readFile(new URL('../electron-builder.yml', import.meta.url), 'utf8'))
  const packager = {
    config,
    info: { metadata: {} },
    compression: 'normal',
    appInfo: {
      sanitizedName: 'archive-probe', version: '1.0.0',
      productFilename: 'archive-probe', updaterCacheDirName: 'archive-probe-updater',
    },
  }
  const target = new NsisTarget(packager, out, 'nsis', { refCount: 0 })
  const archive = await target.buildAppPackage(app, Arch.x64)
  const defines = { APP_FILENAME: 'archive-probe' }
  target.configureDefinesForAllTypeOfInstaller(defines)
  const signatures = {
    zip: Buffer.from([0x50, 0x4b, 0x03, 0x04]),
    '7z': Buffer.from([0x37, 0x7a, 0xbc, 0xaf, 0x27, 0x1c]),
  }
  const expected = signatures[defines.COMPRESSION_METHOD]
  assert.ok(expected, `Unknown NSIS compression: ${defines.COMPRESSION_METHOD}`)
  const bytes = await readFile(archive.path)
  assert.deepEqual(
    bytes.subarray(0, expected.length), expected,
    `NSIS selects ${defines.COMPRESSION_METHOD} extraction but built ${archive.path}`,
  )
  assert.ok(archive.path.endsWith(`.nsis.${defines.COMPRESSION_METHOD}`))
  assert.equal(Object.hasOwn(defines, 'ZIP_COMPRESSION'), defines.COMPRESSION_METHOD === 'zip')
})
