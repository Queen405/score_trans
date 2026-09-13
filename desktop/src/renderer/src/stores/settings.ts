import { requireData } from '../api/client'
import { defineStore } from 'pinia'
import { computed, reactive, ref } from 'vue'
import { settingsApi, type SettingsQuery } from '../api/settings'
import { jianpuLayoutKey } from '../utils/jianpuLayout'
import type {
  AccidentalMode,
  CacheCleanupResponse,
  LlmProviderOption,
  MeasureNumberMode,
  PolyphonyMode,
  SettingsResponse,
  StoragePaths,
  TargetKey,
  ThemeMode,
} from '../models/types'

export type ProviderKind = 'ocr' | 'ai' | 'assistant'

export interface SettingsDraftProvider {
  provider: string
  apiKey: string
}

export interface SettingsDraft {
  audiverisPath: string
  javaHome: string
  audiverisMaxHeap: string
  audiverisMaxPixelCount: string
  audiverisAutoUpscale: boolean
  audiverisMinImageEdge: number
  dataDir: string
  cacheDir: string
  targetKey: TargetKey
  accidentalMode: AccidentalMode
  polyphonyMode: PolyphonyMode
  measureNumberMode: MeasureNumberMode
  jianpuSyntaxHighlight: boolean
  jianpuMeasureDurationCheck: boolean
  jianpuContentScalePercent: number
  jianpuSystemGapPercent: number
  jianpuShortNoteGapPercent: number
  jianpuBeatGapPercent: number
  enableOmrOcr: boolean
  outputDir: string
  jianpuAutoTranspose: boolean
  providers: Record<ProviderKind, SettingsDraftProvider>
  themeMode: ThemeMode
  showRecognitionOverlay: boolean
  showOcrOverlay: boolean
}

export interface ProviderDraftDetails {
  provider: string
  apiKeySet: boolean
  baseUrl: string
  model: string
}

const THEME_MODE_KEY = 'score-trans-theme-mode'
const SHOW_RECOGNITION_OVERLAY_KEY = 'score-trans-show-recognition-overlay'
const SHOW_OCR_OVERLAY_KEY = 'score-trans-show-ocr-overlay'

function loadThemeMode(): ThemeMode {
  try {
    const raw = localStorage.getItem(THEME_MODE_KEY)
    if (raw === 'dark' || raw === 'light' || raw === 'system') return raw
  } catch {
    // localStorage may be unavailable in restricted renderer contexts.
  }
  return 'light'
}

function loadBooleanPreference(key: string, fallback: boolean): boolean {
  try {
    const raw = localStorage.getItem(key)
    if (raw === '1') return true
    if (raw === '0') return false
  } catch {
    // localStorage may be unavailable in restricted renderer contexts.
  }
  return fallback
}

function saveBooleanPreference(key: string, value: boolean): void {
  try {
    localStorage.setItem(key, value ? '1' : '0')
  } catch {
    // Preference remains effective for the current session.
  }
}

function emptyProviderDetails(): ProviderDraftDetails {
  return {
    provider: '',
    apiKeySet: false,
    baseUrl: '',
    model: '',
  }
}

