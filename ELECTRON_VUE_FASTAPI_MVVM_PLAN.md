# Electron + Vue3 + TS + Naive UI + FastAPI 全量实施文档 v1

> 约束：不改动现有代码，仅提供新增方案与实施说明。

---

## 0. 目标与原则

### 目标
- 桌面端：Electron + Vue3 + TypeScript + Naive UI
- 后端：FastAPI
- 前后端均采用 MVVM
- **保持现有目录结构不动**
- 不删除、不修改现有模块

### 原则
- 仅新增，不重构
- 复用已有 `domain/services/use_cases`
- 原有 Qt UI/CLI 保留
- 新前端完全使用 TS/Vue

---

## 1. 总体架构

```
┌────────────────────────────┐
│         Electron Main        │
│  启动/管理 FastAPI 进程       │
└───────────┬────────────────┘
            │ HTTP (localhost)
            ▼
┌────────────────────────────┐
│       FastAPI Backend        │  (MVVM)
│  View: routers               │
│  ViewModel: Pydantic DTO     │
│  Model: domain/use_cases     │
└───────────┬────────────────┘
            │ REST API
            ▼
┌────────────────────────────┐
│       Vue3 + TS Frontend     │  (MVVM)
│  View: Pages/Components      │
│  ViewModel: composables      │
│  Model: api/types/services   │
└────────────────────────────┘
```

---

## 2. 目录结构设计（保持原结构）

### 现有结构（保持不动）
```
src/score_trans/
  domain/
  services/
  use_cases/
  viewmodels/   # Qt ViewModel（保留）
  views/        # Qt View（保留）
  cli/
```

### 新增（建议）
```
src/score_trans/
  api/
    app.py
    views/
      convert.py
      recognize.py
      render.py
      pipeline.py
    viewmodels/
      schemas.py
    dependencies.py
```

### Electron + Vue 前端
```
desktop/
  src/
    main/          # Electron 主进程
    preload/       # Preload (可选)
    renderer/
      views/       # Vue 页面 = View
      viewmodels/  # Vue composables = ViewModel
      models/      # types / interfaces = Model
      services/    # API 请求封装
```

---

## 3. 后端 MVVM 设计（FastAPI）

### 3.1 MVVM 映射
| 层级 | 责任 | 位置 |
|---|---|---|
| View | FastAPI Router | `api/views/` |
| ViewModel | 请求/响应 DTO | `api/viewmodels/` |
| Model | use_cases + domain | `use_cases/` + `domain/` |

### 3.2 API 路由规划（基于现有 UseCase）

| 功能 | UseCase | API |
|---|---|---|
| MusicXML → 简谱 | ConvertMusicXmlToJianpuUseCase | POST `/convert/musicxml-to-jianpu` |
| 简谱 → MusicXML | ConvertJianpuToMusicXmlUseCase | POST `/convert/jianpu-to-musicxml` |
| 识别图片/PDF | RecognizeScoreUseCase | POST `/recognize` |
| 完整流水线 | FullPipelineUseCase | POST `/pipeline` |
| 渲染简谱SVG | RenderMusicXmlJianpuUseCase | POST `/render/jianpu-svg` |

### 3.3 后端 ViewModel（Pydantic DTO）示例

`schemas.py`
```py
class ConvertMusicXmlRequest(BaseModel):
    musicxml_path: str
    target_key: str = "C"
    start_measure_number: int | None = None

class ConvertMusicXmlResponse(BaseModel):
    jianpu_text: str
```

### 3.4 后端 View（Router）示例

`convert.py`
```py
@router.post("/convert/musicxml-to-jianpu")
def convert(req: ConvertMusicXmlRequest):
    jianpu = ConvertMusicXmlToJianpuUseCase().execute(
        req.musicxml_path,
        target_key=req.target_key,
        start_measure_number=req.start_measure_number
    )
    return ConvertMusicXmlResponse(jianpu_text=jianpu)
```

---

## 4. 前端 MVVM 设计（Vue3）

### 4.1 MVVM 映射

| 层级 | 责任 | 位置 |
|---|---|---|
| View | Vue页面/组件 | `renderer/views/` |
| ViewModel | composable | `renderer/viewmodels/` |
| Model | DTO / API service | `renderer/models/`, `renderer/services/` |

### 4.2 前端 ViewModel 示例

`viewmodels/useConvert.ts`
```ts
export function useConvert() {
  const loading = ref(false)
  const result = ref('')

  async function convertMusicXml(path: string) {
    loading.value = true
    const res = await api.post('/convert/musicxml-to-jianpu', { musicxml_path: path })
    result.value = res.jianpu_text
    loading.value = false
  }

  return { loading, result, convertMusicXml }
}
```

### 4.3 View 示例

`views/ConvertView.vue`
```vue
<template>
  <n-input v-model:value="path" />
  <n-button @click="convert">转换</n-button>
  <pre>{{ result }}</pre>
</template>

<script setup lang="ts">
const { result, convertMusicXml } = useConvert()
</script>
```

---

## 5. Electron 与 FastAPI 集成方案

### 5.1 主进程流程
- 开发时：spawn `python -m uvicorn ...`
- 生产时：spawn `backend.exe`
- 退出时 kill 后端

### 5.2 生产环境路径
```
process.resourcesPath/backend/backend.exe
```

---

## 6. 打包与发布（Windows）

### 6.1 后端打包
```
pyinstaller -F backend/app/main.py -n backend
```

### 6.2 Electron 打包
- electron-builder
- extraResources 把 backend.exe 放进 app

---

## 7. 实施步骤清单（逐条）

### 第一步：搭建前端工程
1. 创建 electron-vite Vue3 + TS 项目
2. 安装 Naive UI
3. 初始化 MVVM 目录

### 第二步：新增 FastAPI API 层
1. 新增 `src/score_trans/api/`
2. 添加 app.py
3. 添加 router/viewmodel
4. 注册 router

### 第三步：前端调用后端
1. 前端 services 封装 fetch
2. viewmodels 统一调用
3. views 只绑定状态

### 第四步：Electron 运行 FastAPI
1. dev 环境 spawn uvicorn
2. prod 环境 spawn backend.exe
3. before-quit kill

### 第五步：打包
1. PyInstaller 打后端
2. electron-builder 打前端
3. 组合成安装包

---

## 8. 关键注意事项

- CORS 必须开启
- 端口冲突要处理
- 生产环境不能用 uvicorn
- Electron 退出时必须 kill backend
- Renderer 禁止直接用 Node API

---

## 9. 最终交付物

```
桌面应用.exe
  ├─ Vue3 + Naive UI 界面
  ├─ FastAPI 后端引擎
  ├─ 复用既有 use_cases 功能
```
