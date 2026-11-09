const SVG_NAMESPACE = 'http://www.w3.org/2000/svg'

const ALLOWED_ELEMENTS = new Set([
  'svg',
  'defs',
  'style',
  'g',
  'rect',
  'text',
  'tspan',
  'line',
  'path',
  'circle',
  'ellipse',
  'polyline',
  'polygon',
])

const COMMON_ATTRIBUTES = new Set(['class', 'aria-label', 'aria-hidden'])
const DATA_ATTRIBUTES = new Set([
  'data-note-index',
  'data-note-group',
  'data-playback-version',
  'data-playback-ppq',
  'data-playback-start-tick',
  'data-playback-end-tick',
  'data-playback-tick',
  'data-part-index',
  'data-note-token',
  'data-source-id',
  'data-source-ids',
  'data-bbox',
  'data-number',
  'data-width',
  'data-mark',
  'data-direction',
  'data-font-size',
  'data-render-engine',
  'data-engine-version',
  'data-page-index',
  'data-note-index-start',
  'data-note-index-end',
  'data-ending-number',
  'data-ending-resumed',
])
const SAFE_SOURCE_ROLE_ATTRIBUTE = /^data-source-role(?:-[a-z0-9_-]+)?$/
const ELEMENT_ATTRIBUTES: Record<string, ReadonlySet<string>> = {
  svg: new Set(['xmlns', 'width', 'height', 'viewbox', 'preserveaspectratio']),
  defs: new Set(),
  style: new Set(),
  g: new Set(['transform']),
  rect: new Set(['x', 'y', 'width', 'height', 'rx', 'ry', 'fill', 'stroke', 'stroke-width']),
  text: new Set([
    'x',
    'y',
    'dx',
    'dy',
    'fill',
    'opacity',
    'text-anchor',
    'font-size',
  ]),
  tspan: new Set(['x', 'y', 'dx', 'dy', 'fill', 'text-anchor', 'font-size']),
  line: new Set(['x1', 'y1', 'x2', 'y2', 'stroke', 'stroke-width']),
  path: new Set(['d', 'fill', 'stroke', 'stroke-width', 'transform']),
  circle: new Set(['cx', 'cy', 'r', 'fill', 'stroke', 'stroke-width']),
  ellipse: new Set(['cx', 'cy', 'rx', 'ry', 'fill', 'stroke', 'stroke-width']),
  polyline: new Set(['points', 'fill', 'stroke', 'stroke-width']),
  polygon: new Set(['points', 'fill', 'stroke', 'stroke-width']),
}

const ALLOWED_CSS_PROPERTIES = new Set([
  'font-family',
  'fill',
  'letter-spacing',
  'font-size',
  'font-weight',
  'font-style',
  'stroke',
  'stroke-width',
  'stroke-linecap',
  'stroke-linejoin',
  'stroke-dasharray',
])

