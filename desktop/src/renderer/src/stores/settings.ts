import { defineStore } from 'pinia'
import { ref } from 'vue'
import { settingsApi } from '../api/settings'

export const useSettingsStore = defineStore('settings', () => {
  const audiverisPath = ref('')
  const musescorePath = ref('')
  const javaHome = ref('')
  const targetKey = ref('C')
  const startMeasureNumber = ref<number | null>(null)
  const outputDir = ref('')
  const ocrApiKey = ref('')
  const ocrBaseUrl = ref('https://api.siliconflow.cn/v1')
  const ocrModel = ref('deepseek-ai/DeepSeek-OCR')
  const loaded = ref(false)

  async function load(): Promise<void> {
    try {
      const data = await settingsApi.get()
      audiverisPath.value = data.audiveris_path
      musescorePath.value = data.musescore_path
      javaHome.value = data.java_home
      loaded.value = true
    } catch (e) {
      console.error('Failed to load settings:', e)
    }
  }

  async function save(): Promise<void> {
    await settingsApi.update({
      audiveris_path: audiverisPath.value,
      musescore_path: musescorePath.value,
      java_home: javaHome.value,
    })
  }

  return {
    audiverisPath,
    musescorePath,
    javaHome,
    targetKey,
    startMeasureNumber,
    outputDir,
    ocrApiKey,
    ocrBaseUrl,
    ocrModel,
    loaded,
    load,
    save,
  }
})
