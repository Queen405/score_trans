# Electron + Vue3 + TS + Naive UI + FastAPI 全量实施文档 v2

> 约束：不改动现有代码，仅提供新增方案与实施说明。

---

## 0. 目标与原则

### 目标
- 桌面端：Electron + Vue3 + TypeScript + Naive UI
- 后端：FastAPI
- 前后端均遵循 MVVM
- **保持现有目录结构不动**
- 不删除、不修改现有模块

### 原则
- 仅新增，不重构
- 复用已有 `domain/` + `services/` + `use_cases/`
- 原有 Qt UI（`views/`、`viewmodels/`）和 CLI（`cli/`）保留不动
- 新前端完全使用 TS/Vue
- API 层充当适配器：将 HTTP 文件上传翻译为现有 use_cases 期望的本地路径

---

## 1. 总体架构

```
┌──────────────────────────────────┐
│          Electron Main            │
│  启动 / 管理 / 监控 FastAPI 进程   │
│  窗口管理、系统托盘、原生对话框     │
└───────────┬──────────────────────┘
            │ HTTP (localhost:{port})
            ▼
┌──────────────────────────────────┐
│        FastAPI Backend            │
│  Router (View)                    │  ← 新增，HTTP 边界
│  Schema (DTO)                     │  ← 新增，请求/响应结构
│  Use Cases (ViewModel 编排)       │  ← 复用，不改动
│  Domain + Services (Model)        │  ← 复用，不改动
└───────────┬──────────────────────┘
            │ REST API + SSE
            ▼
┌──────────────────────────────────┐
│       Vue3 + TS Frontend          │
│  Pages / Components (View)        │
│  Composables (局部 ViewModel)     │
│  Pinia Stores (全局 ViewModel)    │
│  API Services (Model)             │
└──────────────────────────────────┘
```

### 各层职责对比

| 层级 | 后端 (FastAPI) | 前端 (Vue3) | 现有 (PySide6) |
|---|---|---|---|
| **View** | `api/routers/` — HTTP 路由 | `.vue` 页面/组件 | `views/main_window.py` |
| **ViewModel** | `use_cases/` — 业务编排（复用） | Pinia stores + composables | `viewmodels/main_window_vm.py` |
| **Model** | `domain/` + `services/`（复用） | `api/` 封装 + TypeScript 类型 | 同左 |

> **关键说明**：Pydantic Schema 是 DTO（数据传输对象），负责请求验证和响应序列化，不承担 ViewModel 的编排职责。现有 `use_cases/` 已经在做 ViewModel 的工作——接收参数、调用 services、编排流程、返回结果——直接复用即可。

---

## 2. 目录结构设计

### 现有结构（保持不动）

```
src/score_trans/
  domain/           # 纯领域模型 + MusicXML/简谱转换
  services/         # 外部工具、文件、渲染、OCR、设置
  use_cases/        # 用户动作：识别、转换、渲染、导出、流水线
  viewmodels/       # Qt ViewModel（保留，不影响新方案）
  views/            # PySide6 View（保留，不影响新方案）
  cli/              # 命令行入口（保留）
```

### 新增后端 API 层

```
src/score_trans/
  api/
    __init__.py
    app.py              # FastAPI 应用工厂（create_app）
    dependencies.py     # 依赖注入：构造 use_case 实例
    routers/
      __init__.py
      convert.py        # POST /convert/musicxml-to-jianpu, /convert/jianpu-to-musicxml
      recognize.py      # POST /recognize
      render.py         # POST /render/jianpu-svg, /render/preserving-layout
      pipeline.py       # POST /pipeline
      files.py          # GET /files/{file_id}, DELETE /files/{file_id}
      health.py         # GET /health
    schemas.py          # Pydantic 请求/响应模型（DTO）
    tasks.py            # 后台任务管理器（task_id → status → result）
    uploads.py          # 上传文件管理（保存、file_id 映射、清理）
```

### 新增 Electron + Vue 前端

```
desktop/
  package.json
  electron.vite.config.ts
  src/
    main/                   # Electron 主进程
      index.ts              # 入口：创建窗口、管理后端进程
      backend.ts            # BackendProcess 类（启动/停止/健康检查）
      ipc.ts                # IPC handlers（可选，原生对话框等）
    preload/
      index.ts              # contextBridge 暴露安全 API
    renderer/
      src/
        main.ts             # Vue 应用入口
        App.vue
        api/                # Model 层：HTTP 请求封装
          client.ts         # fetch/axios 封装，baseURL、错误处理
          convert.ts        # 转换相关 API
          recognize.ts      # 识别相关 API
          render.ts         # 渲染相关 API
          pipeline.ts       # 流水线 API
        models/             # TypeScript 类型定义
          types.ts          # DTO 类型（与后端 schemas 对齐）
        stores/             # 全局 ViewModel：Pinia stores
          task.ts           # useTaskStore（musicxml/jianpu/busy 状态）
          settings.ts       # useSettingsStore（工具路径配置）
          log.ts            # useLogStore（操作日志 + 错误通知）
        composables/        # 局部 ViewModel：可复用逻辑
          useSSE.ts         # SSE 进度监听
          useFileUpload.ts  # 文件上传 + 拖拽
        views/              # View 层：页面
          RecognizeView.vue     # 图片/PDF 识别
          ConvertView.vue       # 简谱互转
          ExportView.vue        # 导出
          SettingsView.vue      # 设置页（可并入主页面）
        components/         # 通用组件
          LogPanel.vue          # 日志面板
          SvgPreview.vue       # SVG 渲染预览
          FileUploader.vue     # 文件上传组件
          JianpuEditor.vue     # 简谱文本编辑器
```

---

## 3. 后端 MVVM 设计（FastAPI）

### 3.1 MVVM 映射（修正版）

| 层级 | 职任 | 位置 | 说明 |
|---|---|---|---|
| **View** | HTTP 边界，解析请求、返回响应 | `api/routers/` | 只做参数提取、调用 use_case、格式化响应 |
| **ViewModel** | 业务编排，状态管理 | `use_cases/` | **已有，直接复用，不改动** |
| **Model** | 纯数据模型 + 领域逻辑 | `domain/` + `services/` | **已有，直接复用，不改动** |
| **DTO** | 请求验证 + 响应序列化 | `api/schemas.py` | 新增，薄层，不含业务逻辑 |

### 3.2 依赖注入（`dependencies.py`）

Router 不自己构造 use_case 实例，通过 FastAPI `Depends` 注入：

```python
from ..use_cases import (
    ConvertMusicXmlToJianpuUseCase,
    ConvertJianpuToMusicXmlUseCase,
    RecognizeScoreUseCase,
    RenderMusicXmlJianpuUseCase,
    RenderJianpuTextUseCase,
    FullPipelineUseCase,
    ExportScoreUseCase,
)
from ..services.settings import ToolConfig

def get_config() -> ToolConfig:
    return ToolConfig.from_env()

def get_convert_to_jianpu() -> ConvertMusicXmlToJianpuUseCase:
    return ConvertMusicXmlToJianpuUseCase()

def get_convert_to_musicxml() -> ConvertJianpuToMusicXmlUseCase:
    return ConvertJianpuToMusicXmlUseCase()

def get_recognize() -> RecognizeScoreUseCase:
    return RecognizeScoreUseCase()

def get_render_jianpu() -> RenderMusicXmlJianpuUseCase:
    return RenderMusicXmlJianpuUseCase()

def get_render_text() -> RenderJianpuTextUseCase:
    return RenderJianpuTextUseCase()

def get_pipeline() -> FullPipelineUseCase:
    return FullPipelineUseCase()

def get_export() -> ExportScoreUseCase:
    return ExportScoreUseCase()
```

