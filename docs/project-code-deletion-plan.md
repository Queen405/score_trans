# 项目级删代码方案

审查日期：2026-07-19  
范围：后端、桌面端、测试与受 Git 管理的样例资产。目标是删除无消费者代码、重复实现和旧兼容面，不以“拆分大文件”替代删除。

## 审查结论

当前最安全的一批可以删除约 130-150 行 Python/TypeScript 代码，且全仓静态引用均只命中定义或包导出：

| 优先级 | 候选 | 证据 | 动作 |
|---|---|---|---|
| P1 | `domain/constants.py` 的 `SEMITONE_TO_STEP` | 全仓只有定义 | 删除常量 |
| P1 | `RenderActions._render_batch_a4_without_page_ocr` | 全仓只有私有方法定义 | 删除方法 |
| P1 | `models/provenance/schemas.py` 的 `RenderAnchor` | 仅类定义和 `models/provenance/__init__.py` 重导出 | 删除类和两处导出 |
| P1 | `services/ocr/client/client.py` 的 `build_request`、`send_request` | 没有调用方；现有 provider 只使用 `ocr_prompt_for_model` | 删除两个函数、只为它们服务的 import，以及包级导出 |
| P1 | `parse/jianpu_text.py` 的第二个 `_utf16_length` | 第 287 行和第 671 行为同一实现 | 保留一个定义，删除另一个 |

`/render/jianpu-svg`、`/render/jianpu-text-svg`、`/render/batch-a4` 和它们的 Action/模型不是死代码：`ConvertView.vue`、`RecognizeView.vue` 与 `usePublicationRender.ts` 都在调用。不得因为它们名称较旧而删除。

## 第一批：可直接删除

### 1. 已完成：删除无消费者符号

修改范围：

- `backend/score_trans/domain/constants.py`
- `backend/score_trans/exec/render/actions.py`
- `backend/score_trans/models/provenance/schemas.py`
- `backend/score_trans/models/provenance/__init__.py`
- `backend/score_trans/services/ocr/client/client.py`
- `backend/score_trans/services/ocr/client/__init__.py`
- `backend/score_trans/services/ocr/__init__.py`
- `backend/score_trans/domain/parse/jianpu_text.py`

已删除上述符号。验证已运行 `tests/test_render.py`、`tests/test_jianpu.py`、`tests/test_ocr.py` 和 `tests/test_architecture.py`，共 147 项通过。

风险：若仓库外有 Python 插件直接 import 这些未公开承诺的符号，会是破坏性变更。桌面应用自身没有此类消费者；发布说明应注明移除了内部 Python API。

### 2. 已完成：删除 Electron 旧连接 IPC

修改范围：

- `desktop/src/main/index.ts`：`get-backend-url` handler 及其注销
- `desktop/src/preload/index.ts`：`getBackendURL()`

证据：渲染进程只使用 `window.api.getBackendConnection()`；`getBackendURL()` 和 `get-backend-url` 仅相互引用，代码注释也明确其服务于旧开发 renderer bundle。

风险：旧版本 renderer bundle 与新版 main process 混跑时会失效。桌面发行包把 main/preload/renderer 一起打包，已接受“不兼容旧 bundle”并删除。已运行 `pnpm typecheck` 与 `pnpm test:utils`；生产构建留待本批最终验证。

## 第二批：先迁移，再删除的兼容层

### 3. 以 `measure_number_mode` 取代 `show_measure_numbers`

这两个字段表达同一件事，并且当前存在冲突组合：`show_measure_numbers=false, measure_number_mode="all"` 与 `show_measure_numbers=true, measure_number_mode="none"` 都会隐藏小节号。布尔字段分散在 settings SQLite、Pydantic 请求、pipeline/render action、渲染 service 和前端 store 中。

迁移步骤：

1. 将 `measure_number_mode` 设为唯一持久化与传输字段，`none/all/row_start` 覆盖全部语义。
2. 添加设置升级：读取旧 `show_measure_numbers` 时一次性转换成 mode；写入时只写 mode。
3. 删除 `show_measure_numbers` 的设置列/键、DTO 字段、前端类型和后端布尔适配函数。
4. 删除 API 兼容测试，重新生成 `desktop/src/renderer/src/models/openapi.ts`，运行后端全测、前端 typecheck 和工具测试。

这是高收益但跨协议的删除，不应与第一批混合提交。

### 4. 收敛 A4 页面尺寸常量

`1240 x 1754` 同时出现在渲染门面、`PublicationStyle`、文本放置、pipeline 和 render actions。它们虽不是死代码，但会使每次版式变更需要同步改多处。

先将唯一常量放在不破坏分层的 `models/` 或 `services/render` 公共 DTO 中，再移除其余字面量。此项是“以集中配置换取重复删除”，不是立即删逻辑；须先确认 `domain/text_placement.py` 不违反现有导入方向。

## 第三批：资产与生成物

- Git 没有跟踪 `build/`、`dist/`、`desktop/dist*`、`node_modules/`、`.venv/`、`__pycache__/`、pytest/ruff cache；它们可在本地清理，不应提交。
- `examples/` 有 165 个文件、约 66.6 MB，且代码和自动测试没有直接路径引用。它们更像人工 OMR 验收语料，而非死代码。建议保留一个明确、可复现的最小样例集；将其余大型 PDF/PNG/OMR 移至 release asset、Git LFS 或单独测试数据仓库后再删除。不要在没有替代集的情况下直接删除，因为当前真实 Audiveris 回归依赖人工样例。
- `website/` 在工作区约 1.38 GB，但不在 Git 跟踪范围内；先确认其是否为独立站点构建缓存，再由本地环境清理，不纳入源码提交。

## 不建议删除的项目

- `RenderJianpuSvgRequest`、`RenderJianpuTextSvgRequest` 及对应 API 路由：前端仍实际调用。
- `ocr_prompt_for_model`：两个 OCR provider 仍复用它；仅旧 urllib 请求层无消费者。
- 大型 Vue 视图：体积大不等于死代码。应先建立组件级测试，再按职责拆分；这属于维护性重构，不是删代码优先事项。
- 现有 render 单页/A4 包装：在删除旧 endpoint 之前仍由调用链使用，不能单独裁剪。

## 建议执行顺序

1. 建立基线：`python -m pytest`、`pnpm typecheck`、`pnpm test:utils`。
2. 独立提交第一批 Python 死代码删除，运行后端回归。
3. 独立提交 Electron 旧 IPC 删除，运行前端检查与生产构建。
4. 单独完成 `show_measure_numbers` 协议迁移并删除兼容层。
5. 对样例资产制定最小语料清单后再移动/删除大文件。

每一批都应在删除后执行一次全仓符号搜索，确认已删符号只存在于提交历史和发布说明中；不要为了“删得更多”删除仍有桌面端消费者的渲染入口。
