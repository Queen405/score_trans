# Restorable Text Anchors Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让失效的五线谱→简谱来源锚点在用户恢复基线文本后精确恢复，并跨历史保存保持该能力。

**Architecture:** 每页保存 canonical 文本与 canonical 锚点，用户编辑后的当前锚点始终由 canonical 基线通过 UTF-16 Myers diff 重算。前端区分有效映射、失效映射和从未映射；后端 SQLite v9 持久化 canonical 基线，并保持旧请求兼容。

**Tech Stack:** Vue 3、Pinia、TypeScript、Node `node:test`、FastAPI/Pydantic、Python dataclasses、SQLite、pytest。

**Spec:** `docs/superpowers/specs/2026-08-25-restorable-text-anchors-design.md`

## Global Constraints

- 所有字符串锚点位置统一使用 UTF-16 code unit。
- Myers 最大一般编辑距离保持 2048；超限时锚点保留上一轮状态。
- 普通编辑和保存不得改写 canonical 基线；重新识别、重置、OMR 修正可以替换整组基线。
- 只对正文发生变化的页面执行重算，不增加防抖定时器。
- 新请求字段可选，响应字段有非空默认值。
- 使用 `bash`；Python 命令固定使用 `.venv/Scripts/python.exe`。
- 本轮不创建 Git commit，完成后保留工作树供用户审阅。

---

### Task 1: 通用 Myers diff 与 UTF-16 锚点重算

**Files:**
- Create: `desktop/src/renderer/src/utils/textDiff.ts`
- Modify: `desktop/src/renderer/src/utils/jianpuTextState.ts`
- Modify: `desktop/src/renderer/src/utils/textAnchorTracking.ts`
- Test: `desktop/scripts/test-text-anchor-tracking.mjs`
- Test: `desktop/scripts/test-jianpu-page-sections.mjs`

**Interfaces:**
- Produces: `sequenceEdits<T>(base, target, maxEditDistance?): SequenceEdit<T>[] | null`
- Produces: `reconcileTextAnchors(baselineText, currentText, baselineAnchors, previousAnchors?): AnchorReconciliation`
- Preserves: `trackTextAnchors(previous, current, anchors): AnchorUpdate`

- [ ] 写失败测试：UTF-16 emoji 偏移、删除后恢复、多处离散编辑、diff 超限保留上一状态。
- [ ] 运行 `node --test scripts/test-text-anchor-tracking.mjs`，确认因缺少新接口而失败。
- [ ] 抽出 generic Myers；`jianpuTextState` 用 `Array.from()`，锚点 reconcile 用 `split('')`。
- [ ] 从 canonical 基线倒序应用离散编辑；`null` 时复制 `previousAnchors` 并返回 `reconciled: false`。
- [ ] 运行锚点和修正合并测试，确认新旧行为均通过。

### Task 2: 页面级编辑集成与 canonical generation 捕获

**Files:**
- Modify: `desktop/src/renderer/src/stores/workspace.ts`
- Modify: `desktop/src/renderer/src/views/ConvertView.vue`
- Modify: `desktop/src/renderer/src/views/RecognizeView.vue`
- Modify: `desktop/src/renderer/src/composables/useHistoryRestore.ts`
- Test: `desktop/scripts/test-frontend-lifecycle.mjs`
- Test: `desktop/scripts/test-workspace-batch-cleanup.mjs`
- Test: `desktop/scripts/test-jianpu-page-sections.mjs`

**Interfaces:**
- Adds to `TaskPage`: `textAnchorBaselineText: string` and `textAnchorBaselineAnchors: TextAnchor[]`.
- Consumes: `reconcileTextAnchors(...)` from Task 1.

- [ ] 写失败测试/结构断言：TaskPage 基线字段被 clone/load/replace 保留；编辑只处理变化页；修正流程使用 canonical reconcile。
- [ ] 运行对应 Node 测试确认失败。
- [ ] 在 workspace 的创建、清空、替换、加载路径贯通基线字段并深拷贝锚点。
- [ ] 识别结果在剥离 `@text` 后执行一次 UTF-16 对齐，同时写 current 与 canonical 锚点。
- [ ] `updateTextAnchorsAfterEdit` 跳过未变化页；缺页只失效 current anchors；正常页从 canonical 重算。
- [ ] 重置和 OMR 修正创建新 canonical generation；保留用户编辑时用多段 reconcile 得到 current anchors。
- [ ] 运行对应 Node 测试确认通过。

### Task 3: 原图三态点击行为