> **为什么不用单例？** 现有 use_cases 都是无状态的（每次 `execute` 传入完整参数），不需要全局单例。未来如需共享状态（如缓存），可在 `dependencies.py` 中切换为单例模式，Router 无需改动。

---

## 4. 文件传输设计

现有 use_cases 全部基于本地文件路径（`Path`），HTTP API 需要一个适配层。

### 4.1 上传机制

```python
# api/uploads.py
import uuid, shutil
from pathlib import Path
from ..services.settings import ToolConfig

class UploadManager:
    def __init__(self, config: ToolConfig | None = None):
        self.config = config or ToolConfig.from_env()
        self.base_dir = self.config.work_dir / "uploads"
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._files: dict[str, Path] = {}   # file_id → 本地路径

    def save(self, upload_file: UploadFile) -> str:
        """保存上传文件，返回 file_id。"""
        file_id = uuid.uuid4().hex[:12]
        file_dir = self.base_dir / file_id
        file_dir.mkdir(parents=True, exist_ok=True)
        target = file_dir / upload_file.filename
        with target.open("wb") as f:
            shutil.copyfileobj(upload_file.file, f)
        self._files[file_id] = target
        return file_id

    def get_path(self, file_id: str) -> Path | None:
        """根据 file_id 返回本地路径（use_case 需要的格式）。"""
        return self._files.get(file_id)

    def cleanup(self, file_id: str) -> None:
        path = self._files.pop(file_id, None)
        if path and path.parent.parent == self.base_dir:
            shutil.rmtree(path.parent, ignore_errors=True)

    def cleanup_all(self) -> None:
        for file_id in list(self._files):
            self.cleanup(file_id)
```

### 4.2 Router 中的使用模式

```python
# api/routers/recognize.py
from fastapi import APIRouter, Depends, UploadFile, File
from ..dependencies import get_recognize, get_config, get_upload_manager
from ..schemas import RecognizeResponse
from ...use_cases import RecognizeScoreUseCase
from ...services.settings import ToolConfig
from ..uploads import UploadManager

router = APIRouter(prefix="/recognize", tags=["recognize"])

@router.post("", response_model=RecognizeResponse)
async def recognize(
    file: UploadFile = File(...),
    target_key: str = "C",
    start_measure_number: int | None = None,
    recognize_uc: RecognizeScoreUseCase = Depends(get_recognize),
    config: ToolConfig = Depends(get_config),
    uploads: UploadManager = Depends(get_upload_manager),
):
    # 1. 保存上传文件，拿到本地路径
    file_id = uploads.save(file)
    input_path = uploads.get_path(file_id)

    # 2. 调用现有 use_case（不改动 use_case 代码）
    output_dir = config.work_dir / "audiveris"
    musicxml_path = recognize_uc.execute(input_path, output_dir, config)

    # 3. 将输出文件也注册到 uploads，供后续步骤引用
    musicxml_id = uploads.register(musicxml_path)

    return RecognizeResponse(
        task_id=...,
        file_id=musicxml_id,
        musicxml_file_id=musicxml_id,
    )
```

### 4.3 文件下载

```python
# api/routers/files.py
from fastapi import APIRouter
from fastapi.responses import FileResponse

router = APIRouter(prefix="/files", tags=["files"])

@router.get("/{file_id}")
async def download_file(file_id: str, ...):
    path = uploads.get_path(file_id)
    if not path or not path.exists():
        raise HTTPException(404, f"文件不存在：{file_id}")
    media_type = {
        ".svg": "image/svg+xml",
        ".pdf": "application/pdf",
        ".musicxml": "application/xml",
        ".mxl": "application/zip",
        ".mid": "audio/midi",
        ".txt": "text/plain; charset=utf-8",
    }.get(path.suffix.lower(), "application/octet-stream")
    return FileResponse(path, media_type=media_type, filename=path.name)

@router.delete("/{file_id}")
async def delete_file(file_id: str, ...):
    uploads.cleanup(file_id)
    return {"status": "deleted"}
```

### 4.4 流水线中的文件传递

完整流水线涉及多步骤，每步的输出是下一步的输入：

```
上传 PDF → recognize → MusicXML file_id
                              ↓
              convert_to_jianpu(用 file_id 对应的 Path)
                              ↓
              render_jianpu_svg(用同一个 musicxml file_id)
                              ↓
              返回 { musicxml_file_id, jianpu_text, svg_file_id }
```

前端可以：
- **一步到位**：`POST /pipeline`（内部编排全部步骤）
- **分步控制**：先 `POST /recognize` 拿到 `musicxml_file_id`，再 `POST /convert/...` 和 `POST /render/...`

### 4.5 临时文件清理

- 每次上传创建独立子目录 `{work_dir}/uploads/{file_id}/`
- 调用 `DELETE /files/{file_id}` 显式清理
- 启动时可选清理超过 24 小时的遗留文件
- 应用退出时由 Electron 主进程通知后端清理

---

## 5. 长任务进度反馈

Audiveris OMR 识别可能耗时数分钟，MuseScore 导出也需要时间。同步等待会阻塞 HTTP 请求。

### 5.1 方案：SSE (Server-Sent Events)

```
FastAPI (StreamingResponse)  ──text/event-stream──▶  Vue (EventSource)
```

选择 SSE 而非 WebSocket 的理由：
- 单向推送（服务端 → 客户端），不需要双向通信
- FastAPI 原生支持（`StreamingResponse` + `text/event-stream`）
- 浏览器原生 `EventSource` API，无需额外库
- 自动重连机制内建

### 5.2 后端任务管理器

```python
# api/tasks.py
import asyncio
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Generator

class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class TaskProgress:
    task_id: str
    status: TaskStatus = TaskStatus.PENDING
    stage: str = ""          # "upload" | "audiveris" | "convert" | "render" | "export"
    percent: int = 0
    message: str = ""
    result: dict[str, Any] | None = None
    error: str | None = None

class TaskManager:
    def __init__(self):
        self._tasks: dict[str, TaskProgress] = {}
        self._queues: dict[str, asyncio.Queue] = {}

    def create_task(self) -> str:
        task_id = uuid.uuid4().hex[:12]
        self._tasks[task_id] = TaskProgress(task_id=task_id)
        self._queues[task_id] = asyncio.Queue()
        return task_id

    async def update(self, task_id: str, **kwargs) -> None:
        progress = self._tasks[task_id]
        for key, value in kwargs.items():
            setattr(progress, key, value)
        await self._queues[task_id].put(progress)

    async def complete(self, task_id: str, result: dict) -> None:
        await self.update(task_id, status=TaskStatus.COMPLETED, percent=100, result=result)

    async def fail(self, task_id: str, error: str) -> None:
        await self.update(task_id, status=TaskStatus.FAILED, error=error)

    def stream(self, task_id: str) -> Generator[str, None, None]:
        """生成 SSE 事件流。"""
        queue = self._queues[task_id]
        progress = self._tasks[task_id]
        yield _sse_event(progress)  # 立即发送初始状态
        while progress.status not in (TaskStatus.COMPLETED, TaskStatus.FAILED):
            try:
                # 非阻塞等待，使用 run_in_executor 适配同步场景
                loop = asyncio.get_event_loop()
                progress = asyncio.run_coroutine_threadsafe(queue.get(), loop).result(timeout=30)
            except Exception:
                break
            yield _sse_event(progress)

def _sse_event(progress: TaskProgress) -> str:
    data = {
        "task_id": progress.task_id,
        "status": progress.status.value,
        "stage": progress.stage,
        "percent": progress.percent,
        "message": progress.message,
    }
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
```

