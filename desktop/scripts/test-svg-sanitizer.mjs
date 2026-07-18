import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'

const here = path.dirname(fileURLToPath(import.meta.url))
const projectRoot = path.resolve(here, '..')
const sanitizerPath = path.join(
  projectRoot,
  'src/renderer/src/utils/svgSanitizer.ts',
)
const sanitizerSource = fs.readFileSync(sanitizerPath, 'utf8')
const compiled = ts.transpileModule(sanitizerSource, {
  compilerOptions: {
    module: ts.ModuleKind.ES2022,
    target: ts.ScriptTarget.ES2022,
  },
  fileName: sanitizerPath,
}).outputText
const sanitizer = await import(
  `data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`
)

test('SVG sanitizer uses a narrow element and attribute allowlist', () => {
  for (const element of ['svg', 'defs', 'style', 'g', 'rect', 'text', 'line', 'path', 'circle']) {
    assert.equal(sanitizer.isAllowedSvgElement(element), true)
  }
  for (const element of ['script', 'foreignObject', 'image', 'use', 'a', 'animate', 'iframe']) {
    assert.equal(sanitizer.isAllowedSvgElement(element), false)
  }

  assert.equal(sanitizer.isAllowedSvgAttribute('path', 'd'), true)
  assert.equal(sanitizer.isAllowedSvgAttribute('g', 'data-source-ids'), true)
  assert.equal(sanitizer.isAllowedSvgAttribute('g', 'data-source-role'), true)
  assert.equal(sanitizer.isAllowedSvgAttribute('g', 'data-source-role-articulation'), true)
  assert.equal(sanitizer.isAllowedSvgAttribute('g', 'transform'), true)
  assert.equal(sanitizer.isAllowedSvgAttribute('text', 'opacity'), true)
  assert.equal(sanitizer.isAllowedSvgAttribute('text', 'aria-hidden'), true)
  assert.equal(
    sanitizer.isSafeSvgAttributeValue(
      'g',
      'transform',
      'translate(102 247) scale(30 -30) translate(-0.279 0)',
    ),
    true,
  )
  assert.equal(
    sanitizer.isSafeSvgAttributeValue('text', 'opacity', '0'),
    true,
  )
  for (const attribute of ['href', 'xlink:href', 'src', 'style', 'onload', 'onclick']) {
    assert.equal(sanitizer.isAllowedSvgAttribute('path', attribute), false)
  }
})

test('SVG CSS sanitizer drops imports, URL functions and unknown properties', () => {
  const css = `
    @import url("https://attacker.invalid/steal.css");
    .note { fill: url(javascript:alert(1)); font-size: 24px; behavior: url(#x); }
    .bar { stroke: #171717; stroke-width: 1.6; }
    body, .note { fill: red; }
  `

  const safe = sanitizer.sanitizeSvgCss(css)

  assert.doesNotMatch(safe, /@import|url\s*\(|javascript|behavior|body/i)
  assert.match(safe, /\.note\{font-size:24px\}/)
  assert.match(safe, /\.bar\{stroke:#171717;stroke-width:1.6\}/)
})

test('publication SVG root styles survive sanitization placement checks', () => {
  const backendCss = fs.readFileSync(
    path.resolve(
      projectRoot,
      '../backend/score_trans/services/render/engraving/svg_backend.py',
    ),
    'utf8',
  )

  assert.match(backendCss, /\.page-background\{fill:#fff\}/)
  assert.equal(
    sanitizer.sanitizeSvgCss('.page-background{fill:#fff}'),
    '.page-background{fill:#fff}',
  )
  assert.equal(sanitizer.isAllowedSvgStyleParent('svg'), true)
  assert.equal(sanitizer.isAllowedSvgStyleParent('defs'), true)
  assert.equal(sanitizer.isAllowedSvgStyleParent('g'), false)
})

test('SVG preview mounts a sanitized DOM node without v-html', () => {
  const preview = fs.readFileSync(
    path.join(projectRoot, 'src/renderer/src/components/PublicationPreview.vue'),
    'utf8',
  )

  assert.doesNotMatch(preview, /\bv-html\s*=/)
  assert.match(preview, /sanitizeSvg/)
  assert.match(preview, /replaceChildren/)
  assert.match(preview, /async function highlightSource/)
  assert.match(preview, /\[data-source-role\]/)
  assert.match(preview, /getScreenCTM/)
  assert.match(preview, /svg\.appendChild\(rect\)/)
  assert.doesNotMatch(preview, /target\.appendChild\(rect\)/)
})
