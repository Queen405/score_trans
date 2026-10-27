/**
 * Audiveris 形状（shape）的人类可读描述。
 *
 * 候选列表里只放一个图标时，很多形状（尤其休止符、拍号、装饰音）会退化成同一个
 * 占位图形，用户无法区分。这里把 shape 拆成「族」和「变体」两层：
 * - 族：音符头 / 休止符 / 谱号…（走 i18n，中英文各一份）
 * - 变体：实心 / 十六分 / 4/4…（能本地化就走 i18n，纯符号的直接给文本）
 */

export type ShapeFamily =
  | 'head'
  | 'rest'
  | 'clef'
  | 'key'
  | 'time'
  | 'accidental'
  | 'slur'
  | 'tuplet'
  | 'dynamic'
  | 'fermata'
  | 'dot'
  | 'articulation'
  | 'ornament'
  | 'pedal'
  | 'wedge'
  | 'arpeggio'
  | 'pluck'
  | 'bow'
  | 'fingering'
  | 'breath'
  | 'structural'
  | 'other'

const FAMILY_RULES: ReadonlyArray<{ pattern: RegExp; family: ShapeFamily }> = [
  { pattern: /^(NOTEHEAD|WHOLE_NOTE|BREVE_NOTE|HALF_NOTE)/, family: 'head' },
  { pattern: /REST/, family: 'rest' },
  { pattern: /CLEF/, family: 'clef' },
  { pattern: /^KEY_/, family: 'key' },
  { pattern: /^(TIME_|COMMON_TIME|CUT_TIME)/, family: 'time' },
  { pattern: /(SLUR|TIE)/, family: 'slur' },
  { pattern: /TUPLET/, family: 'tuplet' },
  { pattern: /^DYNAMICS|^(SF|SFZ|F|P|MP|MF|PP|PPP|FFFF?)$/, family: 'dynamic' },
  { pattern: /FERMATA/, family: 'fermata' },
  { pattern: /(AUGMENTATION_DOT|^DOT$|_DOT$)/, family: 'dot' },
  { pattern: /(MARCATO|ACCENT|STACCATO|TENUTO)/, family: 'articulation' },
  { pattern: /(MORDENT|TURN|TRILL|^TR$)/, family: 'ornament' },
  { pattern: /PEDAL/, family: 'pedal' },
  { pattern: /(CRESCENDO|DIMINUENDO)/, family: 'wedge' },
  { pattern: /ARPEGGIO|ARPEGGIATO/, family: 'arpeggio' },
  { pattern: /(PLUCK|PLECTRUM)/, family: 'pluck' },
  { pattern: /(BOW|SCORDATURA)/, family: 'bow' },
  { pattern: /(FINGERING|^DIGIT_)/, family: 'fingering' },
  { pattern: /(BREATH|CAESURA|PAUSE)/, family: 'breath' },
  { pattern: /(SHARP|FLAT|NATURAL)/, family: 'accidental' },
  { pattern: /(STEM|BEAM|BARLINE|STAFF|LEDGER)/, family: 'structural' },
]

const TAG_FAMILIES: Record<string, ShapeFamily> = {
  head: 'head',
  'unrecognized-head': 'head',
  rest: 'rest',
  alter: 'accidental',
  clef: 'clef',
  key: 'key',
  'time-pair': 'time',
  'time-whole': 'time',
  'time-custom': 'time',
  slur: 'slur',
  tie: 'slur',
  tuplet: 'tuplet',
  dynamics: 'dynamic',
  dynamic: 'dynamic',
  fermata: 'fermata',
  'augmentation-dot': 'dot',
  articulation: 'articulation',
  ornament: 'ornament',
  pedal: 'pedal',
  wedge: 'wedge',
  arpeggiato: 'arpeggio',
  plucking: 'pluck',
  bow: 'bow',
  fingering: 'fingering',
  pause: 'breath',
  'breath-mark': 'breath',
  caesura: 'breath',
}

/** Returns whether a persisted candidate belongs to the selected marker family. */
export function candidateMatchesTag(
  shape: string | null | undefined,
  tag: string | null | undefined,
  fallbackShape = '',
): boolean {
  if (!shape) return false
  return shapeFamily(shape) === familyFromTag(tag, fallbackShape)
}

export function shapeFamily(shape: string | null | undefined): ShapeFamily {
  const value = (shape ?? '').toUpperCase()
  if (!value) return 'other'
  for (const rule of FAMILY_RULES) {
    if (rule.pattern.test(value)) return rule.family
  }
  return 'other'
}