### 5.3 Router 集成

```python
# api/routers/recognize.py（长任务版）
from fastapi.responses import StreamingResponse

@router.post("/recognize/stream")
async def recognize_stream(
    file: UploadFile = File(...),
    task_manager: TaskManager = Depends(get_task_manager),
    ...,
):
    file_id = uploads.save(file)
    task_id = task_manager.create_task()

    async def run():
        try:
            await task_manager.update(task_id, status=TaskStatus.RUNNING, stage="audiveris", percent=10)
            musicxml_path = recognize_uc.execute(input_path, output_dir, config)
            await task_manager.update(task_id, stage="convert", percent=60)
            # ... 后续步骤
            await task_manager.complete(task_id, {"musicxml_file_id": musicxml_id})
        except Exception as e:
            await task_manager.fail(task_id, str(e))

    asyncio.create_task(run())
    return StreamingResponse(
        task_manager.stream(task_id),
        media_type="text/event-stream",
    )
```

### 5.4 前端 SSE 监听

```typescript
// desktop/src/renderer/src/composables/useSSE.ts
import { ref, onUnmounted } from 'vue'

export function useSSE(url: string) {
  const status = ref<'pending' | 'running' | 'completed' | 'failed'>('pending')
  const stage = ref('')
  const percent = ref(0)
  const message = ref('')
  const error = ref<string | null>(null)
  let eventSource: EventSource | null = null

  function start() {
    eventSource = new EventSource(url)
    eventSource.onmessage = (event) => {
      const data = JSON.parse(event.data)
      status.value = data.status
      stage.value = data.stage
      percent.value = data.percent
      message.value = data.message
      if (data.status === 'completed' || data.status === 'failed') {
        eventSource?.close()
      }
    }
    eventSource.onerror = () => {
      error.value = 'SSE 连接中断'
      eventSource?.close()
    }
  }

  function stop() {
    eventSource?.close()
    eventSource = null
  }

  onUnmounted(stop)

  return { status, stage, percent, message, error, start, stop }
}
```

### 5.5 进度阶段映射

| stage | percent | 含义 |
|---|---|---|
| `upload` | 0–10 | 文件上传中 |
| `audiveris` | 10–50 | OMR 识别（最耗时） |
| `convert` | 50–70 | MusicXML → JianpuScore 转换 |
| `render` | 70–90 | 简谱 SVG 渲染 |
| `export` | 90–100 | MuseScore 导出 |

---

## 6. API 路由完整设计

### 6.1 路由总表

| 方法 | 路径 | 对应 UseCase | 说明 |
|---|---|---|---|
| `GET` | `/health` | — | 健康检查（Electron 用） |
| `POST` | `/recognize` | `RecognizeScoreUseCase` | 图片/PDF → MusicXML（同步，适合小文件） |
| `POST` | `/recognize/stream` | `RecognizeScoreUseCase` | 同上，但用 SSE 推送进度 |
| `POST` | `/convert/musicxml-to-jianpu` | `ConvertMusicXmlToJianpuUseCase` | MusicXML → 简谱文本 |
| `POST` | `/convert/jianpu-to-musicxml` | `ConvertJianpuToMusicXmlUseCase` | 简谱文本 → MusicXML |
| `POST` | `/render/jianpu-svg` | `RenderMusicXmlJianpuUseCase` | MusicXML → 简谱 SVG |
| `POST` | `/render/jianpu-text-svg` | `RenderJianpuTextUseCase` | 简谱文本 → SVG |
| `POST` | `/render/preserving-layout` | 组合 | OCR 文字层 + 简谱，保持原页面布局 |
| `POST` | `/pipeline` | `FullPipelineUseCase` | 一键：识别 + 转换 + 渲染 |
| `POST` | `/pipeline/stream` | `FullPipelineUseCase` | 同上，SSE 进度推送 |
| `POST` | `/export` | `ExportScoreUseCase` | MusicXML → PDF/PNG/MIDI (MuseScore) |
| `GET` | `/files/{file_id}` | — | 下载文件 |
| `DELETE` | `/files/{file_id}` | — | 删除临时文件 |
| `GET` | `/settings` | `ToolConfig` | 获取当前配置 |
| `PUT` | `/settings` | `ToolConfig` | 更新配置（写入 .env） |

### 6.2 请求/响应 Schema（`schemas.py`）

```python
from pydantic import BaseModel, Field
from typing import Any

# ── 通用 ──

class ErrorResponse(BaseModel):
    error: str
    detail: str | None = None
    stage: str | None = Field(None, description="出错阶段：audiveris / musescore / ocr / convert / render")

# ── 转换 ──

class MusicXmlToJianpuRequest(BaseModel):
    musicxml_file_id: str
    target_key: str = "C"
    start_measure_number: int | None = None

class MusicXmlToJianpuResponse(BaseModel):
    jianpu_text: str
    jianpu_file_id: str | None = None

class JianpuToMusicXmlRequest(BaseModel):
    jianpu_text: str | None = None     # 直接传文本
    jianpu_file_id: str | None = None   # 或传已上传的文件 ID（二选一）
    title: str = "Jianpu Import"

class JianpuToMusicXmlResponse(BaseModel):
    musicxml_text: str
    musicxml_file_id: str

# ── 渲染 ──

class RenderJianpuSvgRequest(BaseModel):
    musicxml_file_id: str
    target_key: str = "C"
    start_measure_number: int | None = None
    title: str | None = None

class RenderJianpuSvgResponse(BaseModel):
    svg_file_id: str

class RenderJianpuTextSvgRequest(BaseModel):
    jianpu_text: str | None = None
    jianpu_file_id: str | None = None
    title: str = "简谱"

class RenderJianpuTextSvgResponse(BaseModel):
    svg_file_id: str

# ── 识别 ──

class RecognizeResponse(BaseModel):
    task_id: str | None = None
    musicxml_file_id: str
    musicxml_filename: str

# ── 流水线 ──

class PipelineRequest(BaseModel):
    """multipart/form-data 上传时，以下字段作为 form field。"""
    target_key: str = "C"
    start_measure_number: int | None = None
    title: str | None = None

class PipelineResponse(BaseModel):
    task_id: str | None = None
    musicxml_file_id: str
    jianpu_text: str
    jianpu_file_id: str
    svg_file_id: str

# ── 导出 ──

class ExportRequest(BaseModel):
    musicxml_file_id: str
    output_format: str = Field("pdf", pattern="^(pdf|png|mid|midi)$")
    filename: str | None = None

class ExportResponse(BaseModel):
    file_id: str
    filename: str

# ── 配置 ──

class SettingsResponse(BaseModel):
    audiveris_path: str
    musescore_path: str
    java_home: str
    work_dir: str
    target_key: str = "C"

class SettingsUpdateRequest(BaseModel):
    audiveris_path: str | None = None
    musescore_path: str | None = None
    java_home: str | None = None

# ── SSE 进度 ──

class SSEProgressEvent(BaseModel):
    task_id: str
    status: str          # pending / running / completed / failed
    stage: str           # upload / audiveris / convert / render / export
    percent: int
    message: str = ""
    error: str | None = None
    result: dict[str, Any] | None = None

# ── OCR 文字层渲染 ──

class PreservingLayoutRequest(BaseModel):
    musicxml_file_id: str
    page_image_file_id: str
    target_key: str = "C"
    start_measure_number: int | None = None

class PreservingLayoutResponse(BaseModel):
    svg_file_id: str
    page_width: float
    page_height: float
```

