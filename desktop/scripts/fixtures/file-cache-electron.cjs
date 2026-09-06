const assert = require('node:assert/strict')
const fs = require('node:fs')
const http = require('node:http')
const path = require('node:path')
const { app, BrowserWindow } = require('electron')
const ts = require('typescript')

app.setPath('userData', process.env.SCORE_TRANS_TEST_USER_DATA)
app.disableHardwareAcceleration()

const requests = []
const backend = http.createServer((req, res) => {
  if (req.headers.origin) {
    res.setHeader('Access-Control-Allow-Origin', req.headers.origin)
    res.setHeader('Vary', 'Origin')
  }
  if (req.method === 'OPTIONS') {
    res.setHeader('Access-Control-Allow-Methods', 'GET')
    res.setHeader('Access-Control-Allow-Headers', 'Authorization')
    res.end()
    return
  }
  requests.push({ origin: req.headers.origin, authorization: req.headers.authorization })
  // Reproduce the legacy response already present in users' disk caches.
  res.setHeader('Cache-Control', 'max-age=3600')
  res.setHeader('Content-Type', 'image/png')
  res.end('score-image')
})
const frontend = http.createServer((_req, res) => {
  res.setHeader('Content-Type', 'text/html')
  res.end('<!doctype html><html><body></body></html>')
})

function listen(server) {
  return new Promise((resolve) => server.listen(0, '127.0.0.1', () => {
    resolve(`http://127.0.0.1:${server.address().port}`)
  }))
}

async function run() {
  const baseURL = await listen(backend)
  const origin = await listen(frontend)
  await app.whenReady()
  const window = new BrowserWindow({ show: false, webPreferences: { sandbox: true } })
  const sourcePath = path.resolve(__dirname, '../../src/renderer/src/api/client.ts')
  const compiled = ts.transpileModule(fs.readFileSync(sourcePath, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.ES2022, target: ts.ScriptTarget.ES2022 },
    fileName: sourcePath,
  }).outputText
  const moduleURL = `data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`
  await window.loadURL(origin)
  const result = await window.webContents.executeJavaScript(`(async () => {
    const baseURL = ${JSON.stringify(baseURL)};
    const url = baseURL + '/files/cached-image';
    await fetch(url, { mode: 'no-cors' });
    let legacyFailed = false;
    try { await fetch(url); } catch { legacyFailed = true; }
    window.api = { getBackendConnection: async () => ({ baseURL, token: 'test-token' }) };
    const client = await import(${JSON.stringify(moduleURL)});
    await client.initializeBackendConnection();
    const response = await client.fetchFileBlob('cached-image');
    return { legacyFailed, error: response.error?.message, body: response.data && await response.data.text() };
  })()`)
  assert.equal(result.legacyFailed, true, 'fixture must reproduce the cached CORS failure')
  assert.equal(result.error, undefined, `file fetch failed: ${result.error}`)
  assert.equal(result.body, 'score-image')
  assert.ok(requests.some((req) => req.origin === origin && req.authorization === 'Bearer test-token'))
  console.log('Cached CORS reproduction and authenticated recovery passed')
  window.destroy()
}

run().then(() => app.exit(0), (error) => {
  console.error(error)
  app.exit(1)
})
