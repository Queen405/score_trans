#!/usr/bin/env node
/** Immutable COS delivery. Default uploads artifacts only; CI explicitly promotes. */
import { createHash, createHmac } from 'node:crypto'
import { createReadStream, existsSync, readFileSync, statSync } from 'node:fs'
import { open } from 'node:fs/promises'
import { basename, dirname, join, resolve } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { setTimeout as delay } from 'node:timers/promises'

const DESKTOP = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const ROOT = resolve(DESKTOP, '..')
const PROCESS_ENV = { ...process.env }

export function configFromEnv(env) {
  const config = {
    bucket: env.COS_BUCKET || 'score-trans-1320022301',
    region: env.COS_REGION || 'ap-beijing',
    prefix: env.COS_PREFIX || 'download',
    secretId: env.TENCENTCLOUD_SECRET_ID || '',
    secretKey: env.TENCENTCLOUD_SECRET_KEY || '',
  }
  if (!/^[a-z0-9-]+$/.test(config.bucket) || !/^[a-z0-9-]+$/.test(config.region)
      || !/^[a-zA-Z0-9_-]+(?:\/[a-zA-Z0-9_-]+)*$/.test(config.prefix)) {
    throw new Error('Invalid COS bucket, region or prefix')
  }
  return config
}

export function compareVersions(a, b) {
  const parse = (v) => {
    if (typeof v !== 'string' || !/^\d+\.\d+\.\d+$/.test(v)) throw new Error('Invalid release version')
    return v.split('.').map(BigInt)
  }
  const left = parse(a), right = parse(b)
  for (let i = 0; i < 3; i++) {
    if (left[i] !== right[i]) return left[i] > right[i] ? 1 : -1
  }
  return 0
}

const encodeKey = (key) => key.split('/').map(encodeURIComponent).join('/')
const sha1 = (text) => createHash('sha1').update(text).digest('hex')
const hmac = (key, text) => createHmac('sha1', key).update(text).digest('hex')

export function cosAuth(config, method, pathname, params, headers, now = Math.floor(Date.now() / 1000)) {
  const canonical = (values) => Object.entries(values)
    .map(([k, v]) => [k.toLowerCase(), String(v)])
    .sort(([a], [b]) => a < b ? -1 : a > b ? 1 : 0)
  const entries = (values) => canonical(values).map(([k, v]) => encodeURIComponent(k) + '=' + encodeURIComponent(v)).join('&')
  const keys = (values) => canonical(values).map(([k]) => k).join(';')
  const time = (now - 60) + ';' + (now + 7200)
  const http = [method.toLowerCase(), pathname, entries(params), entries(headers), ''].join('\n')
  const signature = hmac(hmac(config.secretKey, time), ['sha1', time, sha1(http), ''].join('\n'))
  return [
    'q-sign-algorithm=sha1', 'q-ak=' + config.secretId,
    'q-sign-time=' + time, 'q-key-time=' + time,
    'q-header-list=' + keys(headers), 'q-url-param-list=' + keys(params),
    'q-signature=' + signature,
  ].join('&')
}

export class CosClient {
  constructor(config, { fetchImpl = fetch, sleep = delay } = {}) {
    this.config = config
    this.fetch = fetchImpl
    this.sleep = sleep
    this.host = config.bucket + '.cos.' + config.region + '.myqcloud.com'
  }

  url(key) { return 'https://' + this.host + '/' + encodeKey(key) }
  key(name) { return this.config.prefix + '/' + name }

  async request(method, key, { params = {}, body, headers = {}, publicRead = false, missingOk = false } = {}) {
    const url = this.url(key) + (Object.keys(params).length ? '?' + new URLSearchParams(params) : '')
    const authorization = cosAuth(this.config, method, '/' + key, params, { host: this.host, ...headers })
    for (let attempt = 0; attempt < 3; attempt++) {
      let res
      try {
        res = await this.fetch(url, {
          method, body, headers: { ...headers, ...(publicRead ? {} : { Authorization: authorization }) },
          signal: AbortSignal.timeout(120000),
        })
      } catch (error) {
        if (attempt === 2) throw new Error('COS network request failed', { cause: error })
        await this.sleep(1000 * (attempt + 1))
        continue
      }
      if (res.ok || (res.status === 404 && missingOk)) return res
      await res.body?.cancel()
      if ((res.status === 429 || res.status >= 500) && attempt < 2) {
        await this.sleep(1000 * (attempt + 1))
        continue
      }
      throw new Error('COS ' + method + ' failed: HTTP ' + res.status)
    }
  }

  async currentManifest() {
    const res = await this.request('GET', this.key('latest.json'), {
      missingOk: true, headers: { 'Cache-Control': 'no-cache' },
    })
    if (res.status === 404) return null
    const text = await res.text()
    const manifest = JSON.parse(text)
    compareVersions(manifest.version, manifest.version)
    if (typeof manifest.url !== 'string') throw new Error('Invalid remote manifest')
    return { text, manifest }
  }

