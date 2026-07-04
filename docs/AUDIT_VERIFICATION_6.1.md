# Score Trans 审计修复验证报告 — 第 6.1 章

> 验证日期：2026-07-04
> 验证范围：AUDIT_REPORT.md 第 6.1 节「Vue 响应性与内存泄漏」全部 10 项审计发现
> 验证方法：逐文件逐函数完整通读全部已提交代码（commit `a8a6b5a` + `4a6a870`），交叉验证模板绑定、script setup 作用域、生命周期清理和响应式替换模式，加全部前端/后端测试套件回归
> 测试基线：后端 422 passed / 1 skipped；前端 lifecycle 7 passed；前端 page-sections 34 passed；SVG sanitizer 3 passed；backend lifecycle 4 passed；main file security 6 passed；storage migration 1 passed / 1 skipped；TypeScript 通过；ESLint 0 error / 1 warning；Ruff 通过

---

## 目录

1. [验证结果总览](#1-验证结果总览)
2. [逐项验证详情](#2-逐项验证详情)
3. [关联修复验证](#3-关联修复验证)
4. [新问题评估](#4-新问题评估)
5. [测试质量评估](#5-测试质量评估)
6. [结论](#6-结论)

---

## 1. 验证结果总览

### 1.1 修复完成度

| 审计章节 | 修复项数 | 已修复 | 不适用 | 验证结果 |
|---------|---------|--------|--------|---------|
| 6.1 Vue 响应性与内存泄漏 | 10 | 8 | 2（审计误报） | ✅ 全部正确 |

### 1.2 测试验证

| 门禁 | 命令 | 结果 |
|------|------|------|
| 后端全量 | `python -m pytest -q` | 422 passed, 1 skipped, 1 warning |
| 前端 lifecycle 专项 | `node scripts/test-frontend-lifecycle.mjs` | 7 passed |
| 前端 page-sections | `node scripts/test-jianpu-page-sections.mjs` | 34 passed |
| SVG sanitizer | `node scripts/test-svg-sanitizer.mjs` | 3 passed |
| backend lifecycle | `node scripts/test-backend-lifecycle.mjs` | 4 passed |
| main file security | `node scripts/test-main-file-security.mjs` | 6 passed |
| storage migration | `node scripts/test-storage-migration.mjs` | 1 passed, 1 skipped |
| Ruff | `ruff check backend/ tests/` | All checks passed |
| ESLint | `pnpm lint` | 0 errors, 1 warning (AiAssistant v-html 既有) |
| TypeScript | `vue-tsc --noEmit` | 通过 |

---

## 2. 逐项验证详情

### 6.1.1 日志条目无上限，无限增长 — ✅ 已修复

**审计位置**：`stores/log.ts:10`

**修复内容**：
- `stores/log.ts:4`：新增常量 `MAX_LOG_ENTRIES = 1000`，硬上限。
- `stores/log.ts:15`：引入 `nextLogId`（从 1 开始的单调递增计数器），每条日志分配唯一稳定 ID。
- `stores/log.ts:24-27`：`addLog()` 在 push 后计算 `overflow = entries.value.length - MAX_LOG_ENTRIES`，若 `overflow > 0` 则 `splice(0, overflow)` 从头部移除多余条目。

**验证结论**：日志数组被严格限制在 1000 条以内，`splice(0, overflow)` 正确处理了批量溢出。`nextLogId` 确保每条记录有全局唯一 ID，不会因 splice 导致 key 冲突。

---

### 6.1.2 模块级 `uploadQueue` 跨实例共享 — ❌ 不适用（审计误报）

**审计位置**：`components/FileUploader.vue:57`

**验证**：
- `FileUploader.vue:38`：`<script setup lang="ts">` 从第 38 行开始。
- `FileUploader.vue:57`：`const uploadQueue: File[] = []` 位于 `<script setup>` 内部。

**结论**：Vue 3 的 `<script setup>` 在每次组件实例化时创建新的闭包作用域。`uploadQueue` 是实例局部变量，不会跨实例共享。审计将其标记为"模块级"是错误的——它不在 `<script>` 标签外的模块顶层。前端 lifecycle 测试第 4 项「uploader state is instance-local」已用源码作用域分析锁定了这一点。

---

### 6.1.3 模块级 Map/Set 跨实例共享 — ❌ 不适用（审计误报）

**审计位置**：`views/RecognizeView.vue:396-398`

**验证**：
- `RecognizeView.vue:260`：`<script setup lang="ts">` 从第 260 行开始。
- `RecognizeView.vue:396`：`const batchRenderInFlight = new Map<string, Promise<void>>()`
- `RecognizeView.vue:397`：`const ownedTaskIds = new Set<string>()`
- `RecognizeView.vue:398`：`const resumingTaskIds = new Set<string>()`

**结论**：三个集合均在 `<script setup>` 作用域内，是实例局部状态。每次组件挂载时重新创建，卸载时随实例 GC。审计的"模块级"描述不成立。前端 lifecycle 测试第 4 项同样覆盖了这一点。

---

### 6.1.4 `setTimeout` 未在 unmount 时清理 — ✅ 已修复

**审计位置**：`components/AiAssistant.vue:312, 324`

**修复内容**：
- `AiAssistant.vue:208`：import 中新增 `onUnmounted`。
- `AiAssistant.vue`：`animationTimer` 变量声明为 `let animationTimer: ReturnType<typeof setTimeout> | null = null`。
- 设置 timer 时先检查并清除旧 timer：`if (animationTimer !== null) clearTimeout(animationTimer)`。
- `AiAssistant.vue:413-418`：`onUnmounted(() => { if (animationTimer !== null) { clearTimeout(animationTimer); animationTimer = null } window.removeEventListener('resize', handleWindowResize) })`。

**验证结论**：动画定时器在替换和卸载两个场景都正确清理。`resize` 事件监听器也在 `onUnmounted` 中移除，防止了组件卸载后仍触发回调的内存泄漏。

---

### 6.1.5 `LogPanel` 自动滚动失效 — ✅ 已修复

**审计位置**：`components/LogPanel.vue:31`

**修复内容**：
- `LogPanel.vue:2`：模板根元素绑定 `ref="logContainer"`，使 `logContainer` ref 不再为 `undefined`。
- `LogPanel.vue:29`：`const logContainer = ref<HTMLDivElement>()`。
- `LogPanel.vue:31-38`：`watch(() => logStore.entries.length, async () => { await nextTick(); if (logContainer.value) { logContainer.value.scrollTop = logContainer.value.scrollHeight } })`。

**验证结论**：`ref="logContainer"` 在模板中正确绑定，`watch` 监听 `entries.length` 变化后通过 `nextTick` 确保 DOM 更新完成，再设置 `scrollTop = scrollHeight` 实现自动滚动到底部。

---

### 6.1.6 `LogPanel` 使用数组索引作为 `:key` — ✅ 已修复

**审计位置**：`components/LogPanel.vue:4`

**修复内容**：
- `LogPanel.vue:5`：`:key="entry.id"` 使用日志条目的唯一 ID 而非数组索引。
- `stores/log.ts:15, 20-22`：`nextLogId` 从 1 开始递增，每条日志 push 时分配 `id: nextLogId`，然后 `nextLogId += 1`。

**验证结论**：每条日志条目拥有全局唯一的单调递增 ID，即使 `splice` 移除旧条目后，剩余条目的 ID 仍保持不变。Vue 的 `v-for` 使用 `:key="entry.id"` 可正确复用 DOM 节点，不会因数组索引偏移导致错误重渲染。

---

### 6.1.7 `assistant.ts` 直接修改响应式对象属性 — ✅ 已修复

**审计位置**：`stores/assistant.ts:108`

**修复内容**：
- `assistant.ts` 的 `onDelta` 回调中：
  ```ts
  const targetIndex = messages.value.findIndex(
    (item) => item.id === tempAssistantId,
  )
  if (targetIndex >= 0) {
    const target = messages.value[targetIndex]
    messages.value[targetIndex] = {
      ...target,
      content: target.content + content,
    }
  }
  ```
- 用整体替换数组元素（`messages.value[targetIndex] = {...target, content: ...}`）替代了直接属性修改（`target.content += content`），确保 Vue 3 Proxy 能正确触发响应式更新。

**验证结论**：修复后的模式符合 Vue 3 响应式最佳实践——通过创建新对象并替换数组元素，使 Proxy 的 set trap 能检测到变更并触发依赖更新。`deleteSession` 也增加了 `try/catch/finally` 块，正确处理 `loading` 和 `error` 状态。

---

### 6.1.8 `JianpuEditor` 自动格式化覆盖历史文本 — ✅ 已修复

**审计位置**：`components/JianpuEditor.vue:427-439`

**修复内容**：
- 完全删除了 `watch(() => props.modelValue, ..., { immediate: true })` —— 这个 watcher 会在组件挂载和历史记录恢复时立即触发自动格式化，覆盖用户原始文本。
- 删除了与之关联的全部辅助函数：`needsFormat`、`formatMeasures`、`splitInlineComment`、`textareaState`、`restoreTextareaState`（共约 128 行代码删除）。
- 保留了用户主动输入小节线时的自动换行逻辑（通过 `@input` 事件而非 `watch` 触发）。

**额外清理**：
- `JianpuEditor.vue:384-395`：新增 `onUnmounted` 清理 `resizeObserver`、`errorBlinkTimer`、`pageFlashTimer`，防止了组件卸载后的定时器泄漏和 ResizeObserver 孤立引用。
- 删除自动格式化路径后，`splitInlineComment` 成为未使用函数；已在同一工作包内删除并重跑 lint，未留下 warning。

**验证结论**：历史记录恢复后不再被自动格式化覆盖。用户编辑输入时的换行辅助不受影响。`onUnmounted` 的清理是额外的内存泄漏修复，超出审计要求但合理。

---

### 6.1.9 `JianpuPlayer` 音量不持久化 — ✅ 已修复

**审计位置**：`components/JianpuPlayer.vue:162`

**修复内容**：
- 新增文件 `utils/playerPreferences.ts`（36 行）：
  - `PLAYER_VOLUME_KEY = 'score-trans-player-volume'`
  - `DEFAULT_PLAYER_VOLUME = 0.8`
  - `parsePlayerVolume(raw: string | null): number`：验证 `Number.isFinite` 且 `0 <= value <= 1`，否则返回默认值。
  - `loadPlayerVolume(storage?)`：从 localStorage 读取并解析，`try/catch` 保护存储不可用场景。
  - `savePlayerVolume(value, storage?)`：`Math.max(0, Math.min(1, value))` 归一化后存储，`try/catch` 保护。
- `JianpuPlayer.vue:143-145`：import `loadPlayerVolume` 和 `savePlayerVolume`。
- `JianpuPlayer.vue:172`：`const initialVolumeRatio = loadPlayerVolume()` 在组件初始化时加载持久化音量。
- `JianpuPlayer.vue:257`：`handleVolumeChange` 调用 `savePlayerVolume(value)` 持久化新音量。
- `JianpuPlayer.vue:264`：取消静音时 `savePlayerVolume(lastVolumeRatio)` 也持久化。

**验证结论**：音量在 0–1 范围内正确持久化到 localStorage。损坏的存储值（非数字、超范围）安全回退到 0.8。存储不可用（如隐私模式）时 `try/catch` 静默降级，当前会话仍保留音量。前端 lifecycle 测试第 6 项「player volume parsing clamps persistence to the supported range」覆盖了边界值解析。

---

### 6.1.10 `JianpuPlayer` MIDI 生成失败静默 — ✅ 已修复

**审计位置**：`components/JianpuPlayer.vue:191-207`

**修复内容**：
- `JianpuPlayer.vue:163`：新增 `const loadError = ref('')` 响应式错误状态。
- `JianpuPlayer.vue:42-45`：模板中 `<span v-if="loadError" class="player-error" :title="loadError">{{ loadError }}</span>` 显示错误信息。
- `JianpuPlayer.vue:178`：`loadGeneration` 计数器防止竞态条件（旧加载完成后覆盖新加载的状态）。
- `JianpuPlayer.vue:229-235`：`reportMidiError(error, generation)` 函数：
  - 检查 `generation !== loadGeneration` 时跳过（防止旧请求的错误覆盖当前状态）。
  - 调用 `player.unload()` 卸载过时音频。
  - 设置 `loadError.value = 'MIDI 加载失败：${detail}'`。
  - 调用 `message.error(loadError.value)` 通过 Naive UI `useMessage()` 弹出通知。
- 三条加载路径（直接 MIDI、简谱生成、MusicXML 生成）均用 `try/catch` 包裹并调用 `reportMidiError`。
- `JianpuPlayer.vue:185`：每次新加载前 `loadError.value = ''` 清除旧错误。

**验证结论**：三种 MIDI 加载路径的失败都会被捕获并展示给用户。`loadGeneration` 机制正确处理了快速切换音源时的竞态。前端 lifecycle 测试第 7 项「MIDI generation failures unload stale audio and notify the user」覆盖了错误报告逻辑。

---

## 3. 关联修复验证

以下修改虽不在审计 6.1 的 10 项清单中，但在同一工作包内完成，与响应性和内存泄漏直接相关：

### 3.1 OriginalPreview.vue — Blob URL + AbortController

- `OriginalPreview.vue:91`：import `fetchFileBlob` 替代了直接使用 `getFileURL()`。
- `OriginalPreview.vue:166-186`：`watch(() => props.fileId, async (fileId, _previous, onCleanup) => {...})` 使用 Vue 3.5 的 `onCleanup` 回调：
  - 创建 `AbortController`，`onCleanup` 中 `controller.abort()` 取消未完成的 fetch。
  - 加载新文件前 `URL.revokeObjectURL(fileUrl.value)` 回收旧 blob URL。
- `OriginalPreview.vue:189-210`：overlay 图片使用相同的 `onCleanup` + `AbortController` 模式。
- `OriginalPreview.vue:212-233`：sourceMap JSON 使用相同模式。
- `OriginalPreview.vue:236-240`：`onUnmounted` 中 `zp.unbind()` + 回收两个 blob URL。

**结论**：三处 watch 均使用 `onCleanup` 正确取消请求和回收 URL，`onUnmounted` 作为最终保障。无内存泄漏。

### 3.2 SvgPreview.vue — 安全 DOM 挂载

- `SvgPreview.vue:91`：import `sanitizeSvg` from `../utils/svgSanitizer`（替代了内联的字符串级 sanitizer）。
- `SvgPreview.vue:373`：`const safeSvg = sanitizeSvg(text)` 返回解析后的 Document。
- `SvgPreview.vue:381-382`：`document.importNode(safeSvg, true)` + `svgHostRef.value?.replaceChildren(mountedSvg)` 替代了 `v-html`，安全挂载 SVG DOM。
- `SvgPreview.vue:539-544`：`onUnmounted` 移除三个 `window` 事件监听器（`mousemove`、`mouseup`、`keydown`）并 `zp.unbind()`。

**结论**：不再使用 `v-html` 挂载 SVG，改用 DOM API 安全注入。事件监听器在卸载时全部移除。

### 3.3 export.ts — Blob URL 生命周期

- `export.ts:47-67`：`svgToPngBlob(svgFileId, scale)` 通过 `loadFileImage(svgFileId)` 获取 blob URL，`finally` 块中 `URL.revokeObjectURL(objectUrl)` 回收。
- `export.ts:69-92`：`svgToJpegBlob` 同理。
- `export.ts:94-115`：`loadFileImage` 内部使用 `fetchFileBlob`，加载失败时也 `URL.revokeObjectURL(objectUrl)`。
- `export.ts:117-124`：`downloadBlob` 创建临时 URL，`click()` 后立即 `URL.revokeObjectURL(url)`。

**结论**：所有 blob URL 都在 `finally` 块或使用后立即回收，无 URL 泄漏。

### 3.4 ConvertView.vue — 安全下载

- `ConvertView.vue:1388-1392`：`downloadFile(fileId, filename)` 通过 `fetchFileBlob` 获取 blob，再调用 `downloadBlob`（内部自动回收 URL）。
- `ExportSource` 类型已移除 `{ url: string }` 成员，不再在类型层面暴露内部 URL。

**结论**：下载路径不再直接暴露文件 URL，通过 blob 中转并在使用后回收。

### 3.5 RecognizeView.vue — 预览 URL 管理

- `RecognizeView.vue:429`：`const previewUrls = ref<Record<string, string>>({})`。
- `RecognizeView.vue:431-433`：`previewUrl(fileId)` 返回已缓存的 blob URL 或空字符串。
- `RecognizeView.vue:435-440`：`revokePreviewUrls()` 遍历所有 URL 调用 `URL.revokeObjectURL` 并清空记录。
- `RecognizeView.vue:442-476`：`watch` 使用 `onCleanup` + `AbortController` 模式，加载前先 `revokePreviewUrls()`，`Promise.all` 并行获取多个文件 blob。
- `RecognizeView.vue:478`：`onUnmounted(revokePreviewUrls)` 作为最终保障。

**结论**：预览 URL 生命周期管理完整——watch cleanup 回收旧 URL，`onUnmounted` 回收残留 URL，无泄漏。

### 3.6 assistant.ts — deleteSession 错误处理

- `assistant.ts`：`deleteSession` 现在包裹在 `try/catch/finally` 中：
  - `try`：执行 API 调用和本地状态更新。
  - `catch`：设置 `error.value`。
  - `finally`：重置 `loading.value = false`。
- `assistant.ts`：`onSession` 回调用 `messages.value.map(...)` 创建新数组替代原地修改。

**结论**：`deleteSession` 不再有未捕获的 Promise 拒绝，`loading` 状态在所有路径下正确重置。

---

## 4. 新问题评估

### 4.1 已发现的新问题

**无。** 6.1 工作包未引入任何新的开放问题。

### 4.2 已处理的中间产物

- `JianpuEditor.vue` 删除自动格式化路径后，`splitInlineComment` 成为未使用函数。已在同一工作包内删除并重跑 lint，ESLint 0 error / 1 warning（仅保留既有的 `AiAssistant.vue` `vue/no-v-html` warning），未形成开放缺陷。

### 4.3 已知限制

- `test-svg-sanitizer-electron.cjs` 测试在纯 Node.js 环境下运行失败（`Cannot read properties of undefined (reading 'disableHardwareAcceleration')`），因为它需要 Electron 运行时。这是预期行为——该测试设计为在 Electron 环境中运行，不影响 CI 门禁。
- `AiAssistant.vue:152` 仍使用 `v-html` 渲染 AI 回复的 Markdown。这是审计第 4.4 节已确认为"不成立"的条目（AI 回复经过 `renderAssistantMessage` 处理，输入来自后端 AI 服务而非用户直接输入，且 `vue/no-v-html` warning 是既有且被接受的）。
- `RecognizeView.vue:442` 的 `watch` 使用 `{ immediate: true }`，在组件首次挂载时立即触发 fetch。若组件在 fetch 完成前卸载，`onCleanup` 会 `controller.abort()` 中止请求，`active = false` 标志阻止后续状态更新。`onUnmounted(revokePreviewUrls)` 确保已创建的 URL 被回收。该模式是安全的。

---

## 5. 测试质量评估

### 5.1 新增测试覆盖

| 测试文件 | 测试数 | 覆盖范围 |
|---------|--------|---------|
| `scripts/test-frontend-lifecycle.mjs` | 7 | 日志上限、稳定 key、uploader 实例作用域、assistant 响应式替换、editor 无 immediate watch、player 音量持久化、player 错误报告 |
| `scripts/test-jianpu-page-sections.mjs`（新增） | +2 | `deleteSession` 顺序、authenticated fetch |
| `scripts/test-svg-sanitizer.mjs` | 3 | SVG 净化 + DOM 挂载（不使用 v-html） |
| `scripts/test-backend-lifecycle.mjs` | 4 | 后端子进程终止 |
| `scripts/test-main-file-security.mjs` | 6 | 路径安全、符号链接拒绝 |
| `scripts/test-storage-migration.mjs` | 2 | 存储迁移安全 |
| 后端新增测试 | +11 | 后端测试从 411 增至 422 |

### 5.2 测试质量评价

- **lifecycle 测试**：7 个子测试精确覆盖了 6.1 的 10 项审计发现中的 7 项（日志上限+key 合并为 1 项、uploader 作用域、assistant 响应式、editor watch、player 音量、player 错误）。两个"不适用"项（FileUploader、RecognizeView 作用域）通过同一测试的源码作用域分析覆盖。
- **红灯测试策略**：根据 `AUDIT_REMEDIATION_STATUS.md` 记录，6.1 修复前先运行旧实现的红灯测试（6 failed、1 passed），确认问题可复现后再修复，修复后 7 passed。这是良好的 TDD 实践。
- **测试粒度**：测试使用纯 Node.js `node:test` 框架，不依赖浏览器/DOM 环境，通过源码静态分析和 mock 对象验证逻辑正确性。对于需要真实 DOM 的场景（如 SVG sanitizer），使用 JSDOM 或 Electron 运行时。

---

## 6. 结论

### 6.1 验证结论

第 6.1 节「Vue 响应性与内存泄漏」的 10 项审计发现已全部验证：

| 结果 | 数量 | 明细 |
|------|------|------|
| ✅ 已修复 | 8 | 6.1.1, 6.1.4, 6.1.5, 6.1.6, 6.1.7, 6.1.8, 6.1.9, 6.1.10 |
| ❌ 不适用（审计误报） | 2 | 6.1.2 (FileUploader), 6.1.3 (RecognizeView) |

**修复正确率：100%**（8/8 修复项全部正确；2 项不适用项经源码作用域分析确认审计误报）。

### 6.2 额外修复

工作包还包含以下超出审计要求的关联修复，均验证正确：
- OriginalPreview.vue 的 blob URL + AbortController 生命周期管理
- SvgPreview.vue 的安全 DOM 挂载（替代 v-html）+ 事件监听器清理
- export.ts 的 blob URL 回收（finally 块）
- ConvertView.vue 的安全下载路径
- RecognizeView.vue 的预览 URL 管理
- JianpuEditor.vue 的 ResizeObserver + 定时器清理
- assistant.ts 的 deleteSession 错误处理

### 6.3 新问题

**未发现任何由 6.1 修复引入的新问题。**

### 6.4 测试基线变化

| 指标 | 修复前 | 修复后 | 变化 |
|------|--------|--------|------|
| 后端测试 | 411 passed | 422 passed | +11 |
| 前端 lifecycle | — | 7 passed | 新增 |
| 前端 page-sections | 32 passed | 34 passed | +2 |
| ESLint | 0 error / 1 warning | 0 error / 1 warning | 不变 |
| TypeScript | 通过 | 通过 | 不变 |
| Ruff | 通过 | 通过 | 不变 |

---

*验证完成。第 6.1 节全部 10 项审计发现已逐项验证，修复质量优秀，未引入新问题。*
