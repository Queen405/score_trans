# 环境变量参考

Score Trans 的配置分为两层：

1. **发布默认配置基线**（`backend/score_trans/config/published_defaults.json`）— 安装包默认值，新安装用户的数据库种子。包含调性、拍号显示、像素上限、Audiveris 开关、provider 选中项等非私有配置。API Key 和路径不进入基线。
2. **环境变量**（`.env`）— 运行时配置。`env.example` 是开发模板，打包时复制为 `resources/backend/.env`。provider 完整目录（`*_PROVIDER_PROFILES`）、Audiveris 执行选项（8 个 `STEP`/`FORCE`/`SAVE` 等）、API 超时/温度等仍由环境变量维护。

**配置优先级：**
1. 已存在的用户数据库值（`INSERT OR IGNORE` 保护）
2. 自动解析的内置路径（打包模式 `resources/third_party/`）
3. 发布默认配置基线（`published_defaults.json`）
4. 环境变量（`.env`）
5. 代码兜底默认值

**哪些配置属于安装包默认值：** `published_defaults.json` 中的 `backend` 和 `providers` 块。

**哪些配置由用户填写：** API Key（OCR/AI/助手）— 始终写空种子，用户在设置页填写。

**哪些配置由环境变量控制：** provider 完整目录、Audiveris 执行选项（8 个 `STEP`/`FORCE`/`SAVE` 等）、API 超时/温度/token 上限。这些不进数据库种子，由 `.env` 控制。

**JDK/Audiveris 路径：** 安装包自动解析 `resources/third_party/` 中的内置 JDK 和 Audiveris，用户无需手填。

**升级行为：** 已有用户设置只补充缺失字段，不覆盖。

---

## 外部工具路径（必填 / 推荐）

| 变量 | 说明 | 默认值 / 示例 |
|------|------|---------------|
| `SCORE_TRANS_JAVA_HOME` | JDK 25 安装目录。Audiveris 源码版要求 JDK 25。 | `E:\ENV\JAVA\JDK25` |
| `SCORE_TRANS_AUDIVERIS` | Audiveris 启动脚本路径。项目已内置源码版。 | `third_party\audiveris\gradlew.bat` |

### 配置示例（PowerShell）

```powershell
$env:SCORE_TRANS_JAVA_HOME="E:\ENV\JAVA\JDK25"
$env:SCORE_TRANS_AUDIVERIS="D:\CODE\MyProjects\score_trans\third_party\audiveris\gradlew.bat"
```

---

## OMR 预处理

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `SCORE_TRANS_OMR_PREPROCESS` | 是否在调用 Audiveris 前对图片做预处理（裁白边、增强对比、放大）。 | `1` |
| `SCORE_TRANS_OMR_PREPROCESS_LONG_EDGE` | 预处理后图片长边像素数。 | `3600` |
| `SCORE_TRANS_OMR_PREPROCESS_BINARIZE` | 是否额外做黑白化。识别异常时可尝试开启或关闭。 | `0` |

---

## Audiveris 高级参数

| 变量 | 说明 |
|------|------|
| `SCORE_TRANS_AUDIVERIS_STEP` | 限制或强制 Audiveris 执行步骤；`TEXTS` 为兼容性空操作。可选值：`LOAD`, `BINARY`, `SCALE`, `GRID`, `HEADERS`, `STEM_SEEDS`, `BEAMS`, `LEDGERS`, `HEADS`, `STEMS`, `REDUCTION`, `CUE_BEAMS`, `TEXTS`, `MEASURES`, `CHORDS`, `CURVES`, `SYMBOLS`, `LINKS`, `RHYTHMS`, `PAGE`。 |
| `SCORE_TRANS_AUDIVERIS_FORCE` | 是否强制重新执行。 |
| `SCORE_TRANS_AUDIVERIS_SAVE` | 是否保存中间结果。 |
| `SCORE_TRANS_AUDIVERIS_SWAP` | 是否启用 swap。 |
| `SCORE_TRANS_AUDIVERIS_TRANSCRIBE` | 是否直接转录。 |
| `SCORE_TRANS_AUDIVERIS_SHEETS` | 指定处理的 sheet。 |
| `SCORE_TRANS_AUDIVERIS_CONSTANTS` | 用分号分隔多个 `-constant key=value`。 |
| `SCORE_TRANS_AUDIVERIS_EXTRA_ARGS` | 高级兜底，直接追加 Audiveris CLI 参数。 |

> 默认值 `SCORE_TRANS_AUDIVERIS_STEP=` 表示不限制步骤，让 Audiveris 跑完整流程。

---

## OCR 文字层（可选）

用于把乐谱图片中的歌词、标题等文字识别后叠回 SVG。

| 变量 | 说明 | 示例 |
|------|------|------|
| `SCORE_TRANS_OCR_PROVIDER` | OCR provider ID。 | `siliconflow_deepseek_ocr` |
| `SCORE_TRANS_OCR_PROVIDER_PROFILES` | provider 配置 JSON，支持多 provider。 | 见 `env.example` |
| `SCORE_TRANS_OCR_BASE_URL` | 兼容 OpenAI 的 API 基础 URL。 | `https://api.siliconflow.cn/v1` |
| `SCORE_TRANS_OCR_MODEL` | 主模型名。 | `deepseek-ai/DeepSeek-OCR` |
| `SCORE_TRANS_OCR_FALLBACK_MODEL` | 主模型无结果时的回退模型。 | `Qwen/Qwen3-VL-8B-Instruct` |
| `SCORE_TRANS_OCR_API_KEY` | API key。 | `sk-your-key` |
| `SCORE_TRANS_OCR_TIMEOUT` | 请求超时秒数。 | `60` |
| `SCORE_TRANS_OCR_MAX_TOKENS` | 最大输出 token 数。 | `4096` |
| `SCORE_TRANS_OCR_TEMPERATURE` | 采样温度。 | `0.1` |