const SAFE_CLASS = /^[A-Za-z0-9_-]+(?:\s+[A-Za-z0-9_-]+)*$/
const SAFE_LENGTH = /^-?(?:\d+(?:\.\d+)?|\.\d+)(?:px|%)?$/
const SAFE_NUMBER_LIST = /^[-+0-9.eE,\s]+$/
const SAFE_PATH = /^[MmZzLlHhVvCcSsQqTtAa0-9eE+.,\s-]+$/
const SAFE_TRANSFORM = /^(?:(?:rotate|translate|scale|matrix)\([-+0-9.eE,\s]+\)\s*)+$/
const SAFE_SELECTOR = /^(?:text|\.[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)*)(?:\s+\.[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)*)*$/
const SAFE_FONT_FAMILY = /^[\p{L}\p{N}\s,'"_-]+$/u
// Outlined Chinese glyphs from the publication font exceed 4 KiB per character.
// Keep the larger allowance specific to path data; its command allowlist still applies.
const MAX_PATH_DATA_LENGTH = 256 * 1024

export function sanitizeSvg(text: string): SVGSVGElement {
  const doc = new DOMParser().parseFromString(text, 'image/svg+xml')
  const root = doc.documentElement
  if (
    doc.getElementsByTagName('parsererror').length
    || root.namespaceURI !== SVG_NAMESPACE
    || root.localName.toLowerCase() !== 'svg'
  ) {
    throw new Error('Invalid SVG')
  }

  const elements = [root, ...Array.from(root.querySelectorAll('*'))]
  for (const element of elements) {
    if (!element.isConnected) continue
    const name = element.localName.toLowerCase()
    if (
      element.namespaceURI !== SVG_NAMESPACE
      || !isAllowedSvgElement(name)
      || (
        name === 'style'
        && !isAllowedSvgStyleParent(element.parentElement?.localName)
      )
    ) {
      element.remove()
      continue
    }

    for (const attribute of Array.from(element.attributes)) {
      const attributeName = attribute.name.toLowerCase()
      if (
        (attribute.namespaceURI && attributeName !== 'xmlns')
        || !isAllowedSvgAttribute(name, attributeName)
        || !isSafeSvgAttributeValue(name, attributeName, attribute.value)
      ) {
        element.removeAttribute(attribute.name)
      }
    }

    if (name === 'style') {
      const safeCss = sanitizeSvgCss(element.textContent ?? '')
      if (!safeCss) {
        element.remove()
      } else {
        element.textContent = safeCss
      }
    }
  }

  return root as unknown as SVGSVGElement
}

export function isAllowedSvgElement(name: string): boolean {
  return ALLOWED_ELEMENTS.has(name.toLowerCase())
}

export function isAllowedSvgStyleParent(name: string | undefined): boolean {
  const parent = name?.toLowerCase()
  return parent === 'svg' || parent === 'defs'
}

export function isAllowedSvgAttribute(
  elementName: string,
  attributeName: string,
): boolean {
  const element = elementName.toLowerCase()
  const attribute = attributeName.toLowerCase()
  return (
    COMMON_ATTRIBUTES.has(attribute)
    || DATA_ATTRIBUTES.has(attribute)
    || SAFE_SOURCE_ROLE_ATTRIBUTE.test(attribute)
    || ELEMENT_ATTRIBUTES[element]?.has(attribute)
    || false
  )
}

export function sanitizeSvgCss(css: string): string {
  const withoutComments = css.replace(/\/\*[\s\S]*?\*\//g, '')
  const withoutAtRules = withoutComments.replace(
    /@[^{;]+(?:;|\{[^{}]*\})/g,
    '',
  )
  const safeRules: string[] = []
  const rulePattern = /([^{}]+)\{([^{}]*)\}/g

  for (const match of withoutAtRules.matchAll(rulePattern)) {
    const selectors = match[1].split(',').map((selector) => selector.trim())
    if (
      !selectors.length
      || selectors.some((selector) => !SAFE_SELECTOR.test(selector))
    ) {
      continue
    }

    const declarations: string[] = []
    for (const declaration of match[2].split(';')) {
      const colon = declaration.indexOf(':')
      if (colon < 1) continue
      const property = declaration.slice(0, colon).trim().toLowerCase()
      const value = declaration.slice(colon + 1).trim()
      if (
        ALLOWED_CSS_PROPERTIES.has(property)
        && isSafeCssValue(property, value)
      ) {
        declarations.push(`${property}:${value}`)
      }
    }
    if (declarations.length) {
      safeRules.push(`${selectors.join(',')}{${declarations.join(';')}}`)
    }
  }

  return safeRules.join('')
}

export function isSafeSvgAttributeValue(
  elementName: string,
  attributeName: string,
  value: string,
): boolean {
  if (elementName === 'path' && attributeName === 'd') {
    return value.length <= MAX_PATH_DATA_LENGTH && SAFE_PATH.test(value)
  }
  if (value.length > 4096) return false
  if (attributeName === 'xmlns') return value === SVG_NAMESPACE
  if (attributeName === 'class') return SAFE_CLASS.test(value)
  if (attributeName === 'aria-hidden') {
    return value === 'true' || value === 'false'
  }
  if (
    attributeName === 'aria-label'
    || DATA_ATTRIBUTES.has(attributeName)
    || SAFE_SOURCE_ROLE_ATTRIBUTE.test(attributeName)
  ) {
    return Array.from(value).every((character) => {
      const code = character.charCodeAt(0)
      return code > 0x1f && code !== 0x7f
    })
  }
  if (attributeName === 'points' || attributeName === 'viewbox') {
    return SAFE_NUMBER_LIST.test(value)
  }
  if (attributeName === 'transform') return SAFE_TRANSFORM.test(value)
  if (attributeName === 'opacity') {
    const opacity = Number(value)
    return Number.isFinite(opacity) && opacity >= 0 && opacity <= 1
  }
  if (attributeName === 'fill' || attributeName === 'stroke') {
    return isSafePaint(value)
  }
  if (attributeName === 'text-anchor') {
    return value === 'start' || value === 'middle' || value === 'end'
  }
  if (attributeName === 'preserveaspectratio') {
    return /^[A-Za-z0-9\s]+$/.test(value)
  }
  if (elementName === 'svg' && (attributeName === 'width' || attributeName === 'height')) {
    return SAFE_LENGTH.test(value)
  }
  return SAFE_LENGTH.test(value)
}

function isSafeCssValue(property: string, value: string): boolean {
  if (
    !value
    || value.length > 256
    || /[\\{}@;]/.test(value)
    || /(?:url|expression|javascript|data)\s*[:(]/i.test(value)
  ) {
    return false
  }
  if (property === 'font-family') return SAFE_FONT_FAMILY.test(value)
  if (property === 'fill' || property === 'stroke') return isSafePaint(value)
  if (property === 'font-style') {
    return value === 'normal' || value === 'italic'
  }
  if (property === 'font-weight') {
    return /^(?:normal|bold|[1-9]00|[1-9]\d{1,2})$/.test(value)
  }
  if (property === 'stroke-linecap') {
    return /^(?:butt|round|square)$/.test(value)
  }
  if (property === 'stroke-linejoin') {
    return /^(?:miter|round|bevel)$/.test(value)
  }
  if (property === 'stroke-dasharray') return SAFE_NUMBER_LIST.test(value)
  return SAFE_LENGTH.test(value)
}

function isSafePaint(value: string): boolean {
  return (
    value === 'none'
    || value === 'currentColor'
    || /^#[0-9A-Fa-f]{3,8}$/.test(value)
    || /^[A-Za-z]+$/.test(value)
  )
}