### 6.3 Router 示例（转换）

```python
# api/routers/convert.py
from fastapi import APIRouter, Depends, HTTPException
from ..schemas import (
    MusicXmlToJianpuRequest, MusicXmlToJianpuResponse,
    JianpuToMusicXmlRequest, JianpuToMusicXmlResponse,
)
from ..dependencies import get_convert_to_jianpu, get_convert_to_musicxml, get_upload_manager
from ..uploads import UploadManager
from ...use_cases import ConvertMusicXmlToJianpuUseCase, ConvertJianpuToMusicXmlUseCase
from ...services.file_service import FileService

router = APIRouter(prefix="/convert", tags=["convert"])

@router.post("/musicxml-to-jianpu", response_model=MusicXmlToJianpuResponse)
async def musicxml_to_jianpu(
    req: MusicXmlToJianpuRequest,
    uc: ConvertMusicXmlToJianpuUseCase = Depends(get_convert_to_jianpu),
    uploads: UploadManager = Depends(get_upload_manager),
):
    path = uploads.get_path(req.musicxml_file_id)
    if not path or not path.exists():
        raise HTTPException(404, f"文件不存在：{req.musicxml_file_id}")

    jianpu_text = uc.execute(path, target_key=req.target_key,
                             start_measure_number=req.start_measure_number)
    return MusicXmlToJianpuResponse(jianpu_text=jianpu_text)

@router.post("/jianpu-to-musicxml", response_model=JianpuToMusicXmlResponse)
async def jianpu_to_musicxml(
    req: JianpuToMusicXmlRequest,
    uc: ConvertJianpuToMusicXmlUseCase = Depends(get_convert_to_musicxml),
    uploads: UploadManager = Depends(get_upload_manager),
):
    if req.jianpu_text:
        xml_text = uc.execute_text(req.jianpu_text, title=req.title)
    elif req.jianpu_file_id:
        path = uploads.get_path(req.jianpu_file_id)
        if not path or not path.exists():
            raise HTTPException(404, f"文件不存在：{req.jianpu_file_id}")
        xml_text = uc.execute_file(path, title=req.title)
    else:
        raise HTTPException(400, "必须提供 jianpu_text 或 jianpu_file_id")

    file_service = FileService()
    out_path = uploads.base_dir / f"{uuid.uuid4().hex[:12]}.musicxml"
    file_service.write_text(out_path, xml_text)
    musicxml_id = uploads.register(out_path)

    return JianpuToMusicXmlResponse(musicxml_text=xml_text, musicxml_file_id=musicxml_id)
```

---

## 7. 前端 MVVM 设计（Vue3）

### 7.1 MVVM 映射

| 层级 | 责任 | 位置 |
|---|---|---|
| **View** | 页面/组件，纯 UI 渲染和用户交互 | `views/*.vue` + `components/*.vue` |
| **ViewModel（全局）** | 跨页面共享状态、业务状态管理 | `stores/*.ts`（Pinia） |
| **ViewModel（局部）** | 页面内可复用逻辑（上传、SSE） | `composables/*.ts` |
| **Model** | TypeScript 类型、API 请求封装 | `models/types.ts` + `api/*.ts` |

### 7.2 全局状态（Pinia Stores）

为什么需要 Pinia 而不是纯 composable？因为现有 PySide6 ViewModel 的状态是跨页面共享的（`musicxml_file`、`jianpu_text`、`busy` 等），Vue composable 是实例级别的，每次 `useXxx()` 创建新实例。Pinia store 是全局单例，才能对齐现有 ViewModel 的行为。

#### `stores/task.ts`

```typescript
// desktop/src/renderer/src/stores/task.ts
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useTaskStore = defineStore('task', () => {
  // ── 状态（对应 MainWindowViewModel 的属性）──
  const inputFileName = ref<string>('')
  const inputFileId = ref<string>('')
  const musicxmlFileId = ref<string>('')
  const musicxmlText = ref<string>('')
  const jianpuText = ref<string>('')
  const svgFileId = ref<string>('')
  const isBusy = ref(false)

  // ── 计算属性 ──
  const hasMusicxml = computed(() => !!musicxmlFileId.value)
  const hasInput = computed(() => !!inputFileId.value)

  // ── 动作（对应 MainWindowViewModel 的方法）──
  function setInputFile(name: string, file_id: string) {
    inputFileName.value = name
    inputFileId.value = file_id
  }

  function setMusicxml(file_id: string, text: string) {
    musicxmlFileId.value = file_id
    musicxmlText.value = text
  }

  function setJianpu(text: string) {
    jianpuText.value = text
  }

  function setSvg(file_id: string) {
    svgFileId.value = file_id
  }

  function setBusy(value: boolean) {
    isBusy.value = value
  }

  function reset() {
    inputFileName.value = ''
    inputFileId.value = ''
    musicxmlFileId.value = ''
    musicxmlText.value = ''
    jianpuText.value = ''
    svgFileId.value = ''
    isBusy.value = false
  }

  return {
    inputFileName, inputFileId, musicxmlFileId, musicxmlText,
    jianpuText, svgFileId, isBusy,
    hasMusicxml, hasInput,
    setInputFile, setMusicxml, setJianpu, setSvg, setBusy, reset,
  }
})
```

#### `stores/settings.ts`

```typescript
// desktop/src/renderer/src/stores/settings.ts
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { getSettings, updateSettings } from '../api/client'

export const useSettingsStore = defineStore('settings', () => {
  const audiverisPath = ref('')
  const musescorePath = ref('')
  const javaHome = ref('')
  const targetKey = ref('C')
  const startMeasureNumber = ref<number | null>(null)

  async function load() {
    const data = await getSettings()
    audiverisPath.value = data.audiveris_path
    musescorePath.value = data.musescore_path
    javaHome.value = data.java_home
  }

  async function save() {
    await updateSettings({
      audiveris_path: audiverisPath.value,
      musescore_path: musescorePath.value,
      java_home: javaHome.value,
    })
  }

  return {
    audiverisPath, musescorePath, javaHome, targetKey, startMeasureNumber,
    load, save,
  }
})
```

#### `stores/log.ts`

```typescript
// desktop/src/renderer/src/stores/log.ts
import { defineStore } from 'pinia'
import { ref } from 'vue'

export interface LogEntry {
  timestamp: string
  level: 'info' | 'warn' | 'error'
  message: string
}

export const useLogStore = defineStore('log', () => {
  const entries = ref<LogEntry[]>([])

  function addLog(message: string, level: LogEntry['level'] = 'info') {
    entries.value.push({
      timestamp: new Date().toLocaleTimeString(),
      level,
      message,
    })
  }

  function addError(message: string) {
    addLog(message, 'error')
  }

  function clear() {
    entries.value = []
  }

  return { entries, addLog, addError, clear }
})
```

### 7.3 页面示例（识别页）

