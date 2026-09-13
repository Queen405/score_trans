# AGENTS.md — Desktop (Electron + Vue 3)

## Stack

- **Electron 33** + **Vue 3.5** (Composition API, `<script setup>`) + **TypeScript**
- **Pinia** (Composition API style `defineStore`) + **Naive UI** + **@vicons/ionicons5**
- **electron-vite** 构建，**electron-builder** 打包（Windows NSIS）
- **pnpm** 包管理

## Directory Structure

```
desktop/src/
  main/               Electron 主进程
    index.ts           窗口创建、IPC handler、app 生命周期
    backend.ts         BackendProcess：启动 FastAPI 后端（开发用 uvicorn，生产用 exe）
  preload/
    index.ts           contextBridge 暴露 window.api（最小化/最大化/关闭、获取后端 URL、选择目录）
  renderer/src/
    main.ts            createApp + Pinia（无 Naive UI 全局注册，组件按需 import）
    App.vue            根组件：自定义标题栏、侧边栏导航、日志抽屉
    api/               按模块封装的 fetch 客户端（client.ts, convert.ts, pipeline.ts, render.ts, export.ts, ai.ts, history.ts, settings.ts）
    stores/            Pinia stores（workspace.ts, settings.ts, assistant.ts, log.ts）
    views/             页面组件（RecognizeView, ConvertView, SyntaxView, SettingsView）
    components/        通用组件（FileUploader, JianpuEditor, PublicationPreview, OriginalPreview, LogPanel, JianpuPlayer, SyntaxDiagnosticPanel）
    models/openapi.ts  从 FastAPI OpenAPI 自动生成的原始类型（不要手工编辑）
    models/contracts.ts 后端契约的语义化类型别名
    models/types.ts    重导出后端契约，并保留少量纯前端类型
    composables/       可复用组合函数
    utils/             工具函数（ocrText.ts 等）
```

## Key Patterns

### Naive UI 组件导入
**Naive UI 不做全局注册**，每个 `.vue` 文件按需 import：
```ts
import { NButton, NIcon, NCode, NInputNumber, useMessage } from 'naive-ui'
```
添加新页面时，务必在 `<script setup>` 中 import 所有用到的 Naive UI 组件。

### API 调用
- 统一通过 `api/` 目录下的封装函数，不要直接 `fetch`
- `api/client.ts` 提供 `apiFetch<T>()`、`authenticatedFetch()`、`fetchFileBlob()`、`fileExists()`、`uploadFile()`
- `getFileURL()` 只构造内部地址，不能直接交给 `<img>`、`<iframe>`、`Image` 或原生 `fetch`；媒体必须先通过 `fetchFileBlob()` 获取，再使用可回收的 object URL
- 异步 API wrapper 返回 `ApiResult<T>`（`{ data, error }`），wrapper 本身不得抛异常
- 页面和 Store 可在现有 `try/catch` 工作流边界使用 `requireData()` 解包，再通过 Naive UI `useMessage()` 展示错误
- Electron 从 `window.api.getBackendConnection()` 获取进程内 URL/token；独立开发浏览器使用匹配的 `VITE_BACKEND_URL` / `VITE_BACKEND_TOKEN`
- 修改 Pydantic 请求/响应模型后运行 `pnpm generate:api-types`；CI 使用 `pnpm check:api-types` 检测契约漂移

### Pinia Store 约定
- `workspace.ts` 是核心 Score Workspace 状态：管理多页输入（`pages[]`, `currentPageIndex`），当前页数据同步到顶层 refs（`inputFileId`, `jianpuText` 等）
- `settings.ts` 管理全局配置，`load()` 从后端读取，`save()` 写回
- `log.ts` 收集运行日志，`errorCount` 计算属性用于 badge 显示

### 页面导航
App.vue 用 `activeTab` + `v-show` 切换三个主视图（recognize / convert / settings），不做路由。

### 文件存在检测
`fileExists(fileId)` 发 HEAD 请求到 `GET /files/{id}`，后端返回 200/404。

### IPC 通信
preload 暴露 `window.api`，主进程通过 `ipcMain.handle` 处理。当前只有窗口控制和目录选择。

## Adding a New View

1. 在 `views/` 创建 `XxxView.vue`，使用 `<script setup lang="ts">`
2. 在 `views/` 中按需 import Naive UI 组件（不要依赖全局注册）
3. 在 `App.vue` 的 `navItems` 数组中添加导航项，`activeTab` 中添加新 key
4. 如果需要后端 API，在 `api/` 下添加封装函数
5. 如果需要持久状态，在 `stores/` 下创建 Pinia store

## Common Pitfalls

- **`n-input-number` 未注册**：ConvertView 中用到 `NInputNumber` 但忘记 import，会导致组件不渲染且控制台 warn。添加任何 Naive UI 组件都要确认 import。
- **CORS**：开发模式前端跑在 `localhost:5173`，后端在 `127.0.0.1:19200/19201`。后端已配置 CORS，但 HEAD 请求返回 405 时响应不带 CORS 头会触发浏览器 block。
- **`fileExists` 竞态**：`UploadService` 每次请求新建实例，`index.json` 并发写入可能导致索引丢失，`fileExists` 返回 false。已在后端修复为原子写入。
- **窗口控制**：`frame: false` 自定义标题栏，`window.api.minimizeWindow()` 等通过 IPC 调用。
- **主题**：跟随系统 `prefers-color-scheme`，通过 `prefersDark` ref 切换 `theme-dark` / `theme-light` class。

## Build & Run

```bash
# 开发（需先启动后端）
cd desktop
pnpm dev

# 构建
pnpm build

# Lint
pnpm lint

# 类型检查
pnpm typecheck

# 前端纯函数/状态工具测试
pnpm test:utils

# 生成或校验后端 API 契约
pnpm generate:api-types
pnpm check:api-types
```

> **Note**: 当前已有基于 Node `node:test` 的工具与状态逻辑测试；组件级 Vitest 和 Playwright E2E 尚未配置。

## Release / 发版流程

发布流程见根目录 `RELEASE.md`，打包细节见 `docs/packaging.md`。

- 新客户端从 GitHub Release 的 `releases/latest/download/latest.json` 获取更新信息。
- `desktop/latest.json` 是发布输入，必须与 `package.json` 保持 `x.y.z` 版本一致。
- `tools/release.py` 校验 tag、版本、两平台全部安装包，上传草稿后再公开 Release。
- 工作分支中的 manifest 不用于新客户端的更新通知，避免提前公布未完成构建。
- 可用 `SCORE_TRANS_UPDATE_MANIFEST_URL` 配置镜像或本地测试地址。
- 更新检查继续使用主进程异步 IPC；连接失败不阻塞应用，不引入同步网络调用。
- 历史版本客户端升级前仍读取旧 jsDelivr 地址。
