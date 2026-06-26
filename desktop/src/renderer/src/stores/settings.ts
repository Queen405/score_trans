import { defineStore } from 'pinia'
import { ref } from 'vue'
import { settingsApi, type SettingsQuery } from '../api/settings'
import type { AccidentalMode, CacheCleanupResponse, LlmProviderOption, MeasureNumberMode, SettingsResponse, StoragePaths, TargetKey, ThemeMode } from '../models/types'

type ProviderKind = 'ocr' | 'ai' | 'assistant'

const THEME_MODE_KEY = 'score-trans-theme-mode'

function loadThemeMode(): ThemeMode {
  try {
    const raw = localStorage.getItem(THEME_MODE_KEY)
    if (raw === 'dark' || raw === 'light' || raw === 'system') return raw
  } catch {
    // ignore
  }
  return 'system'
}

export const useSettingsStore = defineStore('settings', () => {
  const audiverisPath = ref('')
  const javaHome = ref('')
  const dataDir = ref('')
  const cacheDir = ref('')
  const activeDataDir = ref('')
  const activeCacheDir = ref('')
  const storageConfigPath = ref('')
  const cacheSizeBytes = ref(0)
  const cacheSizeAvailable = ref(false)
  const storageRestartRequired = ref(false)
  const targetKey = ref<TargetKey>('C')
  const accidentalMode = ref<AccidentalMode>('auto')
  const showMeasureNumbers = ref(true)
  const measureNumberMode = ref<MeasureNumberMode>('all')
  const confirmStartMeasureNumber = ref(true)
  const jianpuSyntaxHighlight = ref(false)
  const outputDir = ref('')
  const ocrProvider = ref('siliconflow_deepseek_ocr')
  const ocrProviderOptions = ref<LlmProviderOption[]>([])
  const ocrApiKey = ref('')
  const ocrApiKeySet = ref(false)
  const ocrBaseUrl = ref('https://api.siliconflow.cn/v1')
  const ocrModel = ref('deepseek-ai/DeepSeek-OCR')
  const aiProvider = ref('xiaomi_mimo_v25')
  const aiProviderOptions = ref<LlmProviderOption[]>([])
  const aiApiKey = ref('')
  const aiApiKeySet = ref(false)
  const aiBaseUrl = ref('https://api.xiaomimimo.com/v1')
  const aiModel = ref('mimo-v2.5')
  const assistantProvider = ref('dashscope_deepseek_v4_flash')
  const assistantProviderOptions = ref<LlmProviderOption[]>([])
  const assistantApiKey = ref('')
  const assistantApiKeySet = ref(false)
  const assistantBaseUrl = ref('https://dashscope.aliyuncs.com/compatible-mode/v1')
  const assistantModel = ref('deepseek-v4-flash')
  const themeMode = ref<ThemeMode>(loadThemeMode())
  const loaded = ref(false)
  const providerLoadVersion = {
    ocr: 0,
    ai: 0,
    assistant: 0,
  }

  async function load(): Promise<void> {
    try {
      const data = await settingsApi.get()
      applySettings(data)
      await loadStoragePaths()
      loaded.value = true
    } catch (e) {
      console.error('Failed to load settings:', e)
    }
  }

  function setThemeMode(mode: ThemeMode): void {
    themeMode.value = mode
    try {
      localStorage.setItem(THEME_MODE_KEY, mode)
    } catch {
      // ignore
    }
  }

  async function save(): Promise<boolean> {
    const requestedDataDir = dataDir.value
    const requestedCacheDir = cacheDir.value
    const data = await settingsApi.update({
      audiveris_path: audiverisPath.value,
      java_home: javaHome.value,
      output_dir: outputDir.value,
      target_key: targetKey.value,
      accidental_mode: accidentalMode.value,
      show_measure_numbers: measureNumberMode.value !== 'none',
      measure_number_mode: measureNumberMode.value,
      confirm_start_measure_number: confirmStartMeasureNumber.value,
      jianpu_syntax_highlight: jianpuSyntaxHighlight.value,
      ocr_provider: ocrProvider.value,
      ocr_api_key: ocrApiKey.value || undefined,
      ai_provider: aiProvider.value,
      ai_api_key: aiApiKey.value || undefined,
      assistant_provider: assistantProvider.value,
      assistant_api_key: assistantApiKey.value || undefined,
    })
    applySettings(data)
    dataDir.value = requestedDataDir
    cacheDir.value = requestedCacheDir
    return await saveStoragePaths()
  }

  async function clearCache(): Promise<CacheCleanupResponse> {
    const result = await settingsApi.clearCache()
    const api = (globalThis as any).api
    if (typeof api?.clearElectronCache === 'function') {
      await api.clearElectronCache()
    }
    cacheSizeBytes.value = result.after_bytes
    return result
  }

  async function relaunchApp(): Promise<void> {
    const api = (window as any).api
    if (typeof api?.relaunchApp === 'function') {
      await api.relaunchApp()
    }
  }

  async function loadProviderDetails(kind: ProviderKind): Promise<void> {
    const provider = selectedProvider(kind)
    const version = providerLoadVersion[kind] + 1
    providerLoadVersion[kind] = version
    const data = await settingsApi.get(providerQuery(kind, provider))
    if (providerLoadVersion[kind] !== version || selectedProvider(kind) !== provider) return
    applyProviderSettings(kind, data)
  }

  function applySettings(data: SettingsResponse): void {
    audiverisPath.value = data.audiveris_path
    javaHome.value = data.java_home
    activeDataDir.value = data.data_dir ?? ''
    activeCacheDir.value = data.cache_dir ?? data.work_dir ?? ''
    cacheSizeBytes.value = data.cache_size_bytes ?? 0
    cacheSizeAvailable.value = Object.prototype.hasOwnProperty.call(data, 'cache_size_bytes')
    if (!dataDir.value) dataDir.value = activeDataDir.value
    if (!cacheDir.value) cacheDir.value = activeCacheDir.value
    targetKey.value = data.target_key ?? 'C'
    accidentalMode.value = data.accidental_mode ?? 'auto'
    measureNumberMode.value = data.measure_number_mode ?? (data.show_measure_numbers === false ? 'none' : 'all')
    showMeasureNumbers.value = measureNumberMode.value !== 'none'
    confirmStartMeasureNumber.value = data.confirm_start_measure_number ?? true
    jianpuSyntaxHighlight.value = data.jianpu_syntax_highlight ?? false
    outputDir.value = data.output_dir ?? ''
    ocrProvider.value = data.ocr_provider ?? 'siliconflow_deepseek_ocr'
    ocrProviderOptions.value = data.ocr_provider_options ?? []
    ocrApiKey.value = ''
    ocrApiKeySet.value = data.ocr_api_key_set ?? false
    ocrBaseUrl.value = data.ocr_base_url ?? 'https://api.siliconflow.cn/v1'
    ocrModel.value = data.ocr_model ?? 'deepseek-ai/DeepSeek-OCR'
    aiProvider.value = data.ai_provider ?? 'xiaomi_mimo_v25'
    aiProviderOptions.value = data.ai_provider_options ?? []
    aiApiKey.value = ''
    aiApiKeySet.value = data.ai_api_key_set ?? false
    aiBaseUrl.value = data.ai_base_url ?? 'https://api.xiaomimimo.com/v1'
    aiModel.value = data.ai_model ?? 'mimo-v2.5'
    assistantProvider.value = data.assistant_provider ?? 'dashscope_deepseek_v4_flash'
    assistantProviderOptions.value = data.assistant_provider_options ?? []
    assistantApiKey.value = ''
    assistantApiKeySet.value = data.assistant_api_key_set ?? false
    assistantBaseUrl.value = data.assistant_base_url ?? 'https://dashscope.aliyuncs.com/compatible-mode/v1'
    assistantModel.value = data.assistant_model ?? 'deepseek-v4-flash'
  }

  async function loadStoragePaths(): Promise<void> {
    const api = (window as any).api
    if (typeof api?.getStoragePaths !== 'function') {
      dataDir.value = activeDataDir.value
      cacheDir.value = activeCacheDir.value
      storageRestartRequired.value = false
      return
    }

    const paths = (await api.getStoragePaths()) as StoragePaths
    applyStoragePaths(paths)
  }

  async function saveStoragePaths(): Promise<boolean> {
    const api = (window as any).api
    if (typeof api?.setStoragePaths !== 'function') {
      return false
    }
    const beforeDataDir = activeDataDir.value
    const beforeCacheDir = activeCacheDir.value
    const paths = (await api.setStoragePaths({
      dataDir: dataDir.value,
      cacheDir: cacheDir.value,
    })) as StoragePaths
    applyStoragePaths(paths)
    storageRestartRequired.value =
      normalizePath(paths.dataDir) !== normalizePath(beforeDataDir) ||
      normalizePath(paths.cacheDir) !== normalizePath(beforeCacheDir)
    return storageRestartRequired.value
  }

  function applyStoragePaths(paths: StoragePaths): void {
    dataDir.value = paths.dataDir
    cacheDir.value = paths.cacheDir
    storageConfigPath.value = paths.configPath
    storageRestartRequired.value =
      normalizePath(paths.dataDir) !== normalizePath(activeDataDir.value) ||
      normalizePath(paths.cacheDir) !== normalizePath(activeCacheDir.value)
  }

  function normalizePath(value: string): string {
    return value.trim().replace(/\\/g, '/').replace(/\/+$/, '').toLowerCase()
  }

  function selectedProvider(kind: ProviderKind): string {
    if (kind === 'ocr') return ocrProvider.value
    if (kind === 'ai') return aiProvider.value
    return assistantProvider.value
  }

  function providerQuery(kind: ProviderKind, provider: string): SettingsQuery {
    if (kind === 'ocr') return { ocr_provider: provider }
    if (kind === 'ai') return { ai_provider: provider }
    return { assistant_provider: provider }
  }

  function applyProviderSettings(kind: ProviderKind, data: SettingsResponse): void {
    if (kind === 'ocr') {
      ocrProvider.value = data.ocr_provider ?? ocrProvider.value
      ocrApiKey.value = ''
      ocrApiKeySet.value = data.ocr_api_key_set ?? false
      ocrBaseUrl.value = data.ocr_base_url ?? ocrBaseUrl.value
      ocrModel.value = data.ocr_model ?? ocrModel.value
      return
    }
    if (kind === 'ai') {
      aiProvider.value = data.ai_provider ?? aiProvider.value
      aiApiKey.value = ''
      aiApiKeySet.value = data.ai_api_key_set ?? false
      aiBaseUrl.value = data.ai_base_url ?? aiBaseUrl.value
      aiModel.value = data.ai_model ?? aiModel.value
      return
    }
    assistantProvider.value = data.assistant_provider ?? assistantProvider.value
    assistantApiKey.value = ''
    assistantApiKeySet.value = data.assistant_api_key_set ?? false
    assistantBaseUrl.value = data.assistant_base_url ?? assistantBaseUrl.value
    assistantModel.value = data.assistant_model ?? assistantModel.value
  }

  return {
    audiverisPath,
    javaHome,
    dataDir,
    cacheDir,
    activeDataDir,
    activeCacheDir,
    storageConfigPath,
    cacheSizeBytes,
    cacheSizeAvailable,
    storageRestartRequired,
    targetKey,
    accidentalMode,
    showMeasureNumbers,
    measureNumberMode,
    confirmStartMeasureNumber,
    jianpuSyntaxHighlight,
    outputDir,
    ocrProvider,
    ocrProviderOptions,
    ocrApiKey,
    ocrApiKeySet,
    ocrBaseUrl,
    ocrModel,
    aiProvider,
    aiProviderOptions,
    aiApiKey,
    aiApiKeySet,
    aiBaseUrl,
    aiModel,
    assistantProvider,
    assistantProviderOptions,
    assistantApiKey,
    assistantApiKeySet,
    assistantBaseUrl,
    assistantModel,
    themeMode,
    loaded,
    load,
    save,
    clearCache,
    relaunchApp,
    loadProviderDetails,
    setThemeMode,
  }
})
