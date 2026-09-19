# 后端中英文切换改造方案

调研时间：2026-09-19
范围：`backend/`（Python）+ `desktop/`（Electron 渲染进程/主进程），`website/` 本次不动

---

## 一、调研结论：现状如何

### 1.1 前端已经做完了，而且做得很规范

| 层 | 文件 | 状态 |
|---|---|---|
| 语言状态与解析 | `desktop/src/renderer/src/i18n/index.ts` | `locale` ref + 本地持久化，`t(key, vars)` 支持 `{var}` 插值 |
| 文案模块 | `i18n/locales/{zh-CN,en-US}/{app,common,components,convert,recognize,runtime,settings,syntax}.ts` | 8 个模块，双语齐全 |
| 组件库 | 同上 `naiveLocale` / `naiveDateLocale` | Naive UI 已跟随切换 |
| 原生层 | `desktop/src/main/locale.ts` + IPC `locale:get/set` | `ui-locale.json` 持久化，弹窗/菜单双语 |

结论：**切换枢纽已存在**，缺的不是"语言变量"，而是"把这个变量送到后端"的那条线。

### 1.2 后端完全没有 i18n

全量扫描 `backend/**/*.py`（排除 `__pycache__`）：

| 类别 | 行数 | 是否需要处理 |
|---|---:|---|
| 代码注释 | 122 | 否（不面向用户） |
| docstring | 77 | 否 |
| **`raise` 异常消息** | 117 | **是** |
| **结构化消息字段**（`message` / `detail` / `description`） | 69 | **是** |
| **日志 `logger.*`** | 8 | 部分（见 1.3） |
| **其他业务字符串**（诊断文案、记号数据、AI prompt） | 440 | **是** |
| 合计 | **833 行 / 76 个文件** | 需处理约 **634 行** |

热点文件：

| 行数 | 文件 | 内容 | 用户可见？ |
|---:|---|---|---|
| 110 | `domain/parse/jianpu_text.py` | **语法检查 + 时值检查的全部文案** | 直接显示 |
| 117 | `domain/performance_marks.py` | 演奏记号名称/描述 + AI 提示词 | 部分直接显示 |
| 40 | `services/recognize/external_tools.py` | Audiveris / OMR 失败原因 | 直接显示 |
| 25 | `exec/render/actions.py` | 渲染与导出异常 | 直接显示 |
| 20 | `exec/pipeline/actions.py` | 管线异常 + 任务进度文案 | 直接显示 |
| 20 | `domain/write/jianpu_text.py` | 反向生成警告 | 直接显示 |
| 19 | `exec/notation/actions.py` | 演奏技巧说明（语法说明界面） | 直接显示 |

### 1.3 关于"日志"，这里有一个常见误区

你说的"日志"实际是三样不同的东西，**处理方式应该不同**：

| 你看到的 | 真实情况 | 建议 |
|---|---|---|
| Python `logging` 输出 | 只有 8 行中文，`desktop/src/main/backend.ts` 只转发到 Electron 主进程 console，**不进 UI 的 LogPanel** | 改成英文即可，**不翻译**（日志跟随 UI 语言会破坏排查） |
| 任务进度条文案（`report_progress`） | 中文硬编码在 `exec/pipeline`、`exec/recognize`、`exec/ai`、`services/ai/transcription`，经 SSE 直接打到 UI | 要处理，见 P3 |
| UI LogPanel 里的中文 | LogPanel 主文案已 i18n，但用 `{detail}` 拼进了后端返回的中文 message，于是出现「English sentence：文件不存在：xxx」 | **治好后端即可自动消失** |

### 1.4 三个会改坏的耦合点（必须先解耦）

这是本次调研最有价值的发现——如果直接把中文替换成英文，以下三处会立刻失效：

| 位置 | 代码 | 问题 |
|---|---|---|
| `desktop/src/renderer/src/views/ConvertView.vue:1559,1572,1581` | `msg.match(/文件不存在[:：]\s*([A-Za-z0-9_-]+)/)`、`/第\s*(\d+)\s*行/`、`/第\s*(\d+)\s*页/` | **前端在用中文正则解析后端错误消息**来定位 fileId / 行号 / 页码 |
| `domain/parse/jianpu_text.py:578` | `re.fullmatch(r"小节(少拍|超拍)：实际 (.+)，目标 (.+)", error)` | 后端在**解析自己生成的消息** |
| `domain/parse/jianpu_text.py:780` | `("连音组", "和弦", "缺少结束标记") in error.detail` | 用中文子串判断错误类型 |

**因此：不能只做「字符串替换」，必须先把消息结构化（code + params）。**

### 1.5 测试层的约束（可控）

断言依赖中文消息的测试共 **15 行，分布在 5 个文件**：
`tests/test_syntax_validation.py`(9)、`test_api_routes.py`(2)、`test_convert.py`(2)、`test_ai_transcription.py`(1)、`test_jianpu.py`(1)。
例：`assert enabled_errors == ["第 1 小节：小节少拍：实际 3，目标 4"]`。

