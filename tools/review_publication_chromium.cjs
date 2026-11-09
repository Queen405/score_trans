/** Capture complete SVG pages using Electron's Chromium, without tiled images.
 * Run: desktop/node_modules/electron/dist/electron.exe tools/review_publication_chromium.cjs OUTPUT_DIR
 */
const { app, BrowserWindow } = require('electron')
const fs = require('node:fs/promises')
const path = require('node:path')
const os = require('node:os')
const fsSync = require('node:fs')
const directory = path.resolve(process.argv[2])
const progress = (message) => fsSync.appendFileSync(path.join(directory, 'chromium-progress.log'), `${message}\n`)
progress('Application entry loaded')

const profile = fsSync.mkdtempSync(path.join(os.tmpdir(), 'score-trans-engraving-'))
app.setPath('userData', profile)
app.setPath('sessionData', profile)
app.disableHardwareAcceleration()
app.commandLine.appendSwitch('disable-features', 'CalculateNativeWinOcclusion')

app.whenReady().then(async () => {
  progress('Application ready')
  const pages = (await fs.readdir(directory)).filter((name) => /^page-\d+\.svg$/.test(name)).sort()
  const window = new BrowserWindow({
    show: false,
    width: 1280,
    height: 1800,
    useContentSize: true,
    webPreferences: { sandbox: false, contextIsolation: true, nodeIntegration: false },
  })
  const timeout = setTimeout(() => {
    progress('Screenshot review timed out')
    app.exit(1)
  }, 60000)
  const review = { engine: 'Electron Chromium', chromium: process.versions.chrome, pages: [] }
  try {
    for (const name of pages) {
      progress(`Loading ${name}`)
      await window.loadFile(path.join(directory, name))
      progress(`Loaded ${name}`)
      progress(`Reading metrics for ${name}`)
      const metrics = await window.webContents.executeJavaScript(`(() => {
        const svg = document.documentElement
        const box = svg.getBoundingClientRect()
        return {
          width: box.width, height: box.height, left: box.left, top: box.top,
          viewportWidth: innerWidth, viewportHeight: innerHeight,
          viewBox: svg.getAttribute('viewBox'),
          engineVersion: svg.getAttribute('data-engine-version'),
          notes: svg.querySelectorAll('.note').length,
          rhythmLines: svg.querySelectorAll('.beam-line').length,
          compressedChordNotes: svg.querySelectorAll('.note[data-scale-y="0.68"]').length,
          braces: svg.querySelectorAll('.group-brace').length,
          systems: svg.querySelectorAll('.system-connector').length,
        }
      })()`)
      const [viewportWidth, viewportHeight] = window.getContentSize()
      const zoom = Math.min(1, viewportWidth / metrics.width, viewportHeight / metrics.height)
      window.webContents.setZoomFactor(zoom)
      progress(`Capturing ${name} at ${zoom}`)
      const screenshot = await window.webContents.capturePage({
        x: Math.round(metrics.left * zoom), y: Math.round(metrics.top * zoom),
        width: Math.ceil(metrics.width * zoom), height: Math.ceil(metrics.height * zoom),
      }, { stayHidden: true, stayAwake: true })
      const output = name.replace('.svg', '-chromium.png')
      await fs.writeFile(path.join(directory, output), screenshot.toPNG())
      review.pages.push({ page: name, screenshot: output, zoom, screenshotSize: screenshot.getSize(), ...metrics })
      process.stdout.write(`${name}: ${metrics.width} x ${metrics.height}, ${metrics.systems} systems\n`)
    }
    await fs.writeFile(path.join(directory, 'chromium-review-all.json'), JSON.stringify(review, null, 2))
    const figures = review.pages.map((page) => `<figure><img src="${page.screenshot}" alt="${page.page}"><figcaption>${page.page} · ${page.systems} 个系统 · ${page.engineVersion}</figcaption></figure>`).join('')
    await fs.writeFile(path.join(directory, 'chromium.html'), `<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>Chromium 实际渲染检查</title><style>body{background:#e9edf0;color:#17212b;font:16px system-ui;margin:30px}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(420px,1fr));gap:24px}figure{margin:0}img{width:100%;background:white}figcaption{padding:12px 0}a{color:#1459a0}</style><h1>Chromium 实际渲染检查</h1><p>每页一次完整截图，没有分段拼接。为适应本机窗口尺寸使用页面缩放；打印细节请同时查看原始 SVG 与高分辨率 PNG。</p><p><a href="index.html">SVG / 导出 PNG 画廊</a></p><main>${figures}</main></html>`)
    const indexPath = path.join(directory, 'index.html')
    if (fsSync.existsSync(indexPath)) {
      const index = await fs.readFile(indexPath, 'utf8')
      if (!index.includes('chromium.html')) await fs.writeFile(indexPath, index.replace('<main>', '<p><a href="chromium.html">查看 Chromium 完整截图</a></p><main>'))
    }
  } finally {
    clearTimeout(timeout)
    window.destroy()
  }
  app.exit(0)
}).catch((error) => {
  progress(error.stack || String(error))
  process.stderr.write(`${error.stack || error}\n`)
  app.exit(1)
})
