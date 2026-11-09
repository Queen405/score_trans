const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const os = require('node:os')
const ts = require('typescript')
const { app, BrowserWindow } = require('electron')

app.disableHardwareAcceleration()
const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'score-trans-svg-test-'))
app.setPath('userData', profile)
app.setPath('sessionData', profile)

async function main() {
  const sourcePath = path.resolve(
    __dirname,
    '../src/renderer/src/utils/svgSanitizer.ts',
  )
  const source = fs.readFileSync(sourcePath, 'utf8').replace(/^export\s+/gm, '')
  const compiled = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.None,
      target: ts.ScriptTarget.ES2022,
    },
    fileName: sourcePath,
  }).outputText

  const window = new BrowserWindow({
    show: false,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  })
  await window.loadURL('data:text/html,<meta charset="utf-8"><title>svg-test</title>')

  const malicious = `
    <svg xmlns="http://www.w3.org/2000/svg" width="800" height="600"
         viewBox="0 0 800 600" onload="globalThis.pwned=1">
      <defs><style>
        @import url("https://attacker.invalid/x.css");
        .note { fill: url(javascript:alert(1)); font-size: 24px; }
      </style></defs>
      <script>globalThis.pwned=2</script>
      <foreignObject><body xmlns="http://www.w3.org/1999/xhtml" onload="alert(1)"/></foreignObject>
      <image href="https://attacker.invalid/pixel"/>
      <use href="#payload"/>
      <g class="playback-note source-anchor" data-source-ids="s1:i1"
         onclick="alert(1)" style="background:url(https://attacker.invalid)">
        <path class="note" d="M 0 0 L 10 10" href="javascript:alert(1)"/>
      </g>
    </svg>
  `

  const result = await window.webContents.executeJavaScript(`
    (() => {
      ${compiled}
      const root = sanitizeSvg(${JSON.stringify(malicious)})
      return {
        html: new XMLSerializer().serializeToString(root),
        css: root.querySelector('style')?.textContent || '',
        sourceIds: root.querySelector('g')?.getAttribute('data-source-ids') || '',
        path: root.querySelector('path')?.getAttribute('d') || '',
      }
    })()
  `)

  assert.doesNotMatch(
    result.html,
    /script|foreignObject|<image|<use|onload|onclick|style=|href=/i,
  )
  assert.doesNotMatch(result.css, /@import|url\s*\(|javascript/i)
  assert.match(result.css, /\.note\{font-size:24px\}/)
  assert.equal(result.sourceIds, 's1:i1')
  assert.equal(result.path, 'M 0 0 L 10 10')

  const publication = fs.readFileSync(
    path.join(__dirname, 'fixtures/publication-chinese-title.svg'), 'utf8',
  )
  const title = await window.webContents.executeJavaScript(`
    (() => {
      ${compiled}
      const source = new DOMParser().parseFromString(${JSON.stringify(publication)}, 'image/svg+xml').documentElement
      const cleaned = sanitizeSvg(${JSON.stringify(publication)})
      document.body.replaceChildren(source, cleaned)
      const original = source.querySelector('.score-title')
      const sanitized = cleaned.querySelector('.score-title')
      const inkBoxes = node => [...node.querySelectorAll('path')].map(path => {
        const box = path.getBBox()
        return [box.x, box.y, box.width, box.height]
      })
      return {
        title: sanitized.getAttribute('aria-label'),
        originalPaths: [...original.querySelectorAll('path')].map(path => path.getAttribute('d')),
        sanitizedPaths: [...sanitized.querySelectorAll('path')].map(path => path.getAttribute('d')),
        originalBoxes: inkBoxes(original),
        sanitizedBoxes: inkBoxes(sanitized),
      }
    })()
  `)
  assert.equal(title.title, '海阔天空')
  assert.ok(title.originalPaths.some(data => data.length > 4096))
  assert.deepEqual(title.sanitizedPaths, title.originalPaths)
  assert.deepEqual(title.sanitizedBoxes, title.originalBoxes)
  assert.ok(title.sanitizedBoxes.every(box => box[2] > 0 && box[3] > 0))
  window.destroy()
}

app.whenReady()
  .then(main)
  .then(() => {
    console.log('svg-sanitizer-electron: ok')
    app.quit()
  })
  .catch((error) => {
    console.error(error)
    app.exit(1)
  })