这些应改为断言 `code`，改完后就永久免疫未来的文案变动。
另有约 60 行断言 AI prompt 的中文（如 `assert "二胡识别模式" in prompt`），属 P4 决策项，见第五节。

---

## 二、技术方案：消息 key 化 + 请求级 locale + 边界渲染

### 2.1 整体设计

```
  前端切换语言
       │
       ├─ 渲染进程 local t(key)                        ← 已有
       ├─ Electron main IPC                            ← 已有
       └─ HTTP: Accept-Language: en-US  ── 新增
                │
          [LocaleMiddleware]  ← 解析并写入 ContextVar
                │
       ┌────────┴─────────┐
    异常通道           诊断通道
  LocalizedError     SyntaxDiagnostic
  (code+params)      (code+params)
       │                  │
       └──── 渲染为 message 文本（在此处决定语言）
                │
            JSONResponse → UI
```

核心原则：**业务层永远只产出 `(code, params)`，绝不产出已渲染的自然语言；渲染统一发生在最后一层。**

### 2.2 新增：`models/common/i18n.py`

放在 `models/` 的理由（符合 `AGENTS.md` 架构规则）：
- 规则明确「所有层（`api/`/`exec/`/`services/`/`dao/`/`domain/`）均可 import `models/`」，而 `domain/` **不可** import `services/`/`exec/`/`api/`
- 因此 `models/common/i18n.py` 是唯一能被 `domain/parse/jianpu_text.py` 合法引用的位置
- 与现有横切设施 `models/common/errors.py` 同级

API 设计：

```python
LocaleCode = Literal["zh-CN", "en-US"]

_current_locale: ContextVar[LocaleCode] = ContextVar("score_trans_locale", default="zh-CN")

def get_locale() -> LocaleCode: ...
def set_locale(code: LocaleCode) -> Token: ...
def locale_scope(code: LocaleCode) -> Iterator[LocaleCode]: ...   # contextmanager

def t(key: str, **vars: object) -> str:
    """查消息目录并按当前 locale 插值；缺失时回退 zh-CN，再缺失则返回 key。"""
```

关键点：
- **默认 `zh-CN`** → 非 HTTP 路径（单元测试、脚本、CLI）零改动，向后兼容
- 缺失 key 的行为：**回退中文 → 再缺失则返回 `key` 本身**，保证迁移期不会崩
- 消息目录建议按领域分文件 `models/common/messages/{zh-CN,en-US}/*.py`，避免单文件超 600 行

### 2.3 新增：`LocaleMiddleware`

- 读 `Accept-Language`（推荐，标准，curl/官网 demo 未来也能用），退化读 `X-Score-Trans-Locale`
- **用纯 ASGI 中间件实现，不要继承 `BaseHTTPMiddleware`** —— 后者会换新 task，ContextVar 传播行为需要额外处理
- 注册位置：在 `api/app.py` 现有三个 middleware 之后 `add_middleware`（即最外层），这样连鉴权中间件抛出的错误也能本地化
- 为什么不用路由 `Depends`：需要改几十个路由签名，且覆盖不到异常处理器

### 2.4 通道一：诊断消息结构化（`SyntaxDiagnostic`）

```python
class SyntaxDiagnostic(BaseModel):
    id: str
    message: str                      # 保持：已渲染好语言的文本，老客户端不受影响
    code: str | None = None           # 新增：稳定机器码，如 "measure_too_few_beats"
    params: dict[str, Any] = ...      # 新增：{actual: 3, target: 4}
    # 其余字段不变
```

改造 `domain/parse/jianpu_text.py`：
- 引入 `_syntax_error(token, code, **params)`，`ValidationError` 携带 `code`/`params`
- `message` 在组装 `SyntaxDiagnostic` 时由 `t(code, **params)` + 位置前缀生成
- 顺带修掉 1.4 中 L578 / L780 的自解析（改为直接读 `code`）

### 2.5 通道二：异常消息结构化

新增：

```python
class LocalizedError(RuntimeError):
    def __init__(self, code: str, **params: object) -> None: ...
    self.code: str
    self.params: dict[str, Any]
```

在 `api/app.py` 的 7 个 exception handler 中统一：

```python
content = {"error": render_message(exc, get_locale()), "stage": ..., "code": ...}
```

`render_message()` 规则：
- 是 `LocalizedError` → `t(exc.code, **exc.params)`
- 否（旧的明文异常）→ `str(exc)` 原样返回 → **保证迁移期行为不回退**

这样改造可以逐个 `raise` 点替换，**不需要一次性全改完**。

### 2.6 通道三：任务进度文案

`report_progress(cb, stage, percent, message)` 的 `message` 改为 `(code, params)` 结构：

```python
report_progress(cb, "omr", 10, "omr.prepare")     # 替代 "准备 OMR 识别"
```

由前端 `runtime` locale 新增 `progress.*` 映射翻译。
**理由**：后端不需要承担这层翻译，前端已有成熟 i18n + 插值，改起来更快。

### 2.7 为什么不推荐的做法