export const useSettingsStore = defineStore('settings', () => {
  const audiverisPath = ref('')
  const javaHome = ref('')
  const audiverisMaxHeap = ref('3g')
  const audiverisMaxPixelCount = ref('4500000')
  const audiverisAutoUpscale = ref(true)
  const audiverisMinImageEdge = ref(2500)
  const dataDir = ref('')
  const cacheDir = ref('')
  const activeDataDir = ref('')
  const activeCacheDir = ref('')
  const storageConfigPath = ref('')
  const cacheSizeBytes = ref(0)
  const cacheSizeAvailable = ref(false)
  const storageRestartRequired = ref(false)
  const targetKey = ref<TargetKey>('auto')
  const accidentalMode = ref<AccidentalMode>('auto')
  const polyphonyMode = ref<PolyphonyMode>('auto')
  const showMeasureNumbers = ref(true)
  const measureNumberMode = ref<MeasureNumberMode>('all')
  const jianpuSyntaxHighlight = ref(true)
  const jianpuMeasureDurationCheck = ref(true)
  const jianpuContentScalePercent = ref(80)
  const jianpuSystemGapPercent = ref(50)
  const jianpuShortNoteGapPercent = ref(20)
  const jianpuBeatGapPercent = ref(100)
  const enableOmrOcr = ref(false)
  const outputDir = ref('')
  const jianpuAutoTranspose = ref(true)
  const ocrProvider = ref('siliconflow_deepseek_ocr')
  const ocrProviderOptions = ref<LlmProviderOption[]>([])
  const ocrApiKey = ref('')
  const ocrApiKeySet = ref(false)
  const ocrBaseUrl = ref('https://api.siliconflow.cn/v1')
  const ocrModel = ref('deepseek-ai/DeepSeek-OCR')
  const aiProvider = ref('agnes_2_5_flash')
  const aiProviderOptions = ref<LlmProviderOption[]>([])
  const aiApiKey = ref('')
  const aiApiKeySet = ref(false)
  const aiBaseUrl = ref('https://apihub.agnes-ai.com/v1')
  const aiModel = ref('agnes-2.5-flash')
  const assistantProvider = ref('agnes_2_5_flash')
  const assistantProviderOptions = ref<LlmProviderOption[]>([])
  const assistantApiKey = ref('')
  const assistantApiKeySet = ref(false)
  const assistantBaseUrl = ref('https://apihub.agnes-ai.com/v1')
  const assistantModel = ref('agnes-2.5-flash')
  const themeMode = ref<ThemeMode>(loadThemeMode())
  const showRecognitionOverlay = ref(loadBooleanPreference(SHOW_RECOGNITION_OVERLAY_KEY, true))
  const showOcrOverlay = ref(loadBooleanPreference(SHOW_OCR_OVERLAY_KEY, false))

  const loaded = ref(false)
  const loading = ref(false)
  const loadError = ref<string | null>(null)
  const saving = ref(false)
  const saveError = ref<string | null>(null)
  const draftReady = ref(false)
  const draftBaseline = ref('')

  const draft = reactive<SettingsDraft>({
    audiverisPath: '',
    javaHome: '',
    audiverisMaxHeap: '3g',
    audiverisMaxPixelCount: '4500000',
    audiverisAutoUpscale: true,
    audiverisMinImageEdge: 2500,
    dataDir: '',
    cacheDir: '',
    targetKey: 'auto',
    accidentalMode: 'auto',
    polyphonyMode: 'auto',
    measureNumberMode: 'all',
    jianpuSyntaxHighlight: true,
    jianpuMeasureDurationCheck: true,
    jianpuContentScalePercent: 80,
    jianpuSystemGapPercent: 50,
    jianpuShortNoteGapPercent: 20,
    jianpuBeatGapPercent: 100,
    enableOmrOcr: false,
    outputDir: '',
    jianpuAutoTranspose: true,
    providers: {
      ocr: { provider: 'siliconflow_deepseek_ocr', apiKey: '' },
      ai: { provider: 'agnes_2_5_flash', apiKey: '' },
      assistant: { provider: 'agnes_2_5_flash', apiKey: '' },
    },
    themeMode: themeMode.value,
    showRecognitionOverlay: showRecognitionOverlay.value,
    showOcrOverlay: showOcrOverlay.value,
  })

  const draftProviderDetails = reactive<Record<ProviderKind, ProviderDraftDetails>>({
    ocr: emptyProviderDetails(),
    ai: emptyProviderDetails(),
    assistant: emptyProviderDetails(),
  })
  const providerDetailLoading = reactive<Record<ProviderKind, boolean>>({
    ocr: false,
    ai: false,
    assistant: false,
  })
  const providerDetailError = reactive<Record<ProviderKind, string | null>>({
    ocr: null,
    ai: null,
    assistant: null,
  })
  const providerLoadVersion: Record<ProviderKind, number> = {
    ocr: 0,
    ai: 0,
    assistant: 0,
  }

  const draftDirty = computed(
    () => draftReady.value && draftFingerprint(draft) !== draftBaseline.value,
  )
  const jianpuLayoutKeyValue = computed(() => jianpuLayoutKey(
    jianpuContentScalePercent.value,
    jianpuSystemGapPercent.value,
    jianpuShortNoteGapPercent.value,
    jianpuBeatGapPercent.value,
  ))
  const jianpuLayoutRequest = computed(() => ({
    jianpu_content_scale_percent: jianpuContentScalePercent.value,
    jianpu_system_gap_percent: jianpuSystemGapPercent.value,
    jianpu_short_note_gap_percent: jianpuShortNoteGapPercent.value,
    jianpu_beat_gap_percent: jianpuBeatGapPercent.value,
  }))

  async function load(): Promise<void> {
    if (loading.value) return
    loading.value = true
    loadError.value = null
    try {
      const data = await requireData(settingsApi.get())
      applySettings(data)
      await loadStoragePaths()
      loaded.value = true
    } catch (error: unknown) {
      loaded.value = false
      loadError.value = errorMessage(error)
      console.error('Failed to load settings:', error)
    } finally {
      loading.value = false
    }
  }

  function beginEdit(): void {
    assignDraft({
      audiverisPath: audiverisPath.value,
      javaHome: javaHome.value,
      audiverisMaxHeap: audiverisMaxHeap.value,
      audiverisMaxPixelCount: audiverisMaxPixelCount.value,
      audiverisAutoUpscale: audiverisAutoUpscale.value,
      audiverisMinImageEdge: audiverisMinImageEdge.value,
      dataDir: dataDir.value,
      cacheDir: cacheDir.value,
      targetKey: targetKey.value,
      accidentalMode: accidentalMode.value,
      polyphonyMode: polyphonyMode.value,
      measureNumberMode: measureNumberMode.value,
      jianpuSyntaxHighlight: jianpuSyntaxHighlight.value,
      jianpuMeasureDurationCheck: jianpuMeasureDurationCheck.value,
      jianpuContentScalePercent: jianpuContentScalePercent.value,
      jianpuSystemGapPercent: jianpuSystemGapPercent.value,
      jianpuShortNoteGapPercent: jianpuShortNoteGapPercent.value,
      jianpuBeatGapPercent: jianpuBeatGapPercent.value,
      enableOmrOcr: enableOmrOcr.value,
      outputDir: outputDir.value,
      jianpuAutoTranspose: jianpuAutoTranspose.value,
      providers: {
        ocr: { provider: ocrProvider.value, apiKey: '' },
        ai: { provider: aiProvider.value, apiKey: '' },
        assistant: { provider: assistantProvider.value, apiKey: '' },
      },
      themeMode: themeMode.value,
      showRecognitionOverlay: showRecognitionOverlay.value,
      showOcrOverlay: showOcrOverlay.value,
    })

    setDraftProviderDetails('ocr', {
      provider: ocrProvider.value,
      apiKeySet: ocrApiKeySet.value,
      baseUrl: ocrBaseUrl.value,
      model: ocrModel.value,
    })
    setDraftProviderDetails('ai', {
      provider: aiProvider.value,
      apiKeySet: aiApiKeySet.value,
      baseUrl: aiBaseUrl.value,
      model: aiModel.value,
    })
    setDraftProviderDetails('assistant', {
      provider: assistantProvider.value,
      apiKeySet: assistantApiKeySet.value,
      baseUrl: assistantBaseUrl.value,
      model: assistantModel.value,
    })

    providerDetailError.ocr = null
    providerDetailError.ai = null
    providerDetailError.assistant = null
    draftReady.value = true
    draftBaseline.value = draftFingerprint(draft)
    saveError.value = null
  }

  function discardDraft(): void {
    beginEdit()
  }

  async function applyDraft(): Promise<boolean> {
    if (!draftReady.value) beginEdit()
    const next = cloneDraft(draft)
    saving.value = true
    saveError.value = null

    try {
      const data = await requireData(
        settingsApi.update({
          audiveris_path: next.audiverisPath,
          java_home: next.javaHome,
          audiveris_max_heap: next.audiverisMaxHeap as '1g' | '2g' | '3g' | '4g',
          audiveris_max_pixel_count: next.audiverisMaxPixelCount,
          audiveris_auto_upscale: next.audiverisAutoUpscale,
          audiveris_min_image_edge: next.audiverisMinImageEdge,
          output_dir: next.outputDir,
          target_key: next.targetKey,
          accidental_mode: next.accidentalMode,
          polyphony_mode: next.polyphonyMode,
          show_measure_numbers: next.measureNumberMode !== 'none',
          measure_number_mode: next.measureNumberMode,
          jianpu_syntax_highlight: next.jianpuSyntaxHighlight,
          jianpu_measure_duration_check: next.jianpuMeasureDurationCheck,
          jianpu_content_scale_percent: next.jianpuContentScalePercent,
          jianpu_system_gap_percent: next.jianpuSystemGapPercent,
          jianpu_short_note_gap_percent: next.jianpuShortNoteGapPercent,
          jianpu_beat_gap_percent: next.jianpuBeatGapPercent,
          enable_omr_ocr: next.enableOmrOcr,
          jianpu_auto_transpose: next.jianpuAutoTranspose,
          ocr_provider: next.providers.ocr.provider,
          ocr_api_key: next.providers.ocr.apiKey.trim() || undefined,
          ai_provider: next.providers.ai.provider,
          ai_api_key: next.providers.ai.apiKey.trim() || undefined,
          assistant_provider: next.providers.assistant.provider,
          assistant_api_key: next.providers.assistant.apiKey.trim() || undefined,
        }),
      )
      const storageResult = await persistStoragePaths(next.dataDir, next.cacheDir)

      applySettings(data)
      applyStoragePaths(storageResult.paths)
      storageRestartRequired.value = storageResult.restartRequired
      setThemeMode(next.themeMode)
      setShowRecognitionOverlay(next.showRecognitionOverlay)
      setShowOcrOverlay(next.showOcrOverlay)
      beginEdit()
      return storageResult.restartRequired
    } catch (error: unknown) {
      saveError.value = errorMessage(error)
      throw error
    } finally {
      saving.value = false
    }
  }

  async function loadDraftProviderDetails(kind: ProviderKind): Promise<void> {
    const provider = draft.providers[kind].provider
    const version = providerLoadVersion[kind] + 1
    providerLoadVersion[kind] = version
    draft.providers[kind].apiKey = ''
    setDraftProviderDetails(kind, {
      provider,
      apiKeySet: false,
      baseUrl: '',
      model: '',
    })
    providerDetailLoading[kind] = true
    providerDetailError[kind] = null

    try {
      const data = await requireData(settingsApi.get(providerQuery(kind, provider)))
      if (
        providerLoadVersion[kind] !== version ||
        draft.providers[kind].provider !== provider
      ) {
        return
      }
      setDraftProviderDetails(kind, providerDetailsFromResponse(kind, provider, data))
    } catch (error: unknown) {
      if (providerLoadVersion[kind] !== version) return
      providerDetailError[kind] = errorMessage(error)
      throw error
    } finally {
      if (providerLoadVersion[kind] === version) {
        providerDetailLoading[kind] = false
      }
    }
  }

  function setThemeMode(mode: ThemeMode): void {
    themeMode.value = mode
    try {
      localStorage.setItem(THEME_MODE_KEY, mode)
    } catch {
      // Theme remains effective for the current session.
    }
  }

  function setShowRecognitionOverlay(value: boolean): void {
    showRecognitionOverlay.value = value
    saveBooleanPreference(SHOW_RECOGNITION_OVERLAY_KEY, value)
  }

  function setShowOcrOverlay(value: boolean): void {
    showOcrOverlay.value = value
    saveBooleanPreference(SHOW_OCR_OVERLAY_KEY, value)
  }

  async function clearCache(): Promise<CacheCleanupResponse> {
    const result = await requireData(settingsApi.clearCache())
    const api = window.api
    if (typeof api.clearElectronCache === 'function') {
      await api.clearElectronCache()
    }
    cacheSizeBytes.value = result.after_bytes
    return result
  }

  async function relaunchApp(): Promise<void> {
    const api = window.api
    if (typeof api.relaunchApp === 'function') {
      await api.relaunchApp()
    }
  }

  function applySettings(data: SettingsResponse): void {
    audiverisPath.value = data.audiveris_path
    javaHome.value = data.java_home
    audiverisMaxHeap.value = data.audiveris_max_heap ?? '3g'
    audiverisMaxPixelCount.value = data.audiveris_max_pixel_count ?? '4500000'
    audiverisAutoUpscale.value = data.audiveris_auto_upscale ?? true
    audiverisMinImageEdge.value = data.audiveris_min_image_edge ?? 2500
    activeDataDir.value = data.data_dir ?? ''
    activeCacheDir.value = data.cache_dir ?? data.work_dir ?? ''
    cacheSizeBytes.value = data.cache_size_bytes ?? 0
    cacheSizeAvailable.value = Object.prototype.hasOwnProperty.call(data, 'cache_size_bytes')
    if (!dataDir.value) dataDir.value = activeDataDir.value
    if (!cacheDir.value) cacheDir.value = activeCacheDir.value
    targetKey.value = data.target_key ?? 'auto'
    accidentalMode.value = data.accidental_mode ?? 'auto'
    polyphonyMode.value = data.polyphony_mode ?? 'auto'
    measureNumberMode.value =
      data.measure_number_mode ?? (data.show_measure_numbers === false ? 'none' : 'all')
    showMeasureNumbers.value = measureNumberMode.value !== 'none'
    jianpuSyntaxHighlight.value = data.jianpu_syntax_highlight ?? true
    jianpuMeasureDurationCheck.value = data.jianpu_measure_duration_check ?? true
    jianpuContentScalePercent.value = data.jianpu_content_scale_percent ?? 80
    jianpuSystemGapPercent.value = data.jianpu_system_gap_percent ?? 50
    jianpuShortNoteGapPercent.value = data.jianpu_short_note_gap_percent ?? 20
    jianpuBeatGapPercent.value = data.jianpu_beat_gap_percent ?? 100
    enableOmrOcr.value = data.enable_omr_ocr ?? false
    outputDir.value = data.output_dir ?? ''
    jianpuAutoTranspose.value = data.jianpu_auto_transpose ?? true
    ocrProvider.value = data.ocr_provider ?? 'siliconflow_deepseek_ocr'
    ocrProviderOptions.value = data.ocr_provider_options ?? []
    ocrApiKey.value = ''
    ocrApiKeySet.value = data.ocr_api_key_set ?? false
    ocrBaseUrl.value = data.ocr_base_url ?? 'https://api.siliconflow.cn/v1'
    ocrModel.value = data.ocr_model ?? 'deepseek-ai/DeepSeek-OCR'
    aiProvider.value = data.ai_provider ?? 'agnes_2_5_flash'
    aiProviderOptions.value = data.ai_provider_options ?? []
    aiApiKey.value = ''
    aiApiKeySet.value = data.ai_api_key_set ?? false
    aiBaseUrl.value = data.ai_base_url ?? 'https://apihub.agnes-ai.com/v1'
    aiModel.value = data.ai_model ?? 'agnes-2.5-flash'
    assistantProvider.value =
      data.assistant_provider ?? 'agnes_2_5_flash'
    assistantProviderOptions.value = data.assistant_provider_options ?? []
    assistantApiKey.value = ''
    assistantApiKeySet.value = data.assistant_api_key_set ?? false
    assistantBaseUrl.value =
      data.assistant_base_url ?? 'https://apihub.agnes-ai.com/v1'
    assistantModel.value = data.assistant_model ?? 'agnes-2.5-flash'
  }

  async function loadStoragePaths(): Promise<void> {
    const api = window.api
    if (typeof api.getStoragePaths !== 'function') {
      dataDir.value = activeDataDir.value
      cacheDir.value = activeCacheDir.value
      storageRestartRequired.value = false
      return
    }

    const paths = await api.getStoragePaths()
    applyStoragePaths(paths)
  }

  async function persistStoragePaths(
    requestedDataDir: string,
    requestedCacheDir: string,
  ): Promise<{ paths: StoragePaths; restartRequired: boolean }> {
    const api = window.api
    if (typeof api.setStoragePaths !== 'function') {
      return {
        paths: {
          dataDir: requestedDataDir,
          cacheDir: requestedCacheDir,
          configPath: storageConfigPath.value,
        },
        restartRequired: false,
      }
    }

    const paths = (await api.setStoragePaths({
      dataDir: requestedDataDir,
      cacheDir: requestedCacheDir,
    })) as StoragePaths
    return {
      paths,
      restartRequired:
        normalizePath(paths.dataDir) !== normalizePath(activeDataDir.value) ||
        normalizePath(paths.cacheDir) !== normalizePath(activeCacheDir.value),
    }
  }

  function applyStoragePaths(paths: StoragePaths): void {
    dataDir.value = paths.dataDir
    cacheDir.value = paths.cacheDir
    storageConfigPath.value = paths.configPath
    storageRestartRequired.value =
      normalizePath(paths.dataDir) !== normalizePath(activeDataDir.value) ||
      normalizePath(paths.cacheDir) !== normalizePath(activeCacheDir.value)
  }

  function assignDraft(next: SettingsDraft): void {
    draft.audiverisPath = next.audiverisPath
    draft.javaHome = next.javaHome
    draft.audiverisMaxHeap = next.audiverisMaxHeap
    draft.audiverisMaxPixelCount = next.audiverisMaxPixelCount
    draft.audiverisAutoUpscale = next.audiverisAutoUpscale
    draft.audiverisMinImageEdge = next.audiverisMinImageEdge
    draft.dataDir = next.dataDir
    draft.cacheDir = next.cacheDir
    draft.targetKey = next.targetKey
    draft.accidentalMode = next.accidentalMode
    draft.polyphonyMode = next.polyphonyMode
    draft.measureNumberMode = next.measureNumberMode
    draft.jianpuSyntaxHighlight = next.jianpuSyntaxHighlight
    draft.jianpuMeasureDurationCheck = next.jianpuMeasureDurationCheck
    draft.jianpuContentScalePercent = next.jianpuContentScalePercent
    draft.jianpuSystemGapPercent = next.jianpuSystemGapPercent
    draft.jianpuShortNoteGapPercent = next.jianpuShortNoteGapPercent
    draft.jianpuBeatGapPercent = next.jianpuBeatGapPercent
    draft.enableOmrOcr = next.enableOmrOcr
    draft.outputDir = next.outputDir
    draft.jianpuAutoTranspose = next.jianpuAutoTranspose
    draft.providers.ocr = { ...next.providers.ocr }
    draft.providers.ai = { ...next.providers.ai }
    draft.providers.assistant = { ...next.providers.assistant }
    draft.themeMode = next.themeMode
    draft.showRecognitionOverlay = next.showRecognitionOverlay
    draft.showOcrOverlay = next.showOcrOverlay
  }

  function setDraftProviderDetails(
    kind: ProviderKind,
    details: ProviderDraftDetails,
  ): void {
    Object.assign(draftProviderDetails[kind], details)
  }

  return {
    audiverisPath,
    javaHome,
    audiverisMaxHeap,
    audiverisMaxPixelCount,
    audiverisAutoUpscale,
    audiverisMinImageEdge,
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
    polyphonyMode,
    showMeasureNumbers,
    measureNumberMode,
    jianpuSyntaxHighlight,
    jianpuMeasureDurationCheck,
    jianpuContentScalePercent,
    jianpuSystemGapPercent,
    jianpuShortNoteGapPercent,
    jianpuBeatGapPercent,
    jianpuLayoutKey: jianpuLayoutKeyValue,
    jianpuLayoutRequest,
    enableOmrOcr,
    outputDir,
    jianpuAutoTranspose,
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
    showRecognitionOverlay,
    showOcrOverlay,
    loaded,
    loading,
    loadError,
    saving,
    saveError,
    draft,
    draftReady,
    draftDirty,
    draftProviderDetails,
    providerDetailLoading,
    providerDetailError,
    load,
    beginEdit,
    discardDraft,
    applyDraft,
    loadDraftProviderDetails,
    clearCache,
    relaunchApp,
    setThemeMode,
    setShowRecognitionOverlay,
    setShowOcrOverlay,
  }
})