```vue
<!-- desktop/src/renderer/src/views/RecognizeView.vue -->
<template>
  <n-space vertical>
    <n-space>
      <file-uploader @upload="onFileUploaded" accept=".pdf,.png,.jpg,.jpeg,.tif,.tiff" />
      <n-button @click="recognize" :loading="store.isBusy" :disabled="!store.hasInput">
        识别为 MusicXML
      </n-button>
      <n-button @click="recognizeAndExport" :loading="store.isBusy" :disabled="!store.hasInput">
        识别并导出简谱
      </n-button>
      <n-button @click="openMusicXml">直接打开 MusicXML</n-button>
    </n-space>

    <n-progress v-if="sse.status.value === 'running'"
      :percentage="sse.percent.value" :indicator-placement="'inside'">
      {{ sse.stage.value }} - {{ sse.message.value }}
    </n-progress>

    <n-card title="MusicXML 预览">
      <n-code :code="store.musicxmlText" language="xml" word-wrap />
    </n-card>
  </n-space>
</template>

<script setup lang="ts">
import { useTaskStore } from '../stores/task'
import { useLogStore } from '../stores/log'
import { useSSE } from '../composables/useSSE'
import { recognizeApi, pipelineApi } from '../api/recognize'

const store = useTaskStore()
const log = useLogStore()
const sse = useSSE()

async function onFileUploaded(fileId: string, fileName: string) {
  store.setInputFile(fileName, fileId)
  log.addLog(`已选择文件：${fileName}`)
}

async function recognize() {
  store.setBusy(true)
  try {
    const result = await recognizeApi.stream(store.inputFileId, sse)
    store.setMusicxml(result.musicxml_file_id, '')
    log.addLog(`OMR 完成：${result.musicxml_filename}`)
  } catch (e: any) {
    log.addError(`识别失败：${e.message}`)
  } finally {
    store.setBusy(false)
  }
}

async function recognizeAndExport() {
  store.setBusy(true)
  try {
    const result = await pipelineApi.stream(store.inputFileId, sse, {
      target_key: store.targetKey,
    })
    store.setMusicxml(result.musicxml_file_id, '')
    store.setJianpu(result.jianpu_text)
    store.setSvg(result.svg_file_id)
    log.addLog('流水线完成')
  } catch (e: any) {
    log.addError(`流水线失败：${e.message}`)
  } finally {
    store.setBusy(false)
  }
}
</script>
```

### 7.4 状态映射表

| PySide6 ViewModel 属性/信号 | Vue Pinia Store | 组件绑定 |
|---|---|---|
| `input_file: Path` | `useTaskStore().inputFileId/Name` | `RecognizeView` |
| `musicxml_file: Path` | `useTaskStore().musicxmlFileId` | 所有页面 |
| `musicxml_text: str` | `useTaskStore().musicxmlText` | `RecognizeView` 预览 |
| `jianpu_text: str` | `useTaskStore().jianpuText` | `ConvertView` 编辑器 |
| `busy: bool` | `useTaskStore().isBusy` | 全局按钮禁用 |
| `target_key: str` | `useSettingsStore().targetKey` | `SettingsView` |
| `start_measure_text: str` | `useSettingsStore().startMeasureNumber` | `SettingsView` |
| `config: ToolConfig` | `useSettingsStore()` 全部属性 | `SettingsView` |
| `log_added` signal | `useLogStore().addLog()` | `LogPanel` 组件 |
| `error_occurred` signal | `useLogStore().addError()` + Naive UI `useMessage` | 全局 |
| `busy_changed` signal | `useTaskStore().isBusy` (响应式) | 全局按钮 |
| `input_file_changed` signal | `useTaskStore().setInputFile()` | `RecognizeView` |
| `musicxml_text_changed` signal | `useTaskStore().setMusicxml()` | `RecognizeView` |
| `jianpu_text_changed` signal | `useTaskStore().setJianpu()` | `ConvertView` |

---

## 8. Electron 与 FastAPI 集成方案

### 8.1 后端进程管理（`backend.ts`）

```typescript
// desktop/src/main/backend.ts
import { spawn, ChildProcess } from 'child_process'
import { app } from 'electron'
import path from 'path'
import http from 'http'

const DEFAULT_PORT = 18513
const HEALTH_CHECK_INTERVAL = 1000
const HEALTH_CHECK_TIMEOUT = 15000
const SHUTDOWN_TIMEOUT = 5000

export class BackendProcess {
  private process: ChildProcess | null = null
  private port: number
  private baseURL: string

  constructor(port: number = DEFAULT_PORT) {
    this.port = port
    this.baseURL = `http://127.0.0.1:${port}`
  }

  async start(): Promise<void> {
    const isDev = !app.isPackaged

    if (isDev) {
      // 开发环境：spawn uvicorn
      this.process = spawn('python', [
        '-m', 'uvicorn',
        'score_trans.api.app:create_app()',
        '--host', '127.0.0.1',
        '--port', String(this.port),
        '--reload',
      ], { stdio: 'pipe' })
    } else {
      // 生产环境：spawn backend/backend.exe
      const exePath = path.join(process.resourcesPath, 'backend', 'backend.exe')
      this.process = spawn(exePath, [
        '--host', '127.0.0.1',
        '--port', String(this.port),
      ], { stdio: 'pipe' })
    }

    this.process.stdout?.on('data', (data: Buffer) => {
      console.log(`[backend] ${data.toString().trim()}`)
    })
    this.process.stderr?.on('data', (data: Buffer) => {
      console.error(`[backend] ${data.toString().trim()}`)
    })

    this.process.on('exit', (code) => {
      console.log(`[backend] 进程退出，code=${code}`)
      this.process = null
    })

    // 等待健康检查通过
    await this.waitForHealthy()
  }

  async waitForHealthy(maxWait: number = HEALTH_CHECK_TIMEOUT): Promise<void> {
    const start = Date.now()
    while (Date.now() - start < maxWait) {
      try {
        await this.healthCheck()
        return  // 健康检查通过
      } catch {
        await new Promise(r => setTimeout(r, HEALTH_CHECK_INTERVAL))
      }
    }
    throw new Error(`后端启动超时（${maxWait}ms）`)
  }

  healthCheck(): Promise<void> {
    return new Promise((resolve, reject) => {
      const req = http.get(`${this.baseURL}/health`, (res) => {
        res.resume()
        if (res.statusCode === 200) resolve()
        else reject(new Error(`health check returned ${res.statusCode}`))
      })
      req.on('error', reject)
      req.setTimeout(2000, () => { req.destroy(); reject(new Error('timeout')) })
    })
  }

  async stop(): Promise<void> {
    if (!this.process) return

    // 尝试优雅关闭
    this.process.kill('SIGTERM')

    await new Promise<void>((resolve) => {
      const timeout = setTimeout(() => {
        this.process?.kill('SIGKILL')
        resolve()
      }, SHUTDOWN_TIMEOUT)

      this.process?.on('exit', () => {
        clearTimeout(timeout)
        resolve()
      })
    })

    this.process = null
  }

  getBaseURL(): string {
    return this.baseURL
  }
}
```

### 8.2 主进程集成（`index.ts`）

```typescript
// desktop/src/main/index.ts
import { app, BrowserWindow } from 'electron'
import { BackendProcess } from './backend'

let mainWindow: BrowserWindow | null = null
let backend: BackendProcess | null = null

app.on('ready', async () => {
  backend = new BackendProcess()
  await backend.start()

  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    webPreferences: {
      preload: path.join(__dirname, '../preload/index.js'),
      // 生产环境不加载 file:// 时需要 nodeIntegration
      nodeIntegration: false,
      contextIsolation: true,
    },
  })

  const isDev = !app.isPackaged
  if (isDev) {
    mainWindow.loadURL('http://localhost:5173')  // Vite dev server
  } else {
    mainWindow.loadFile(path.join(__dirname, '../renderer/index.html'))
  }

  // 将后端地址注入 renderer
  mainWindow.webContents.session.webRequest.onBeforeSendHeaders((details, callback) => {
    callback({ requestHeaders: details.requestHeaders })
  })
})