/** 优先按后端给的标记类型判断族，拿不到再回退到 shape 推断。 */
export function familyFromTag(
  tag: string | null | undefined,
  fallbackShape = '',
): ShapeFamily {
  if (tag && TAG_FAMILIES[tag]) return TAG_FAMILIES[tag]
  return shapeFamily(fallbackShape)
}

const HEAD_VARIANTS: Record<string, string> = {
  NOTEHEAD_BLACK: 'headBlack',
  NOTEHEAD_BLACK_SMALL: 'headBlackSmall',
  NOTEHEAD_VOID: 'headVoid',
  NOTEHEAD_VOID_SMALL: 'headVoidSmall',
  NOTEHEAD_HALF: 'headVoid',
  HALF_NOTE: 'headVoid',
  NOTEHEAD_CROSS: 'headCross',
  NOTEHEAD_CROSS_VOID: 'headCrossVoid',
  NOTEHEAD_DIAMOND_FILLED: 'headDiamond',
  NOTEHEAD_DIAMOND_VOID: 'headDiamondVoid',
  NOTEHEAD_TRIANGLE_DOWN_FILLED: 'headTriangle',
  NOTEHEAD_TRIANGLE_DOWN_VOID: 'headTriangleVoid',
  NOTEHEAD_CIRCLE_X: 'headCircleX',
  NOTEHEAD_CIRCLE_X_VOID: 'headCircleXVoid',
  WHOLE_NOTE: 'whole',
  WHOLE_NOTE_SMALL: 'wholeSmall',
  WHOLE_NOTE_CROSS: 'wholeCross',
  WHOLE_NOTE_DIAMOND: 'wholeDiamond',
  WHOLE_NOTE_TRIANGLE_DOWN: 'wholeTriangle',
  WHOLE_NOTE_CIRCLE_X: 'wholeCircleX',
  BREVE: 'breve',
  BREVE_NOTE: 'breve',
  BREVE_SMALL: 'breveSmall',
  BREVE_CROSS: 'breveCross',
  BREVE_DIAMOND: 'breveDiamond',
  BREVE_TRIANGLE_DOWN: 'breveTriangle',
  BREVE_CIRCLE_X: 'breveCircleX',
}

const REST_VARIANTS: Record<string, string> = {
  WHOLE_REST: 'restWhole',
  HALF_REST: 'restHalf',
  QUARTER_REST: 'restQuarter',
  EIGHTH_REST: 'restEighth',
  SIXTEENTH_REST: 'restS16',
  THIRTY_SECOND_REST: 'restS32',
  SIXTY_FOURTH_REST: 'restS64',
  ONE_16TH_REST: 'restS16',
  ONE_32ND_REST: 'restS32',
  ONE_64TH_REST: 'restS64',
  ONE_128TH_REST: 'restS128',
  LONG_REST: 'restLong',
  BREVE_REST: 'restBreve',
}

const CLEF_VARIANTS: Record<string, string> = {
  G_CLEF: 'clefTreble',
  F_CLEF: 'clefBass',
  C_CLEF: 'clefAlto',
  PERCUSSION_CLEF: 'clefPercussion',
  TAB_CLEF: 'clefTab',
}

const DYNAMIC_VARIANTS: Record<string, string> = {
  DYNAMICS_P: 'dynamicP',
  DYNAMICS_PP: 'dynamicPP',
  DYNAMICS_PPP: 'dynamicPPP',
  DYNAMICS_MP: 'dynamicMP',
  DYNAMICS_F: 'dynamicF',
  DYNAMICS_FF: 'dynamicFF',
  DYNAMICS_FFF: 'dynamicFFF',
  DYNAMICS_MF: 'dynamicMF',
  DYNAMICS_FP: 'dynamicFP',
  DYNAMICS_FZ: 'dynamicFZ',
  DYNAMICS_SF: 'dynamicSF',
  DYNAMICS_SFZ: 'dynamicSFZ',
  SF: 'dynamicSF',
  SFZ: 'dynamicSFZ',
}

const ACCIDENTAL_VARIANTS: Record<string, string> = {
  SHARP: 'accidentalSharp',
  FLAT: 'accidentalFlat',
  NATURAL: 'accidentalNatural',
  DOUBLE_SHARP: 'accidentalDoubleSharp',
  DOUBLE_FLAT: 'accidentalDoubleFlat',
}

const CLEF_OCTAVE_SUFFIX = /[_-](8VA|8VB|15MA|15MB|OTTAVA)$/

const ACCIDENTAL_TEXT: Record<string, string> = {
  SHARP: '♯',
  FLAT: '♭',
  NATURAL: '♮',
  DOUBLE_SHARP: '𝄪',
  DOUBLE_FLAT: '𝄫',
}