```powershell
$env:SCORE_TRANS_OCR_API_KEY="sk-your-key"
$env:SCORE_TRANS_OCR_BASE_URL="https://api.siliconflow.cn/v1"
$env:SCORE_TRANS_OCR_MODEL="deepseek-ai/DeepSeek-OCR"
```

---

## AI 视觉转写（可选）

独立于 Audiveris 的快速草稿流程：把乐谱图片/PDF 直接交给视觉模型，输出项目简谱文本。

| 变量 | 说明 | 示例 |
|------|------|------|
| `SCORE_TRANS_AI_PROVIDER` | AI provider ID。 | `xiaomi_mimo_v25` |
| `SCORE_TRANS_AI_PROVIDER_PROFILES` | provider 配置 JSON。 | 见 `env.example` |
| `SCORE_TRANS_AI_BASE_URL` | API 基础 URL。 | `https://api.xiaomimimo.com/v1` |
| `SCORE_TRANS_AI_MODEL` | 视觉模型名。 | `mimo-v2.5` |
| `SCORE_TRANS_AI_API_KEY` | API key。 | `sk-your-key` |
| `SCORE_TRANS_AI_TIMEOUT` | 请求超时秒数。 | `120` |
| `SCORE_TRANS_AI_TEMPERATURE` | 采样温度。 | `0.3` |
| `SCORE_TRANS_AI_MAX_TOKENS` | 输出 token 上限回退值。provider profile 的 `max_tokens` 优先于此变量；均未配置时使用 4096。 | `4096` |

provider profile JSON 支持可选字段 `max_tokens`（正整数）：已确认支持更大输出的模型可在 profile 中显式配置（如 `8192`），避免全局默认值对旧模型造成不兼容。若响应因达到上限被截断，后端会用更紧凑的提示重试一次，仍失败则返回明确的转写错误。

```powershell
$env:SCORE_TRANS_AI_API_KEY="sk-your-key"
$env:SCORE_TRANS_AI_BASE_URL="https://api.xiaomimimo.com/v1"
$env:SCORE_TRANS_AI_MODEL="mimo-v2.5"
```

---

## 工作台 AI 助手（可选）

桌面应用内简谱助手对话使用的模型。

| 变量 | 说明 | 示例 |
|------|------|------|
| `SCORE_TRANS_ASSISTANT_PROVIDER` | provider ID。 | `dashscope_deepseek_v4_flash` |
| `SCORE_TRANS_ASSISTANT_PROVIDER_PROFILES` | provider 配置 JSON。 | 见 `env.example` |
| `SCORE_TRANS_ASSISTANT_BASE_URL` | API 基础 URL。 | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| `SCORE_TRANS_ASSISTANT_MODEL` | 模型名。 | `deepseek-v4-flash` |
| `SCORE_TRANS_ASSISTANT_MAX_TOKENS` | 输出 token 上限回退值。provider profile 的 `max_tokens` 优先于此变量；均未配置时使用 4096。 | `4096` |
| `SCORE_TRANS_ASSISTANT_API_KEY` | API key。 | `sk-your-key` |

工作台聊天响应若因 `finish_reason=length` 截断，后端会自动续写（最多 3 轮），续写内容对前端透明；达到上限仍截断时报错且不保存半截回答。

> 注意：`SCORE_TRANS_OCR_MAX_TOKENS`（乐谱 OCR）仍为固定配置，OCR 长文本截断问题不属于本次 AI 续写修复范围。

---

## API 与 CORS

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `SCORE_TRANS_API_TITLE` | FastAPI 文档标题。 | `Score Trans` |
| `SCORE_TRANS_API_VERSION` | API 版本号。 | `0.1.0` |
| `SCORE_TRANS_CORS_ORIGINS` | 允许的 CORS 来源，逗号分隔。 | `http://localhost:5173,http://127.0.0.1:5173,null` |

---

## PDF 渲染

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `SCORE_TRANS_PDF_RENDER_DPI` | PDF 渲染为图片时的 DPI。 | `300` |
| `SCORE_TRANS_UPLOAD_PDF_DPI` | 上传 PDF 预览时的 DPI。 | `300` |

---

## 简谱出版渲染

出版引擎使用内置 Noto Serif CJK SC 和 Bravura 字体、固定版式参数与确定性分页，不再通过 `SCORE_TRANS_RENDER_*` 环境变量调整绘制几何。

---

## MIDI 导出

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `SCORE_TRANS_MIDI_TICKS_PER_BEAT` | 每拍 tick 数。 | `480` |
| `SCORE_TRANS_MIDI_DEFAULT_BPM` | 默认速度。 | `120` |
| `SCORE_TRANS_MIDI_DEFAULT_VELOCITY` | 默认力度。 | `80` |

---

## 参考文件

完整示例见 [`backend/score_trans/config/env.example`](../backend/score_trans/config/env.example)。
