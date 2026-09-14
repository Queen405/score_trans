import assert from 'node:assert/strict'
import { test } from 'node:test'
import { mkdtemp, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { createHash } from 'node:crypto'
import { CosClient, compareVersions, configFromEnv, loadSnapshot, main } from './upload-cos.mjs'

const config = configFromEnv({ COS_BUCKET: 'test-123', COS_REGION: 'ap-test', COS_PREFIX: 'isolated' })
const hash = (bytes) => createHash('sha256').update(bytes).digest('hex')

function remote() {
  const objects = new Map(), calls = [], parts = []
  let fail = null
  const fetchImpl = async (url, options) => {
    const parsed = new URL(url), key = decodeURIComponent(parsed.pathname).slice(1)
    calls.push({ method: options.method, key, params: parsed.searchParams, headers: options.headers })
    if (fail?.(options.method, key, parsed.searchParams)) return new Response('', { status: 503 })
    if (options.method === 'HEAD') return new Response(null, { status: objects.has(key) ? 200 : 404 })
    if (options.method === 'GET') return new Response(objects.get(key) ?? null, { status: objects.has(key) ? 200 : 404 })
    if (options.method === 'POST' && parsed.searchParams.has('uploads')) return new Response('<UploadId>abc</UploadId>')
    if (options.method === 'PUT' && parsed.searchParams.has('partNumber')) {
      parts[Number(parsed.searchParams.get('partNumber')) - 1] = Buffer.from(options.body)
      return new Response(null, { headers: { etag: '"abcdef"' } })
    }
    if (options.method === 'POST') {
      objects.set(key, Buffer.concat(parts))
      return new Response('<CompleteMultipartUploadResult/>')
    }
    if (options.method === 'PUT') { objects.set(key, options.body); return new Response(null) }
    if (options.method === 'DELETE') return new Response(null)
    throw new Error('Unexpected request')
  }
  return { objects, calls, setFailure: (value) => { fail = value },
    client: new CosClient(config, { fetchImpl, sleep: async () => {} }) }
}

async function fixture(t, client, version = '1.2.3') {
  const dir = await mkdtemp(join(tmpdir(), 'cos-test-'))
  t.after(() => rm(dir, { recursive: true, force: true }))
  const names = [`Score Trans Setup ${version}.exe`, `Score Trans-${version}-arm64.dmg`]
  const manifest = { version, url: client.url(client.key(names[0])), urlMac: client.url(client.key(names[1])), notes: 'test' }
  const text = JSON.stringify(manifest, null, 2) + '\n'
  const entries = [[names[0], 'windows'], [names[1], 'mac'], ['latest.json', text]]
  for (const [name, bytes] of entries) await writeFile(join(dir, name), bytes)
  const checksumPath = join(dir, 'SHA256SUMS.txt')
  await writeFile(checksumPath, entries.map(([name, bytes]) => `${hash(bytes)}  ${name}\n`).join(''))
  return loadSnapshot(join(dir, 'latest.json'), checksumPath, client)
}

test('default and empty config agree; custom destination remains explicit', () => {
  assert.deepEqual(configFromEnv({}), configFromEnv({ COS_BUCKET: '', COS_REGION: '', COS_PREFIX: '' }))
  assert.equal(config.bucket, 'test-123')
  assert.throws(() => configFromEnv({ COS_PREFIX: '../download' }))
})

test('versions compare numerically, including values beyond JS integer precision', () => {
  assert.equal(compareVersions('1.10.0', '1.9.9'), 1)
  assert.equal(compareVersions('1.2.3', '1.2.3'), 0)
  assert.equal(compareVersions('1.2.3', '2.0.0'), -1)
  assert.equal(compareVersions('9007199254740993.0.0', '9007199254740992.0.0'), 1)
  assert.throws(() => compareVersions('v1.2.3', '1.2.3'))
})

test('complete upload, promotion and retry preserve identical manifest bytes', async (t) => {
  const r = remote(), snapshot = await fixture(t, r.client)
  await r.client.artifacts(snapshot)
  assert.equal(r.objects.has(r.client.key('latest.json')), false)
  assert.deepEqual(await r.client.promote(snapshot), { status: 'promoted' })
  assert.equal(r.objects.get(r.client.key('latest.json')), snapshot.text)
  const writes = r.calls.filter((c) => c.method === 'POST' || c.method === 'PUT').length
  await r.client.artifacts(snapshot)
  assert.deepEqual(await r.client.promote(snapshot), { status: 'unchanged' })
  assert.equal(r.calls.filter((c) => c.method === 'POST' || c.method === 'PUT').length, writes)
})

test('older release is archived without replacing the latest manifest', async (t) => {
  const r = remote(), snapshot = await fixture(t, r.client)
  const newer = JSON.stringify({ version: '1.3.0', url: 'https://example.test/new.exe' })
  r.objects.set(r.client.key('latest.json'), newer)
  await r.client.artifacts(snapshot)
  assert.deepEqual(await r.client.promote(snapshot), { status: 'older' })
  assert.equal(r.objects.get(r.client.key('latest.json')), newer)
})

test('same-version manifest conflict and changed installer cannot be overwritten', async (t) => {
  const r = remote(), snapshot = await fixture(t, r.client)
  r.objects.set(r.client.key('latest.json'), JSON.stringify(snapshot.manifest))
  await assert.rejects(r.client.promote(snapshot), /different manifest bytes/)
  r.objects.set(r.client.key('Score Trans Setup 1.2.3.exe'), 'different')
  await assert.rejects(r.client.artifacts(snapshot), /immutable snapshot/)
  assert.equal(r.calls.some((c) => c.method === 'POST'), false)
})

test('failed multipart upload is aborted and never promotes the manifest', async (t) => {
  const r = remote(), snapshot = await fixture(t, r.client)
  r.setFailure((method, _key, params) => method === 'PUT' && params.has('partNumber'))
  await assert.rejects(r.client.artifacts(snapshot), /HTTP 503/)
  assert.equal(r.calls.filter((c) => c.method === 'PUT').length, 3)
  assert.equal(r.calls.filter((c) => c.method === 'DELETE').length, 1)
  assert.equal(r.objects.size, 0)
  r.setFailure(null)
  await r.client.artifacts(snapshot)
  await r.client.promote(snapshot)
})

test('manifest write failure resumes after installers have already been uploaded', async (t) => {
  const r = remote(), snapshot = await fixture(t, r.client)
  await r.client.artifacts(snapshot)
  r.setFailure((method, key) => method === 'PUT' && key.endsWith('/latest.json'))
  await assert.rejects(r.client.promote(snapshot), /HTTP 503/)
  assert.equal(r.objects.size, 2)
  r.setFailure(null)
  await r.client.artifacts(snapshot)
  assert.equal((await r.client.promote(snapshot)).status, 'promoted')
})

test('only 404 initializes a channel; authorization errors and malformed JSON fail closed', async () => {
  let attempts = 0
  const client = new CosClient(config, { fetchImpl: async () => { attempts++; return new Response('', { status: 403 }) } })
  await assert.rejects(client.currentManifest(), /HTTP 403/)
  assert.equal(attempts, 1)
  const r = remote()
  assert.equal(await r.client.currentManifest(), null)
  r.objects.set(r.client.key('latest.json'), '{broken')
  await assert.rejects(r.client.currentManifest())
})

test('promotion verifies public files even when called directly', async (t) => {
  const r = remote(), snapshot = await fixture(t, r.client)
  await assert.rejects(r.client.promote(snapshot), /HTTP 404/)
  assert.equal(r.objects.size, 0)
})

test('dry preflight never accesses remote state; obsolete skip-upload cannot accidentally upload', async () => {
  assert.deepEqual(await main(['--phase=preflight', '--dry-run']), { status: 'dry-run', phase: 'preflight' })
  await assert.rejects(main(['--skip-upload']), /Unsupported argument/)
  await assert.rejects(main(['--manifest=test.json']), /Both/)
})
