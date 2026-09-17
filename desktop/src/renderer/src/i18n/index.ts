import { computed, ref } from 'vue'
import { dateEnUS, dateZhCN, enUS, zhCN } from 'naive-ui'
import enUSMessages from './locales/en-US'
import zhCNMessages from './locales/zh-CN'

export type LocaleCode = 'zh-CN' | 'en-US'

export const LOCALE_STORAGE_KEY = 'score-trans-locale'

export const LOCALE_OPTIONS: { value: LocaleCode; label: string }[] = [
  { value: 'zh-CN', label: '简体中文' },
  { value: 'en-US', label: 'English' },
]

const MESSAGES: Record<LocaleCode, unknown> = {
  'zh-CN': zhCNMessages,
  'en-US': enUSMessages,
}

export function isLocaleCode(value: unknown): value is LocaleCode {
  return value === 'zh-CN' || value === 'en-US'
}

function systemLocale(): LocaleCode {
  try {
    const tag = navigator.language || ''
    return tag.toLowerCase().startsWith('zh') ? 'zh-CN' : 'en-US'
  } catch {
    return 'zh-CN'
  }
}

function loadLocale(): LocaleCode {
  try {
    const raw = localStorage.getItem(LOCALE_STORAGE_KEY)
    if (isLocaleCode(raw)) return raw
  } catch {
    // localStorage may be unavailable in restricted renderer contexts.
  }
  return systemLocale()
}

export const locale = ref<LocaleCode>(loadLocale())

export function setLocale(next: LocaleCode): void {
  locale.value = next
  try {
    localStorage.setItem(LOCALE_STORAGE_KEY, next)
  } catch {
    // The preference stays effective for the current session.
  }
  void window.api.setLocale(next).catch(() => undefined)
}

/**
 * Reconciles the renderer locale with the main process copy. The main process
 * owns the persisted file; the renderer only caches it for a first-paint value.
 */
export async function initLocale(): Promise<void> {
  let stored: LocaleCode | null = null
  try {
    const raw = localStorage.getItem(LOCALE_STORAGE_KEY)
    if (isLocaleCode(raw)) stored = raw
  } catch {
    stored = null
  }
  try {
    const fromMain = await window.api.getLocale()
    // The main process owns the persisted file; the renderer only caches it so the
    // first paint already uses the right language.
    if (stored === null && isLocaleCode(fromMain)) {
      locale.value = fromMain
    }
  } catch {
    // Keep the cached renderer value when the main process is unreachable.
  }
}

type MessageVars = Record<string, string | number>

function lookup(source: unknown, key: string): unknown {
  let current: unknown = source
  for (const segment of key.split('.')) {
    if (typeof current !== 'object' || current === null) return undefined
    current = (current as Record<string, unknown>)[segment]
  }
  return current
}

export function t(key: string, vars?: MessageVars): string {
  const raw = lookup(MESSAGES[locale.value], key)
  if (typeof raw !== 'string') return key
  if (!vars) return raw
  return raw.replace(/\{(\w+)\}/g, (match, name: string) =>
    name in vars ? String(vars[name]) : match,
  )
}

export const naiveLocale = computed(() => (locale.value === 'zh-CN' ? zhCN : enUS))

export const naiveDateLocale = computed(() => (locale.value === 'zh-CN' ? dateZhCN : dateEnUS))