app.on('before-quit', async (e) => {
  if (backend) {
    e.preventDefault()
    await backend.stop()
    app.quit()
  }
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})
```

### 8.3 FastAPI 健康检查端点

```python
# api/routers/health.py
from fastapi import APIRouter

router = APIRouter(tags=["health"])

@router.get("/health")
async def health():
    return {"status": "ok"}
```

### 8.4 FastAPI 应用工厂

```python
# api/app.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

def create_app() -> FastAPI:
    app = FastAPI(title="Score Trans API", version="0.1.0")

    # CORS（仅开发环境需要，生产环境 Electron 用 file:// 不需要）
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],  # Vite dev server
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from .routers import health, convert, recognize, render, pipeline, files
    app.include_router(health.router)
    app.include_router(convert.router)
    app.include_router(recognize.router)
    app.include_router(render.router)
    app.include_router(pipeline.router)
    app.include_router(files.router)

    return app
```

### 8.5 端口策略

- **默认端口**：`18513`（选一个不常用的端口，减少冲突概率）
- **冲突检测**：启动前先尝试 `GET /health`，如果已有响应说明端口被占用
- **备用策略**：Electron 可尝试 `18513 → 18514 → 18515`，找到可用端口后注入 renderer
- **端口注入**：通过 `preload` 脚本暴露 `window.__BACKEND_URL__`

---

## 9. 打包与发布（Windows）

### 9.1 后端打包

```powershell
# 使用 --onedir（目录模式），不用 -F（单文件模式）
# -F 启动慢（每次解压到临时目录），且 hidden import 难排查

# 方案 A：纯 FastAPI，不含 PySide6
pyinstaller --onedir ^
  --name backend ^
  --hidden-import=score_trans.api.app ^
  --hidden-import=uvicorn.logging ^
  --collect-all score_trans ^
  src/score_trans/api/app.py

# 产出目录：
#   dist/backend/
#     backend.exe
#     _internal/...
```

> **关键**：生产环境后端只跑 FastAPI，不依赖 PySide6。打包时排除 `PySide6` 可以大幅减小体积。

### 9.2 Electron 打包

```yaml
# desktop/electron-builder.yml
appId: com.scoretrans.app
productName: Score Trans
directories:
  output: dist-electron
files:
  - "dist/**/*"
  - "package.json"
extraResources:
  - from: "../dist/backend"
    to: "backend"
win:
  target: nsis
  icon: build/icon.ico
nsis:
  oneClick: false
  allowToChangeInstallationDirectory: true
```

### 9.3 Audiveris / JDK 分发策略

| 方案 | 优点 | 缺点 | 建议 |
|---|---|---|---|
| 要求用户预装 Audiveris + JDK 25 | 安装包小 | 用户需要手动安装 | **初期推荐**，与现有行为一致 |
| 内嵌 JRE（不含 Audiveris） | 降低用户门槛 | 增加约 80MB 体积 | 后期考虑 |
| 完全不依赖 Audiveris（纯 OCR） | 无外部依赖 | 识别精度降低 | 需评估 |

**初期建议**：沿用现有策略，用户安装 Audiveris + JDK，在设置界面配置路径。

### 9.4 依赖关系

```
桌面应用安装包
  ├─ Electron + Vue3 前端         (~150MB)
  ├─ backend/ (FastAPI 打包)      (~30-50MB, 不含 PySide6)
  └─ 外部工具（用户自行安装）
       ├─ Audiveris（可选，OMR 识别时需要）
       └─ MuseScore（可选，导出时需要）
```

---

## 10. 错误处理与日志

### 10.1 统一错误响应

所有 API 错误返回统一格式：

```json
{
  "error": "Audiveris 执行失败",
  "detail": "外部程序执行失败：audiveris -batch ... \nSTDERR: ...",
  "stage": "audiveris"
}
```

```python
# api/app.py 中注册异常处理
from fastapi import Request
from fastapi.responses import JSONResponse
from ..services.external_tools import ExternalToolError
from ..services.ocr_provider import OCRError

@app.exception_handler(ExternalToolError)
async def external_tool_error_handler(request: Request, exc: ExternalToolError):
    stage = "audiveris" if "audiveris" in str(exc).lower() else "musescore"
    return JSONResponse(status_code=502, content={
        "error": str(exc),
        "stage": stage,
    })

@app.exception_handler(OCRError)
async def ocr_error_handler(request: Request, exc: OCRError):
    return JSONResponse(status_code=502, content={
        "error": str(exc),
        "stage": "ocr",
    })

@app.exception_handler(ValueError)
async def validation_error_handler(request: Request, exc: ValueError):
    return JSONResponse(status_code=400, content={
        "error": str(exc),
        "stage": "convert",
    })
```

### 10.2 错误阶段标记

| stage | 来源 | 对应异常类 |
|---|---|---|
| `audiveris` | OMR 识别失败 | `ExternalToolError` |
| `musescore` | 导出失败 | `ExternalToolError` |
| `ocr` | OCR 请求/解析失败 | `OCRError` |
| `convert` | 转换逻辑错误 | `ValueError` |
| `render` | SVG 渲染错误 | `RuntimeError` |
| `upload` | 文件上传错误 | `HTTPException(400)` |

### 10.3 前端错误处理

```typescript
// desktop/src/renderer/src/api/client.ts
import { useLogStore } from '../stores/log'

const BASE_URL = window.__BACKEND_URL__ || 'http://127.0.0.1:18513'

export async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, options)

  if (!response.ok) {
    const error = await response.json().catch(() => ({ error: `HTTP ${response.status}` }))
    const log = useLogStore()
    log.addError(`[${error.stage || 'unknown'}] ${error.error}`)
    throw new ApiError(error.error, error.stage, error.detail)
  }

  return response.json()
}

export class ApiError extends Error {
  constructor(
    message: string,
    public stage?: string,
    public detail?: string,
  ) {
    super(message)
  }
}
```

---

## 11. CORS 与安全

### 11.1 开发环境

```
Electron Renderer (localhost:5173, Vite dev server)
         │
         │  CORS 允许
         ▼
FastAPI (localhost:18513)
```

FastAPI `CORSMiddleware` 只允许 `http://localhost:5173`。

### 11.2 生产环境

生产环境 Electron 使用自定义 scheme（`score-trans://`）或 `file://`。两种方案：

**方案 A：自定义 scheme（推荐）**
- 注册 `score-trans://` 协议，请求天然同源，不需要 CORS
- `session.protocol.registerSchemesAsPrivileged([{ scheme: 'score-trans', privileges: { standard: true, secure: true } }])`

**方案 B：file://**
- `file://` 与 `http://localhost` 不同源，仍然需要 CORS
- CORS 配置中添加 `file://` origin

### 11.3 输入验证

- 文件上传类型白名单：`.pdf .png .jpg .jpeg .tif .tiff .musicxml .xml .mxl .txt`
- 文件大小限制：建议 100MB（足够处理大型 PDF 乐谱）
- 路径安全：`UploadManager` 只操作 `{work_dir}/uploads/` 子目录，不接受外部路径
- API 参数：Pydantic Schema 自带验证（类型、正则、范围）

---

## 12. 测试策略

### 12.1 后端 API 测试

```python
# tests/test_api_convert.py
import pytest
from fastapi.testclient import TestClient
from score_trans.api.app import create_app

@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)

def test_musicxml_to_jianpu(client, tmp_path):
    # 准备一个简单的 MusicXML 文件
    musicxml = tmp_path / "test.musicxml"
    musicxml.write_text(SIMPLE_MUSICXML, encoding="utf-8")

    # 上传文件
    with open(musicxml, "rb") as f:
        upload_resp = client.post("/files/upload", files={"file": ("test.musicxml", f)})
    file_id = upload_resp.json()["file_id"]

    # 调用转换
    resp = client.post("/convert/musicxml-to-jianpu", json={
        "musicxml_file_id": file_id,
        "target_key": "C",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "jianpu_text" in data
    assert "1=" in data["jianpu_text"]
```