**Files:**
- Modify: `desktop/src/renderer/src/views/ConvertView.vue`
- Modify: `desktop/src/renderer/src/components/OriginalPreview.vue`
- Test: `desktop/scripts/test-frontend-lifecycle.mjs`

**Interfaces:**
- `OriginalPreview` new prop: `mappedSourceIds?: string[]`.
- `clickableSourceIds`: 仅当前有效锚点 source ID。
- `mappedSourceIds`: canonical 基线的全部 source ID。

- [ ] 写失败结构测试：有效集合过滤 `valid !== false`；mapped 集合来自 baseline；disabled 仅包含未映射来源。
- [ ] 运行 `node --test scripts/test-frontend-lifecycle.mjs` 确认失败。
- [ ] 将两个 ID 集合分别传入 `OriginalPreview`。
- [ ] 让失效映射既不进入 clickable layer，也不进入 disabled layer；保留真正未映射元素提示。
- [ ] 运行前端生命周期测试确认通过。

### Task 4: 前端保存、恢复和 API payload 贯通

**Files:**
- Modify: `desktop/src/renderer/src/utils/historySavePayload.ts`
- Modify: `desktop/src/renderer/src/utils/workspacePersistence.ts`
- Modify: `desktop/src/renderer/src/utils/historyPageState.ts`
- Modify: `desktop/src/renderer/src/utils/historyEvents.ts`
- Modify: `desktop/src/renderer/src/composables/useHistoryRestore.ts`
- Modify: `desktop/src/renderer/src/views/RecognizeView.vue`
- Modify: `desktop/src/renderer/src/views/ConvertView.vue`
- Test: `desktop/scripts/test-history-save-payload.mjs`
- Test: `desktop/scripts/test-workspace-persistence.mjs`

**Interfaces:**
- Sends/receives: `text_anchor_baseline_text` and `text_anchor_baseline_anchors`.

- [ ] 写失败测试：create/save payload 保留 canonical 字段；保存响应回写基线而非从当前文本构造。
- [ ] 运行 payload/persistence 测试确认失败。
- [ ] 在识别单页 PATCH/POST、批次 create/save、历史事件、两处历史恢复中贯通字段。
- [ ] 旧响应字段缺失时以当前页面文本和现有锚点作为兼容基线。
- [ ] 运行 payload/persistence 测试确认通过。

### Task 5: 后端契约与 SQLite v9 迁移

**Files:**
- Modify: `backend/score_trans/models/history/entities.py`
- Modify: `backend/score_trans/models/history/schemas.py`
- Modify: `backend/score_trans/exec/history/actions.py`
- Modify: `backend/score_trans/services/history/history_service.py`
- Modify: `backend/score_trans/dao/history/history_dao.py`
- Test: `tests/test_history_atomic_save.py`
- Test: `tests/test_history_service.py`
- Test: `tests/test_history_snapshot.py`
- Test: `tests/test_api_routes.py`

**Interfaces:**
- Entity/response fields: `text_anchor_baseline_text: str = ""`, `text_anchor_baseline_anchors: list[TextAnchor]`.
- Request fields: matching `str | None = None` and `list[TextAnchor] | None = None`.

- [ ] 写失败测试：create/save/update 往返、v8→v9 加列、reorder 后基线不变、OpenAPI 请求可选/响应存在。
- [ ] 用 `.venv/Scripts/python.exe -m pytest` 运行目标测试确认失败。
- [ ] schema 升级到 9，新建表和迁移增加两列；DAO 所有读写路径贯通字段。
- [ ] actions 对旧请求缺失字段使用当前 page `jianpu_text`/`text_anchors` 兼容回退；service 透传可选更新。
- [ ] 保持 `reorder_pages` SQL 不包含 canonical 列。
- [ ] 运行目标 pytest 确认通过。

### Task 6: 契约再生成与全量验收

**Files:**
- Regenerate: `build/openapi.json`
- Regenerate: `desktop/src/renderer/src/models/openapi.ts`
- Verify: all modified files

**Interfaces:**
- OpenAPI generated names must match Task 4/5 exactly.

- [ ] 运行 `node scripts/export-openapi.mjs`，确认使用仓库 `.venv`。
- [ ] 运行本地 `openapi-typescript` 生成并 `--check`。
- [ ] 运行 `.venv/Scripts/python.exe -m ruff check backend tests` 与 format check。
- [ ] 运行 `.venv/Scripts/python.exe -m pytest`。
- [ ] 运行前端 `vue-tsc`、ESLint、全部 `node --test` 工具测试和 `electron-vite build`。
- [ ] 检查 `git diff --check`、迁移版本、字段命名和未关联用户修改。