const TIME_TEXT: Record<string, string> = {
  TIME_FOUR_FOUR: '4/4',
  TIME_TWO_TWO: '2/2',
  TIME_TWO_FOUR: '2/4',
  TIME_THREE_FOUR: '3/4',
  TIME_FIVE_FOUR: '5/4',
  TIME_SIX_FOUR: '6/4',
  TIME_THREE_EIGHT: '3/8',
  TIME_SIX_EIGHT: '6/8',
  TIME_NINE_EIGHT: '9/8',
  TIME_TWELVE_EIGHT: '12/8',
  COMMON_TIME: 'C',
  CUT_TIME: '¢',
}

const NUMBER_WORDS: Record<string, string> = {
  ONE: '1',
  TWO: '2',
  THREE: '3',
  FOUR: '4',
  FIVE: '5',
  SIX: '6',
  SEVEN: '7',
  EIGHT: '8',
  NINE: '9',
  TWELVE: '12',
}

/**
 * 返回可本地化的变体 key（`convert.marker.variant.<key>`），
 * 没有对应文案时返回 null，由 {@link shapeVariantText} 兜底。
 */
export function shapeVariantKey(shape: string | null | undefined): string | null {
  const value = (shape ?? '').toUpperCase()
  if (!value) return null
  if (HEAD_VARIANTS[value]) return HEAD_VARIANTS[value]
  if (REST_VARIANTS[value]) return REST_VARIANTS[value]
  if (CLEF_VARIANTS[value]) return CLEF_VARIANTS[value]
  if (DYNAMIC_VARIANTS[value]) return DYNAMIC_VARIANTS[value]
  if (ACCIDENTAL_VARIANTS[value]) return ACCIDENTAL_VARIANTS[value]
  const ordinal = /^ONE_(\d+)(?:ST|ND|RD|TH)_REST$/.exec(value)
  if (ordinal) return `restS${ordinal[1]}`
  if (CLEF_OCTAVE_SUFFIX.test(value)) {
    const base = CLEF_VARIANTS[value.replace(CLEF_OCTAVE_SUFFIX, '')]
    if (base) return base
  }
  return null
}

/** 谱号的八度标记单独成词，避免为每个组合再开一条文案。 */
export function shapeClefOctave(
  shape: string | null | undefined,
): 'octaveUp' | 'octaveDown' | null {
  const value = (shape ?? '').toUpperCase()
  const match = CLEF_OCTAVE_SUFFIX.exec(value)
  if (!match) return null
  return match[1].endsWith('B') ? 'octaveDown' : 'octaveUp'
}

/** 无需翻译、直接用符号或数字表达的变体。 */
export function shapeVariantText(shape: string | null | undefined): string {
  const value = (shape ?? '').toUpperCase()
  if (!value) return ''
  if (ACCIDENTAL_TEXT[value]) return ACCIDENTAL_TEXT[value]
  if (TIME_TEXT[value]) return TIME_TEXT[value]
  if (value.startsWith('KEY_SHARP_')) {
    const count = Number(value.slice('KEY_SHARP_'.length))
    return `${Number.isFinite(count) ? count : 1}♯`
  }
  if (value.startsWith('KEY_FLAT_')) {
    const count = Number(value.slice('KEY_FLAT_'.length))
    return `${Number.isFinite(count) ? count : 1}♭`
  }
  if (value === 'KEY_CANCEL') return '♮'
  if (value.startsWith('DYNAMICS_')) return value.slice('DYNAMICS_'.length).toLowerCase()
  if (value === 'SF' || value === 'SFZ') return value.toLowerCase()
  const tuplet = /^TUPLET_([A-Z]+)$/.exec(value)
  if (tuplet && NUMBER_WORDS[tuplet[1]]) return NUMBER_WORDS[tuplet[1]]
  if (/^DIGIT_[0-9]$/.test(value)) return value.slice(-1)
  // 没有对应文案时返回空串，由调用方回退到中文族名，绝不把英文 shape 名直接展示给用户
  return ''
}

/** 百分数展示，避免出现「100%」和「99%」之间的视觉抖动。 */
export function formatScorePercent(score: number | null | undefined): string {
  const value = Number(score)
  if (!Number.isFinite(value)) return '—'
  const clamped = Math.max(0, Math.min(1, value))
  return `${Math.round(clamped * 100)}%`
}

/** 低分候选弱化展示，但不把它当作产品阈值。 */
export function isLowConfidence(score: number | null | undefined): boolean {
  const value = Number(score)
  return Number.isFinite(value) && value < 0.5
}