### 12.2 复用现有 Mock 模式

现有代码已有 `MockOCRProvider`，API 测试中可以直接注入：

```python
# 测试时通过依赖覆盖注入 mock
from score_trans.services.ocr_provider import MockOCRProvider
from score_trans.domain.models import OCRTextBlock

app = create_app()
app.dependency_overrides[get_ocr_provider] = lambda: MockOCRProvider([
    OCRTextBlock(text="Allegro", role="expression"),
])
```

### 12.3 前端测试

```typescript
// desktop/src/renderer/src/stores/__tests__/task.spec.ts
import { describe, it, expect } from 'vitest'
import { useTaskStore } from '../task'
import { createPinia, setActivePinia } from 'pinia'

describe('useTaskStore', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('should track busy state', () => {
    const store = useTaskStore()
    expect(store.isBusy).toBe(false)
    store.setBusy(true)
    expect(store.isBusy).toBe(true)
  })
})
```

### 12.4 E2E 测试（Playwright）

```typescript
// desktop/e2e/convert.spec.ts
import { test, expect, _electron as electron } from '@playwright/test'

test('launch app and convert', async () => {
  const app = await electron.launch({ args: ['dist/main/index.js'] })
  const window = await app.firstWindow()

  await expect(window.locator('text=Score Trans')).toBeVisible()
  // ... 上传文件、点击转换、验证输出

  await app.close()
})
```

---

## 13. OCR 文字层与页面尺寸约束

> 目标：**仅翻译谱子**，**文字不翻译且位置不变**，并且**输出页面尺寸与原谱一致**。

### 13.1 需求要点

- **文字不翻译**，只翻译谱子（音符 → 简谱）
- **文字位置固定**，保持与原谱一致
- **页面尺寸固定**，输出与原谱尺寸完全一致

### 13.2 API 设计

```
POST /render/preserving-layout
  Content-Type: multipart/form-data
  ┌─ musicxml_file: MusicXML/MXL 文件（或 file_id）
  ├─ page_image: 原始页面图片（用于 OCR + 尺寸提取）
  ├─ target_key: "C"
  └─ start_measure_number: 可选

  Response:
  ┌─ svg_file_id: 输出 SVG 文件 ID
  ├─ page_width: 页面宽度（像素）
  └─ page_height: 页面高度（像素）
```

### 13.3 实现流程

```
1. 获取页面尺寸
   ├── 图片文件：读取图片宽高（PIL / cv2 / 纯二进制头解析）
   └── PDF 文件：使用 PyMuPDF (fitz) 提取页面 MediaBox

2. OCR 文字提取
   ├── 使用 OpenAICompatibleOCRProvider（复用现有）
   ├── 返回 TextBlock[]，每个带 bbox 坐标和 role
   └── 按 role 分类：title / instrument / lyric / expression / measure_number

3. SVG 生成（扩展现有 rendering.py）
   ├── viewBox = 原始页面尺寸（点或像素）
   ├── 文字层：<text> 元素，使用 bbox 绝对定位
   │   ├── x/y 从 bbox 推算
   │   └── font-size 从 bbox 高度推算
   ├── 简谱层：在同一坐标系中排版
   │   ├── 复用 render_score_svg() 的逻辑
   │   └── 排版区域 = 页面尺寸 - 文字占位区域（或覆盖模式）
   └── 页面尺寸严格锁定，不参与自适应
```

### 13.4 坐标系统对齐

```
原图片坐标系:  左上角 (0,0)，右下角 (width, height)
SVG viewBox:   0 0 {width} {height}
文字定位:      <text x="{bbox[0]}" y="{bbox[3]}">text</text>
                bbox = [x1, y1, x2, y2] → SVG 坐标直接使用
```

需要处理的问题：
- OCR 返回的 bbox 可能是归一化坐标（0-1），需要乘以页面宽高还原
- 不同 OCR 模型返回格式不同，在 `ocr_provider.py` 中统一转换

### 13.5 关键注意事项

- 简谱渲染不能改变页面尺寸
- 文字 `<text>` 元素使用绝对坐标，不参与流式布局
- 字号由 bbox 高度推算：`font-size ≈ bbox_height * 0.85`
- 如果 OCR bbox 不可用，降级为现有纯简谱 SVG 模式

---

## 14. 实施步骤清单

### 第零步：准备开发环境

**验收标准**：`pnpm dev` 能启动 Electron 窗口并显示 Vue 页面。

| 序号 | 任务 | 产出文件 |
|---|---|---|
| 0.1 | 安装 Node.js 20+、pnpm | — |
| 0.2 | `pnpm create @quick-start/electron` 选择 Vue3 + TS 模板 | `desktop/` 目录 |
| 0.3 | `pnpm add naive-ui @vicons/ionicons5` | `desktop/package.json` |
| 0.4 | `pnpm add pinia vue-router` | `desktop/package.json` |
| 0.5 | 配置 electron-vite（alias、端口） | `desktop/electron.vite.config.ts` |
| 0.6 | 创建目录结构（`api/`, `stores/`, `composables/`, `views/`, `components/`） | 空文件骨架 |

### 第一步：搭建 FastAPI API 层

**验收标准**：`python -m uvicorn score_trans.api.app:create_app()` 能启动，`curl /health` 返回 200。

**API 依赖图（建议实现顺序）：**

```
health.py           ← 第一个实现（无依赖）
  ↓
schemas.py          ← 定义所有 DTO
uploads.py          ← 文件上传管理
  ↓
convert.py          ← 依赖 uploads + schemas + 现有 use_cases
render.py           ← 依赖 uploads + schemas + 现有 use_cases
  ↓
recognize.py        ← 依赖 uploads + 外部工具
  ↓
pipeline.py         ← 组合 recognize + convert + render
files.py            ← 文件下载/删除
  ↓
tasks.py            ← SSE 进度推送（可选，第二迭代）
```

| 序号 | 任务 | 产出文件 |
|---|---|---|
| 1.1 | 创建 `api/app.py`（FastAPI 应用工厂 + CORS） | `api/app.py` |
| 1.2 | 创建 `api/routers/health.py`（`GET /health`） | `api/routers/health.py` |
| 1.3 | 创建 `api/schemas.py`（所有 DTO） | `api/schemas.py` |
| 1.4 | 创建 `api/uploads.py`（UploadManager） | `api/uploads.py` |
| 1.5 | 创建 `api/dependencies.py`（use_case 注入） | `api/dependencies.py` |
| 1.6 | 实现 `api/routers/convert.py` | `api/routers/convert.py` |
| 1.7 | 实现 `api/routers/render.py` | `api/routers/render.py` |
| 1.8 | 实现 `api/routers/recognize.py` | `api/routers/recognize.py` |
| 1.9 | 实现 `api/routers/pipeline.py` | `api/routers/pipeline.py` |
| 1.10 | 实现 `api/routers/files.py` | `api/routers/files.py` |
| 1.11 | 编写 API 测试（TestClient） | `tests/test_api_*.py` |

### 第二步：Electron 启动 FastAPI

**验收标准**：启动 Electron 桌面应用后，FastAPI 后端自动启动，健康检查通过。