| 方案 | 为什么不采用 |
|---|---|
| 后端把中文用 Google/AI 翻译 API | 实时网络依赖、不可缓存、失败难降级、术语（「声线」「声部」「时值」）翻译质量不可控 |
| 前端维护一张「中文原文 → 英文译文」映射表 | 后端改一个标点就全部失配，且无法处理 `{var}` 插值位置差异 |
| 直接把中文字符串换成英文字符串 | 1.4 的三处解析会直接崩；且丧失未来再加语言的可能 |

---

## 三、分批实施计划（按优先级）

| 批次 | 内容 | 涉及文件 | 可交付验证 |
|---|---|---|---|
| **P0 地基** | `models/common/i18n.py` + `LocaleMiddleware` + 前端注入 `Accept-Language` header + contextvar 跨线程验证 | 约 4 个 | 请求带 `en-US` 时 `get_locale()` 返回正确值，含 `to_thread` 场景 |
| **P1 语法/时值检查** ⭐ | `jianpu_text.py` 110 行消息 key 化；`SyntaxDiagnostic` 增 `code`/`params`；修 L578/L780 自解析；前端 `ConvertView.vue` 三处正则改读 `code`；15 行测试断言改断言 `code` | 约 8 个 | 切英文后语法面板与时值提示全英文；`pytest tests/test_syntax_validation.py` 全绿 |
| **P2 异常与 API 边界** | `LocalizedError` + `render_message()` + 7 个 handler；迁移 `exec/*/actions.py` 约 40 处 raise + `external_tools.py` 40 行 | 约 12 个 | LogPanel、错误 toast 全英文 |
| **P3 进度文案** | `report_progress` 改传 key；前端 `runtime` locale 加 `progress.*` | 约 6 个 | 识别/渲染/AI 进度条全英文 |
| **P4 记号与技巧内容** | `performance_marks.py` 名称描述、`exec/notation/actions.py` 说明（约 90 行） | 2 个 | 语法说明界面全英文 |
| **P5 后端内部日志** | 8 行 logging 中文改英文（不翻译） | 约 6 个 | 无回归 |

建议顺序：**P0 → P1 → P2**，这三批做完你的核心诉求就满足了；P3–P5 可以之后再补。

每批之间的验收动作统一为：
1. `python -m pytest tests/test_syntax_validation.py tests/test_api_routes.py tests/test_convert.py tests/test_jianpu.py`
2. 桌面端切到英文做一次完整冒烟：识别 → 转换 → 故意写错谱 → 看面板/日志/进度条

---

## 四、风控清单

| 风险 | 影响 | 对策 |
|---|---|---|
| `asyncio.to_thread` 是否透传 ContextVar | P0 若不成立，整个方案失效 | CPython 实现中用 `copy_context()` + `ctx.run`，可透传。P0 阶段写一个最小测试确认后再开工 |
| 中间件是否拿到 ContextVar | 异常处理器拿不到 locale | 用纯 ASGI 中间件（非 `BaseHTTPMiddleware`），并在 P0 验证 exception handler 内 `get_locale()` 有值 |
| 后台任务（`BackgroundTasks`）丢失 locale | 异步管线报错语言错乱 | 两种均在同一 task context，理论安全；P0 加断言保护 |
| 消息 key 遗漏导致界面出现裸 key（如 `syntax.measureTooFewBeats`） | 用户体验 | `t()` 缺失回退中文，并加一条架构测试：扫描 `domain/parse` 中残留中文源头串 |
| 术语翻译不一致（声部/声线/时值/古筝/阮/二胡） | 专业感下降 | P1 开工前先定一张**术语对照表**，我来拟初稿给你确认 |
| 老版本客户端 / 直连 API | 拿不到 locale | 默认 `zh-CN`，行为与今天完全一致 |

---

## 五、需要你拍板的四个决策

| # | 决策点 | 推荐选项 | 备选 |
|---|---|---|---|
| 1 | locale 传递方式 | **`Accept-Language` 请求头**（标准做法，未来官网 demo / curl / 第三方都能用） | 自定义 `X-Score-Trans-Locale`（避免被代理改写，但不标准） |
| 2 | 进度文案在哪翻译 | **前端翻译**（后端只传 key，改动最小） | 后端翻译（API 更自洽，但多维护一处目录） |
| 3 | AI 提示词要不要跟着切英文 | **不建议**（识别结果质量会随之波动，且目前 ~60 行测试锁定了中文 prompt） | 英文界面时换英文 prompt，但需做识别质量回归对比 |
| 4 | 本次做到哪一批 | **P0→P1→P2**（你的三个诉求全覆盖） | 一次性做完 P0–P5 |

另外有一个待确认的小点：**默认标题 `"简谱"` 写死在后端**（`exec/render/actions.py` 的 `_DEFAULT_TITLE`、`domain/parse/jianpu_text.py`）。建议前端传 `title` 兜底，后端不再造默认值——这属于数据而非文案，单独一刀会不会更干净？

---

## 六、结语

这份方案最核心的一句话是：**别急着翻译，先把消息变成 `(code, params)` 结构**。
翻译是机械劳动，但结构化决定了这件事做一次之后是否还会第二次返工。
