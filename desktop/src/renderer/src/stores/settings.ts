import { defineStore } from 'pinia'
import { ref } from 'vue'
import { settingsApi, type SettingsQuery } from '../api/settings'
import type { LlmProviderOption, SettingsResponse } from '../models/types'

type ProviderKind = 'ocr' | 'ai' | 'assistant'

export const useSettingsStore = defineStore('settings', () => {
  const audiverisPath = ref('')
  const javaHome = ref('')
  const targetKey = ref('C')
  const outputDir = ref('')
  const ocrProvider = ref('siliconflow_deepseek_ocr')
  const ocrProviderOptions = ref<LlmProviderOption[]>([])
  const ocrApiKey = ref('')
  const ocrApiKeySet = ref(false)
  const ocrBaseUrl = ref('https://api.siliconflow.cn/v1')
  const ocrModel = ref('deepseek-ai/DeepSeek-OCR')
  const aiProvider = ref('siliconflow_qwen3_vl_8b')
  const aiProviderOptions = ref<LlmProviderOption[]>([])
  const aiApiKey = ref('')
  const aiApiKeySet = ref(false)
  const aiBaseUrl = ref('https://api.siliconflow.cn/v1')
  const aiModel = ref('Qwen/Qwen3-VL-8B-Instruct')
  const assistantProvider = ref('dashscope_deepseek_v4_flash')
  const assistantProviderOptions = ref<LlmProviderOption[]>([])
  const assistantApiKey = ref('')
  const assistantApiKeySet = ref(false)
  const assistantBaseUrl = ref('https://dashscope.aliyuncs.com/compatible-mode/v1')
  const assistantModel = ref('deepseek-v4-flash')
  const omrPreprocess = ref(true)
  const omrPreprocessLongEdge = ref(3600)
  const omrPreprocessBinarize = ref(false)
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
      loaded.value = true
    } catch (e) {
      console.error('Failed to load settings:', e)
    }
  }

  async function save(): Promise<void> {
    const data = await settingsApi.update({
      audiveris_path: audiverisPath.value,
      java_home: javaHome.value,
      output_dir: outputDir.value,
      target_key: targetKey.value,
      ocr_provider: ocrProvider.value,
      ocr_api_key: ocrApiKey.value || undefined,
      ai_provider: aiProvider.value,
      ai_api_key: aiApiKey.value || undefined,
      assistant_provider: assistantProvider.value,
      assistant_api_key: assistantApiKey.value || undefined,
      omr_preprocess: omrPreprocess.value,
      omr_preprocess_long_edge: omrPreprocessLongEdge.value,
      omr_preprocess_binarize: omrPreprocessBinarize.value,
    })
    applySettings(data)
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
    targetKey.value = data.target_key ?? 'C'
    outputDir.value = data.output_dir ?? ''
    ocrProvider.value = data.ocr_provider ?? 'siliconflow_deepseek_ocr'
    ocrProviderOptions.value = data.ocr_provider_options ?? []
    ocrApiKey.value = data.ocr_api_key ?? ''
    ocrApiKeySet.value = data.ocr_api_key_set ?? false
    ocrBaseUrl.value = data.ocr_base_url ?? 'https://api.siliconflow.cn/v1'
    ocrModel.value = data.ocr_model ?? 'deepseek-ai/DeepSeek-OCR'
    aiProvider.value = data.ai_provider ?? 'siliconflow_qwen3_vl_8b'
    aiProviderOptions.value = data.ai_provider_options ?? []
    aiApiKey.value = data.ai_api_key ?? ''
    aiApiKeySet.value = data.ai_api_key_set ?? false
    aiBaseUrl.value = data.ai_base_url ?? 'https://api.siliconflow.cn/v1'
    aiModel.value = data.ai_model ?? 'Qwen/Qwen3-VL-8B-Instruct'
    assistantProvider.value = data.assistant_provider ?? 'dashscope_deepseek_v4_flash'
    assistantProviderOptions.value = data.assistant_provider_options ?? []
    assistantApiKey.value = data.assistant_api_key ?? ''
    assistantApiKeySet.value = data.assistant_api_key_set ?? false
    assistantBaseUrl.value = data.assistant_base_url ?? 'https://dashscope.aliyuncs.com/compatible-mode/v1'
    assistantModel.value = data.assistant_model ?? 'deepseek-v4-flash'
    omrPreprocess.value = data.omr_preprocess ?? true
    omrPreprocessLongEdge.value = data.omr_preprocess_long_edge ?? 3600
    omrPreprocessBinarize.value = data.omr_preprocess_binarize ?? false
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
      ocrApiKey.value = data.ocr_api_key ?? ''
      ocrApiKeySet.value = data.ocr_api_key_set ?? false
      ocrBaseUrl.value = data.ocr_base_url ?? ocrBaseUrl.value
      ocrModel.value = data.ocr_model ?? ocrModel.value
      return
    }
    if (kind === 'ai') {
      aiProvider.value = data.ai_provider ?? aiProvider.value
      aiApiKey.value = data.ai_api_key ?? ''
      aiApiKeySet.value = data.ai_api_key_set ?? false
      aiBaseUrl.value = data.ai_base_url ?? aiBaseUrl.value
      aiModel.value = data.ai_model ?? aiModel.value
      return
    }
    assistantProvider.value = data.assistant_provider ?? assistantProvider.value
    assistantApiKey.value = data.assistant_api_key ?? ''
    assistantApiKeySet.value = data.assistant_api_key_set ?? false
    assistantBaseUrl.value = data.assistant_base_url ?? assistantBaseUrl.value
    assistantModel.value = data.assistant_model ?? assistantModel.value
  }

  return {
    audiverisPath,
    javaHome,
    targetKey,
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
    omrPreprocess,
    omrPreprocessLongEdge,
    omrPreprocessBinarize,
    loaded,
    load,
    save,
    loadProviderDetails,
  }
})