| 序号 | 任务 | 产出文件 |
|---|---|---|
| 2.1 | 实现 `main/backend.ts`（BackendProcess 类） | `desktop/src/main/backend.ts` |
| 2.2 | 实现 `main/index.ts`（创建窗口 + 启动后端） | `desktop/src/main/index.ts` |
| 2.3 | 实现 `preload/index.ts`（暴露 `__BACKEND_URL__`） | `desktop/src/preload/index.ts` |

### 第三步：前端对接后端

**验收标准**：在 Electron 中能完成完整的识别→转换→渲染→导出流程。

| 序号 | 任务 | 产出文件 |
|---|---|---|
| 3.1 | 实现 `api/client.ts`（HTTP 封装 + 错误处理） | `desktop/src/renderer/src/api/client.ts` |
| 3.2 | 实现各 API 模块（convert/recognize/render/pipeline） | `desktop/src/renderer/src/api/*.ts` |
| 3.3 | 实现 Pinia stores（task/settings/log） | `desktop/src/renderer/src/stores/*.ts` |
| 3.4 | 实现 `composables/useSSE.ts` | `desktop/src/renderer/src/composables/useSSE.ts` |
| 3.5 | 实现通用组件（LogPanel/SvgPreview/FileUploader/JianpuEditor） | `desktop/src/renderer/src/components/*.vue` |
| 3.6 | 实现页面（RecognizeView/ConvertView/ExportView） | `desktop/src/renderer/src/views/*.vue` |
| 3.7 | 实现路由和主布局 | `desktop/src/renderer/src/App.vue` |

### 第四步：打包与发布

**验收标准**：双击 `.exe` 安装后能正常使用。

| 序号 | 任务 |
|---|---|
| 4.1 | PyInstaller 打包后端（`--onedir`，排除 PySide6） |
| 4.2 | 配置 electron-builder（`extraResources` 指向后端目录） |
| 4.3 | 测试完整安装流程 |
| 4.4 | 测试外部工具（Audiveris/MuseScore）在安装版中的调用 |

### 第五步（可选）：SSE 进度推送

| 序号 | 任务 |
|---|---|
| 5.1 | 实现 `api/tasks.py`（TaskManager） |
| 5.2 | 在 recognize/pipeline router 中添加 `/stream` 端点 |
| 5.3 | 前端接入 SSE，显示进度条 |

---

## 15. 与现有代码的边界

### 15.1 不改动的模块

以下模块完全保持现有代码，API 层通过 import 调用：

| 模块 | 原因 |
|---|---|
| `domain/models.py` | 纯数据模型，无外部依赖 |
| `domain/jianpu.py` | 简谱文本 ↔ MusicXML 转换 |
| `domain/musicxml.py` | MusicXML → JianpuScore 解析 |
| `services/rendering.py` | SVG 渲染引擎 |
| `services/external_tools.py` | Audiveris/MuseScore CLI 调用 |
| `services/ocr_provider.py` | OCR 客户端 |
| `services/settings.py` | 配置管理 |
| `use_cases/*` | 所有 use_case 保持原样 |
| `cli/commands.py` | CLI 保持原样 |
| `viewmodels/` | Qt ViewModel 保持原样 |
| `views/` | PySide6 View 保持原样 |

### 15.2 新增模块的职责

| 新增模块 | 职责 | 改动现有代码？ |
|---|---|---|
| `api/routers/` | HTTP 参数提取 → 调用 use_case → 格式化响应 | ❌ |
| `api/schemas.py` | 请求验证 + 响应序列化 | ❌ |
| `api/uploads.py` | HTTP 文件 → 本地路径（适配器） | ❌ |
| `api/tasks.py` | 后台任务状态管理 | ❌ |
| `api/app.py` | FastAPI 应用组装 | ❌ |

### 15.3 适配模式

```
HTTP 请求（文件上传）
  → uploads.save(file) → 本地 Path
  → use_case.execute(path, ...) → 结果
  → schema 序列化 → HTTP 响应
```

所有对现有代码的调用都是通过正常的 Python import + 函数调用，不需要修改任何现有函数签名。

### 15.4 PySide6 代码的保留策略

- **保留**：`viewmodels/` 和 `views/` 目录完整保留
- **共存**：CLI（`python -m score_trans`）仍然可以直接启动 PySide6 GUI
- **最终形态**：两种 UI 共存，用户可以选择：
  - `score-trans` 命令 → CLI
  - `ScoreTrans.exe` → Electron 桌面应用（新）
  - `python -m score_trans` → PySide6 桌面应用（现有）

---

## 16. 关键注意事项

### 必须做

- [ ] CORS 仅开发环境开启，生产环境使用自定义 scheme
- [ ] FastAPI 端口冲突检测与健康检查
- [ ] Electron `before-quit` 中优雅关闭后端（SIGTERM → 等待 → SIGKILL）
- [ ] Renderer 进程禁止直接使用 Node API（通过 preload bridge）
- [ ] 文件上传大小限制（建议 100MB）
- [ ] 上传文件只操作 `{work_dir}/uploads/` 子目录
- [ ] 后端打包排除 PySide6（生产不需要 Qt 依赖）

### 容易忽略

- [ ] Audiveris 需要 JDK 25，需要在设置界面/文档中提醒用户
- [ ] Java 代理设置：`http_proxy` → `JAVA_TOOL_OPTIONS`（已在 `external_tools.py` 中处理）
- [ ] `.env` 文件加载：`load_project_env()` 在 API 启动时需要调用
- [ ] 简谱文本编码：统一 UTF-8（已在 `file_service.py` 中处理）
- [ ] MXL 文件是 ZIP 格式，上传后 Content-Type 应为 `application/zip`

---

## 17. 最终交付物

```
桌面应用.exe (NSIS 安装包)
  ├─ Electron + Vue3 + Naive UI 界面
  ├─ FastAPI 后端引擎（backend.exe + 依赖）
  ├─ 复用既有 use_cases / domain / services
  ├─ SSE 实时进度反馈
  ├─ 文件上传/下载管理
  └─ 统一错误处理与日志面板
```

### 功能清单对照

| 现有 PySide6 功能 | 新 Vue3 实现 | API |
|---|---|---|
| Audiveris 路径设置 | `SettingsView` | `PUT /settings` |
| MuseScore 路径设置 | `SettingsView` | `PUT /settings` |
| JDK 路径设置 | `SettingsView` | `PUT /settings` |
| 简谱调 / 起始小节号 | `SettingsView` | 前端本地状态 |
| 选择图片/PDF | `FileUploader` 组件 | `POST /files/upload` |
| 识别为 MusicXML | `RecognizeView` | `POST /recognize/stream` |
| 识别并导出简谱 | `RecognizeView` | `POST /pipeline/stream` |
| 直接打开 MusicXML | `RecognizeView` | `POST /files/upload` |
| MusicXML 预览 | `RecognizeView` | `GET /files/{id}` |
| MusicXML → 简谱 | `ConvertView` | `POST /convert/musicxml-to-jianpu` |
| 简谱 → MusicXML | `ConvertView` | `POST /convert/jianpu-to-musicxml` |
| 保存简谱文本 | `ConvertView` | `GET /files/{id}` (下载) |
| 导出简谱 SVG | `ConvertView` | `POST /render/jianpu-svg` |
| 保存 MusicXML | `ExportView` | `GET /files/{id}` (下载) |
| MuseScore 导出 | `ExportView` | `POST /export` |
| 日志面板 | `LogPanel` 组件 | `useLogStore` |
| Busy 状态 | 全局 `isBusy` | `useTaskStore` |
| 错误弹窗 | Naive UI `useMessage` | `useLogStore.addError` |