  async verifyPublic(key, expectedHash, expectedSize, missingOk = false) {
    // Hash the publicly downloadable bytes, not a multipart ETag or user metadata.
    const res = await this.request('GET', key, { publicRead: true, missingOk })
    if (res.status === 404) return false
    const hash = createHash('sha256')
    let size = 0
    for await (const chunk of res.body) { hash.update(chunk); size += chunk.length }
    if (size !== expectedSize || hash.digest('hex') !== expectedHash) {
      throw new Error('Existing COS object differs from immutable snapshot: ' + key)
    }
    return true
  }

  async upload(file, key) {
    const size = statSync(file).size
    const init = await this.request('POST', key, { params: { uploads: '' } })
    const uploadId = (await init.text()).match(/<UploadId>([^<]+)<\/UploadId>/)?.[1]
    if (!uploadId) throw new Error('COS did not return a multipart upload ID')
    let handle
    try {
      handle = await open(file, 'r')
      const parts = []
      for (let offset = 0, number = 1; offset < size; number++) {
        const buffer = Buffer.alloc(Math.min(8 * 1024 * 1024, size - offset))
        const { bytesRead } = await handle.read(buffer, 0, buffer.length, offset)
        if (!bytesRead) throw new Error('Installer changed while uploading')
        const part = await this.request('PUT', key, {
          params: { partNumber: String(number), uploadId },
          body: buffer.subarray(0, bytesRead),
          headers: { 'Content-MD5': createHash('md5').update(buffer.subarray(0, bytesRead)).digest('base64') },
        })
        const etag = part.headers.get('etag')
        await part.body?.cancel()
        if (!etag || !/^"?[a-fA-F0-9-]+"?$/.test(etag)) throw new Error('Invalid multipart ETag')
        parts.push('<Part><PartNumber>' + number + '</PartNumber><ETag>' + etag + '</ETag></Part>')
        offset += bytesRead
      }
      const completed = await this.request('POST', key, {
        params: { uploadId },
        body: '<CompleteMultipartUpload>' + parts.join('') + '</CompleteMultipartUpload>',
        headers: { 'Content-Type': 'application/xml', 'x-cos-forbid-overwrite': 'true' },
      })
      const text = await completed.text()
      if (!text.includes('<CompleteMultipartUploadResult')) throw new Error('COS multipart completion failed')
    } catch (error) {
      try {
        const aborted = await this.request('DELETE', key, { params: { uploadId }, missingOk: true })
        await aborted.body?.cancel()
      } catch { /* Original failure remains authoritative; no object deletion. */ }
      throw error
    } finally {
      await handle?.close()
    }
  }

  async artifacts(snapshot) {
    for (const file of snapshot.files) {
      const key = this.key(basename(file.path))
      // An authenticated HEAD distinguishes absence from a private/misconfigured public object.
      const head = await this.request('HEAD', key, { missingOk: true })
      if (head.status === 404) await this.upload(file.path, key)
      await this.verifyPublic(key, file.hash, file.size)
    }
    return { status: 'verified' }
  }