function cloneDraft(draft: SettingsDraft): SettingsDraft {
  return {
    ...draft,
    providers: {
      ocr: { ...draft.providers.ocr },
      ai: { ...draft.providers.ai },
      assistant: { ...draft.providers.assistant },
    },
  }
}

function draftFingerprint(draft: SettingsDraft): string {
  return JSON.stringify(draft)
}

function normalizePath(value: string): string {
  return value.trim().replace(/\\/g, '/').replace(/\/+$/, '').toLowerCase()
}

function providerQuery(kind: ProviderKind, provider: string): SettingsQuery {
  if (kind === 'ocr') return { ocr_provider: provider }
  if (kind === 'ai') return { ai_provider: provider }
  return { assistant_provider: provider }
}

function providerDetailsFromResponse(
  kind: ProviderKind,
  provider: string,
  data: SettingsResponse,
): ProviderDraftDetails {
  if (kind === 'ocr') {
    return {
      provider,
      apiKeySet: data.ocr_api_key_set ?? false,
      baseUrl: data.ocr_base_url ?? '',
      model: data.ocr_model ?? '',
    }
  }
  if (kind === 'ai') {
    return {
      provider,
      apiKeySet: data.ai_api_key_set ?? false,
      baseUrl: data.ai_base_url ?? '',
      model: data.ai_model ?? '',
    }
  }
  return {
    provider,
    apiKeySet: data.assistant_api_key_set ?? false,
    baseUrl: data.assistant_base_url ?? '',
    model: data.assistant_model ?? '',
  }
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error)
}
