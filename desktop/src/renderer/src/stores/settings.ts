import { defineStore } from 'pinia'
import { ref } from 'vue'
import { settingsApi } from '../api/settings'

export const useSettingsStore = defineStore('settings', () => {
  const audiverisPath = ref('')
  const javaHome = ref('')
  const targetKey = ref('C')
  const outputDir = ref('')
  const ocrApiKey = ref('')
  const ocrApiKeySet = ref(false)
  const ocrBaseUrl = ref('https://api.siliconflow.cn/v1')
  const ocrModel = ref('deepseek-ai/DeepSeek-OCR')
  const aiApiKey = ref('')
  const aiApiKeySet = ref(false)
  const aiBaseUrl = ref('https://api.siliconflow.cn/v1')
  const aiModel = ref('Qwen/Qwen3-VL-8B-Instruct')
  const assistantApiKey = ref('')
  const assistantApiKeySet = ref(false)
  const assistantBaseUrl = ref('https://dashscope.aliyuncs.com/compatible-mode/v1')
  const assistantModel = ref('deepseek-v4-flash')
  const omrPreprocess = ref(true)
  const omrPreprocessLongEdge = ref(3600)
  const omrPreprocessBinarize = ref(false)
  const loaded = ref(false)

  async function load(): Promise<void> {
    try {
      const data = await settingsApi.get()
      audiverisPath.value = data.audiveris_path
      javaHome.value = data.java_home
      targetKey.value = data.target_key ?? 'C'
      outputDir.value = data.output_dir ?? ''
      ocrApiKey.value = data.ocr_api_key ?? ''
      ocrApiKeySet.value = data.ocr_api_key_set ?? false
      ocrBaseUrl.value = data.ocr_base_url ?? 'https://api.siliconflow.cn/v1'
      ocrModel.value = data.ocr_model ?? 'deepseek-ai/DeepSeek-OCR'
      aiApiKey.value = data.ai_api_key ?? ''
      aiApiKeySet.value = data.ai_api_key_set ?? false
      aiBaseUrl.value = data.ai_base_url ?? 'https://api.siliconflow.cn/v1'
      aiModel.value = data.ai_model ?? 'Qwen/Qwen3-VL-8B-Instruct'
      assistantApiKey.value = data.assistant_api_key ?? ''
      assistantApiKeySet.value = data.assistant_api_key_set ?? false
      assistantBaseUrl.value = data.assistant_base_url ?? 'https://dashscope.aliyuncs.com/compatible-mode/v1'
      assistantModel.value = data.assistant_model ?? 'deepseek-v4-flash'
      omrPreprocess.value = data.omr_preprocess ?? true
      omrPreprocessLongEdge.value = data.omr_preprocess_long_edge ?? 3600
      omrPreprocessBinarize.value = data.omr_preprocess_binarize ?? false
      loaded.value = true
    } catch (e) {
      console.error('Failed to load settings:', e)
    }
  }

  async function save(): Promise<void> {
    await settingsApi.update({
      audiveris_path: audiverisPath.value,
      java_home: javaHome.value,
      output_dir: outputDir.value,
      target_key: targetKey.value,
      ocr_api_key: ocrApiKey.value || undefined,
      ocr_base_url: ocrBaseUrl.value,
      ocr_model: ocrModel.value,
      ai_api_key: aiApiKey.value || undefined,
      ai_base_url: aiBaseUrl.value,
      ai_model: aiModel.value,
      assistant_api_key: assistantApiKey.value || undefined,
      assistant_base_url: assistantBaseUrl.value,
      assistant_model: assistantModel.value,
      omr_preprocess: omrPreprocess.value,
      omr_preprocess_long_edge: omrPreprocessLongEdge.value,
      omr_preprocess_binarize: omrPreprocessBinarize.value,
    })
  }

  return {
    audiverisPath,
    javaHome,
    targetKey,
    outputDir,
    ocrApiKey,
    ocrApiKeySet,
    ocrBaseUrl,
    ocrModel,
    aiApiKey,
    aiApiKeySet,
    aiBaseUrl,
    aiModel,
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
  }
})
