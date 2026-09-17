import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import { initializeBackendConnection } from './api/client'
import { initLocale } from './i18n'

async function bootstrap(): Promise<void> {
  await initializeBackendConnection()
  await initLocale()
  const app = createApp(App)
  app.use(createPinia())
  app.mount('#app')
}

void bootstrap()