  async promote(snapshot) {
    const current = await this.currentManifest()
    const order = current ? compareVersions(snapshot.manifest.version, current.manifest.version) : 1
    if (order < 0) return { status: 'older' }
    if (order === 0 && current.text !== snapshot.text) throw new Error('Same version has different manifest bytes')
    // Recheck public installers even on a resumed promotion.
    for (const file of snapshot.files) {
      await this.verifyPublic(this.key(basename(file.path)), file.hash, file.size)
    }
    if (order > 0) {
      const put = await this.request('PUT', this.key('latest.json'), {
        body: snapshot.text,
        headers: { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-cache' },
      })
      await put.body?.cancel()
    }
    const readback = await this.request('GET', this.key('latest.json'), {
      publicRead: true, headers: { 'Cache-Control': 'no-cache' },
    })
    if (await readback.text() !== snapshot.text) throw new Error('Manifest readback differs')
    return { status: order === 0 ? 'unchanged' : 'promoted' }
  }
}

export async function fileHash(path) {
  const hash = createHash('sha256')
  for await (const chunk of createReadStream(path)) hash.update(chunk)
  return hash.digest('hex')
}

export async function loadSnapshot(manifestPath, checksumPath, client) {
  const text = readFileSync(manifestPath, 'utf8')
  const manifest = JSON.parse(text)
  compareVersions(manifest.version, manifest.version)
  const names = ['Score Trans Setup ' + manifest.version + '.exe', 'Score Trans-' + manifest.version + '-arm64.dmg']
  if (manifest.url !== client.url(client.key(names[0])) || manifest.urlMac !== client.url(client.key(names[1]))) {
    throw new Error('Manifest destination differs from COS configuration')
  }
  const hashes = new Map()
  const allowed = new Set([...names, 'latest.json', 'release-metadata.json'])
  for (const line of readFileSync(checksumPath, 'utf8').trimEnd().split(/\r?\n/)) {
    const match = line.match(/^([0-9a-f]{64})  (.+)$/)
    if (!match || !allowed.has(match[2]) || hashes.has(match[2])) throw new Error('Invalid checksum entry')
    hashes.set(match[2], match[1])
  }
  const files = []
  for (const name of [...names, 'latest.json', ...(hashes.has('release-metadata.json') ? ['release-metadata.json'] : [])]) {
    const path = join(dirname(manifestPath), name)
    const hash = await fileHash(path)
    if (hash !== hashes.get(name)) throw new Error('Local snapshot checksum mismatch: ' + name)
    if (names.includes(name)) {
      const size = statSync(path).size
      if (!size) throw new Error('Empty installer')
      files.push({ path, hash, size })
    }
  }
  return { text, manifest, files }
}

function localEnv() {
  const file = join(ROOT, '.env')
  if (!existsSync(file)) return {}
  const env = {}
  for (const raw of readFileSync(file, 'utf8').split(/\r?\n/)) {
    const line = raw.trim()
    if (!line || line.startsWith('#')) continue
    const eq = line.indexOf('=')
    if (eq < 1) continue
    let value = line.slice(eq + 1).trim()
    if ((value.startsWith('"') && value.endsWith('"')) || (value.startsWith("'") && value.endsWith("'"))) value = value.slice(1, -1)
    env[line.slice(0, eq).trim()] = value
  }
  return env
}

export async function main(argv = process.argv.slice(2)) {
  const flags = new Set(['--dry-run', '--no-sync', '--no-cdn'])
  const names = new Set(['phase', 'manifest', 'checksums', 'file', 'files'])
  const seen = new Set()
  for (const value of argv) {
    const name = value.match(/^--([^=]+)=/)?.[1]
    if (!flags.has(value) && (!name || !names.has(name))) throw new Error('Unsupported argument: ' + value.split('=')[0])
    if (name && seen.has(name)) throw new Error('Duplicate argument: ' + name)
    if (name) seen.add(name)
  }
  const arg = (name) => argv.find((value) => value.startsWith('--' + name + '='))?.slice(name.length + 3)
  if (Boolean(arg('manifest')) !== Boolean(arg('checksums'))) throw new Error('Both --manifest and --checksums are required')
  const phase = arg('phase') || 'artifacts'
  if (!['preflight', 'artifacts', 'promote'].includes(phase)) throw new Error('Invalid COS phase')
  const env = PROCESS_ENV.GITHUB_ACTIONS === 'true' ? PROCESS_ENV : { ...localEnv(), ...PROCESS_ENV }
  const config = configFromEnv(env)
  const client = new CosClient(config)
  const dryRun = argv.includes('--dry-run')
  if (!dryRun && (!config.secretId || !config.secretKey)) throw new Error('Tencent COS credentials are required')
  if (phase === 'preflight') {
    if (dryRun) return { status: 'dry-run', phase }
    await client.currentManifest()
    return { status: 'ready' }
  }
  if (phase === 'promote' && (env.GITHUB_ACTIONS !== 'true' || env.SCORE_TRANS_RELEASE_JOB !== '1')) {
    throw new Error('Promote only through the serialized release workflow')
  }
  let snapshot
  if (arg('manifest') && arg('checksums')) {
    snapshot = await loadSnapshot(resolve(arg('manifest')), resolve(arg('checksums')), client)
  } else {
    if (phase === 'promote') throw new Error('Promotion requires an immutable snapshot')
    const version = JSON.parse(readFileSync(join(DESKTOP, 'package.json'), 'utf8')).version
    compareVersions(version, version)
    const names = ['Score Trans Setup ' + version + '.exe', 'Score Trans-' + version + '-arm64.dmg']
    const paths = arg('files') ? arg('files').split(',').map((p) => resolve(p.trim()))
      : arg('file') ? [resolve(arg('file'))]
        : names.map((name) => join(DESKTOP, 'dist-electron', name)).filter(existsSync)
    if (!paths.length || paths.some((p) => !names.includes(basename(p)))) throw new Error('Expected versioned installer files')
    snapshot = { files: await Promise.all(paths.map(async (path) => ({
      path, hash: await fileHash(path), size: statSync(path).size,
    }))) }
    if (snapshot.files.some((file) => file.size === 0)) throw new Error('Empty installer')
  }
  if (dryRun) return { status: 'dry-run', phase, files: snapshot.files.map((f) => basename(f.path)) }
  return phase === 'artifacts' ? client.artifacts(snapshot) : client.promote(snapshot)
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  main().then((result) => console.log(JSON.stringify(result))).catch((error) => {
    console.error(error.message)
    process.exitCode = 1
  })
}
