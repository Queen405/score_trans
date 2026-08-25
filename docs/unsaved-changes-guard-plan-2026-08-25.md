# 未保存更改守护与保存链路原子化 — 实现记录(as-built)

- 日期:2026-08-25(方案)→ 同日实现并合入
- 状态:**已实现**(分支 v1.0.0;主要 commit:`5cc0066` 原子保存与关闭协调、`402fe41` 历史版本快照、`521a576` 智能合并、`404122a` 文本锚点基线/schema v9)
- 范围:桌面端(Electron 渲染进程 + 主进程)+ 后端(FastAPI 历史模块,SQLite schema v9)

> 本文档原为实施前方案,现已按实际代码(as-built)修订为设计与实现记录。方案与实现的差异见第 4 节;两轮审查的发现与修订见附录 A。

## 1. 背景与需求

| 编号 | 需求/问题 | 实现位置 |
|---|---|---|
| R1 | 编辑未保存时,"简谱编辑"右侧提示"当前有更改未保存" | ConvertView.vue `unsaved-hint`(约 312 行) |
| R2 | 未保存状态下关闭软件(标题栏/Alt+F4/任务栏)弹出确认:保存并关闭 / 直接关闭 / 取消 | main/index.ts `close` 拦截 + App.vue 确认弹窗 |
| R3 | 未保存状态下重置/恢复历史版本,先确认将丢弃修改 | ConvertView.vue `confirmDiscardUnsaved`(1745/2117/2150) |
| S1 | 保存链路原子化(失败不留半保存状态)、失败可见(不假成功) | 后端 `PATCH /history/{id}/save-all` 单事务 |

## 2. 决策记录(按实现校准)

| # | 决策点 | 最终结论 |
|---|---|---|
| D1 | 多批次脏时"保存并关闭" | 保存**全部**未保存批次,当前批次优先;全部成功后复查 `hasUnsavedChanges`,保存期间有新编辑则抛错取消关闭(workspacePersistence.ts:145-159) |
| D2 | 改数据目录触发的重启 | **已修正**:relaunch 不再绕过确认——作为 `CloseIntent='relaunch'` 走同一确认流,弹窗文案按意图适配("已取消重启");批准后 `approveWindowClose('relaunch')` 才 `app.relaunch()`(main/index.ts:294-297)。比原方案(直接 forceClose 绕过)更保护未保存编辑 |
| D3 | 提示位置与文案 | "简谱编辑"右侧,文案"当前有更改未保存",warning 色前缀圆点 |
| D4 | 保存链路修复方式 | 单一事务端点 `PATCH /history/{batch_id}/save-all`;**实现采用全页完整快照**(每页全字段),而非方案中的部分补丁——更强,天然覆盖附件/OCR 持久化 |
| D5 | 快照来源标记 | `source`: 'save' / 'reset' / 'auto'(auto 不写快照);快照与文本在**同一事务**写入(`_push_snapshot_locked`) |
| D6 | render stale 语义 | 实现为 `BatchRenderStateUpdate` 的 Pydantic `model_validator`:渲染标记为新鲜时必须提供 `render_page_file_ids`,OCR page_index 唯一非负(schemas.py:123-134);提供渲染页时条件更新 engine_version/layout_key(dao:545-546)。比方案的"默认 True"更强的契约约束 |
| D7 | "未保存"判定与渲染 stale 解耦 | 实现为 **revision 状态机**(见 3.1),而非方案中的布尔标志——顺带修复了方案未覆盖的"保存期间新编辑被误清"竞态 |
| D8 | busy 时的关闭保存 | "保存并关闭"在 `saveBeforeCloseBlocked` 时禁用(App.vue:458) |
| D9 | 创建分支收敛 | `buildBatchPersistenceSnapshot` 统一构建 create/update 请求,创建即含 render 字段(historySavePayload.ts) |

## 3. 实现架构(as-built)

### 3.1 脏状态:revision 状态机(utils/unsavedChangeState.ts)

每批次维护 `BatchRevisionState { edited, saved }`,对三类变更分别计数:`jianpu` / `ocr` / `attachments`。

- `markEdited`:用户编辑时递增对应 kind 的 `edited`
- `captureEditedRevision` / `acknowledgeRevision`:保存前捕获版本快照,**成功后只 acknowledge 到捕获点**——保存期间产生的新编辑不会被误清(竞态安全,这是相对布尔标志的核心优势)
- `hasUnsavedChanges(state)` = 任一 kind `edited > saved`
- store 集成(workspace.ts):`batchUserChangeRevisions` map;`isBatchUnsaved` / `isBatchChangeKindUnsaved`;`hasUnsavedChanges` 聚合全部批次(无批次兜底 `jianpuDirty`);`currentBatchOcrUserEdited` / `currentBatchAttachmentUserEdited` computed

**关键约束(审查修订 A/D7)**:OCR/附件判定独立于渲染 stale——禁止用 `batchRenderPageOcrDirty`(它读 `batchRenderOutputStale`,会被加载历史时的 stale=1 污染,造成零编辑也误报)。

### 3.2 R1 编辑面板提示

ConvertView.vue 面板标题"简谱编辑"右侧,`currentBatchHasUnsavedChanges` 为真时显示 `unsaved-hint`(warning 色圆点 + 文案)。加载"渲染过期"的历史批次不误报(D7);编辑即亮、保存/渲染持久化成功即灭(渲染持久化仅 acknowledge `ocr` kind,见 3.4)。

### 3.3 R2 关闭协调(三路关闭全覆盖)

**主进程**(main/closeCoordinator.ts + index.ts):

```
mainWindow.on('close'):
  allowWindowClose → 放行
  渲染进程不可用(未就绪/已销毁)→ confirmCloseWithoutRenderer()(原生 dialog:
      "界面进程当前不可用,未保存的更改可能丢失,是否仍要直接退出?")→ 通过则 approveWindowClose
  否则 → closeCoordinator.request(intent)(重复请求去重,同一 pending 不重复发)
      → webContents.send('app:close-requested', { requestId, intent })
ipcMain.on('app:resolve-close') → coordinator.resolve(requestId, decision)
  → proceed 时 approveWindowClose(intent)(relaunch 时 app.relaunch())
```

- 渲染进程就绪管理:`did-start-loading` / `render-process-gone` 重置 ready 标志;`rendererWasReady` 恢复后重发 pending 请求(main/index.ts:81-86, 178-183)——热重载/崩溃场景均有兜底
- intent:`closeWindow()` 传 'close',`relaunchApp()` 传 'relaunch'(preload:32/67)

**渲染进程**(App.vue):

- `processCloseRequest`:无脏 → 直接 `resolveCloseRequest(requestId, 'proceed')`;有脏 → 弹三按钮确认窗
- **保存并关闭**:`workspacePersistence.saveAllUnsavedBatches(store)` → 成功 proceed;失败显示错误(`closeSaveError`,文案按 intent 适配"取消关闭/取消重启")并保留窗口
- **直接关闭** / **取消**:对应 proceed / cancel

### 3.4 多批次保存(utils/workspacePersistence.ts)

注入式纯编排层(可测,见 test-workspace-persistence.mjs):

- `saveBatch(store, batchId, source, overrides)`:捕获 revision → `buildBatchPersistenceSnapshot`(依据 pages 的 historyBatchId 一致性选择 create/update;historySavePayload.ts)→ 单次请求 → 回写 store(historyPageId、`text_anchor_baseline_*`、render 状态)→ `acknowledgeBatchChanges(captured)` → `notifyHistoryUpdated()`
- `saveAllUnsavedBatches(store)`:收集所有 `isBatchUnsaved` 批次(当前批次置前),逐个 `saveBatch`,完成后复查 `hasUnsavedChanges`(有新编辑 → 抛错取消关闭)
- `saveRenderState(store, batchId, state)`:`PATCH /render-state` 更新渲染状态,**仅 acknowledge `ocr` kind**——渲染流程持久化只兑现 OCR 编辑,简谱/附件仍需保存

### 3.5 R3 重置/恢复守卫

ConvertView.vue `confirmDiscardUnsaved('重置' | '恢复历史版本')`(约 2150 行):干净直接放行;脏则 `dialog.warning` 确认(继续/取消;`maskClosable/closable: false` + onMaskClick/onEsc/onClose 全兜底 resolve,防 Promise 悬挂——审查修订 C)。守卫接入 `resetAll()`(1745)与 `restoreJianpuSnapshot()`(2117)开头。

### 3.6 S1 后端原子保存

**`PATCH /history/{batch_id}/save-all`**(routes.py:99):
- `BatchSaveRequest(BatchRenderStateUpdate)`:`jianpu_text` + `source` + `pages: list[BatchSavePage]`(**全页完整快照**:每页含 jianpu_text/ocr_text/text_attachments/svg/锚点/`text_anchor_baseline_*` 等全字段)+ render 状态
- 校验:`render_state` 必须自洽(validator);"pages 必须恰好为该批次的全部页且每页仅一次",缺/重/越界页 → `ValueError` → 400 且**零写入**

**DAO `save_batch`**(history_dao.py:496):`BEGIN IMMEDIATE` 单事务内——归属校验 → `_save_page_locked` 逐页全量更新 → 批次更新(jianpu_text/render 状态/条件更新 engine_version 与 layout_key)→ `_refresh_batch_status` → `_push_snapshot_locked` 同事务写快照(去重+裁剪 3 条)→ 任一失败整体回滚。`update_page`/`push_snapshot` 已重构为 conn 级 helper(`_apply_page_updates`/`_push_snapshot_locked`),独立调用行为不变。

**渲染流程**:`PATCH /history/{batch_id}/render-state`(routes.py:108)专供渲染后持久化渲染页与 OCR 文本层。

**快照**:`GET /history/{batch_id}/jianpu-snapshots`(最多 3 条,save/reset/auto 来源;auto 不写快照,用于后台识别自动保存)。

**创建路径**:`POST /history` 单事务不变;前端创建请求即含 render 字段(D9)。

### 3.7 与智能合并/锚点基线的交互(521a576 / 404122a)

schema v9 新增 `history_page.text_anchor_baseline_text/anchors`(迁移回填 = jianpu_text/text_anchors,dao:895-908)。`saveBatch` 成功后回写页面锚点基线(workspacePersistence.ts:118-128),供"恢复检测"与**手动编辑与生成修正的智能合并**(`preserveEditedJianpuText`)使用。schema 版本当前为 **v9**(注意 commit 消息中"MySQL"为笔误,实为 SQLite `user_version`)。

## 4. 方案 vs 实现差异表

| 方案设计 | 实际实现 | 评估 |
|---|---|---|
| 布尔脏标志(D7) | revision 状态机(edited/saved 计数器 + capture/acknowledge) | **更优**:修复方案未覆盖的"保存期间新编辑被误清"竞态 |
| save-all 部分补丁(current_page + page_patches) | 全页完整快照 `pages[]` + "恰好全部页"校验 | **更强**:天然覆盖非当前页附件/OCR 持久化(修复了审查修订 R 所指既有缺陷),契约更清晰 |
| D2:relaunch 时 forceClose 绕过确认 | relaunch 作为 `CloseIntent` 走同一确认流,文案按意图适配 | **更安全**(改变了原 D2 决策);若未来想绕过,主进程侧放行即可 |
| ready 标志 + 无兜底 | ready/wasReady + 渲染不可用时原生 dialog 兜底 + 恢复重发 | 修复了原方案限制 G(热重载间隙)并覆盖渲染崩溃 |
| 事件桥 appCloseEvents.ts 委托保存 | App.vue 直接调 `workspacePersistence.saveAllUnsavedBatches(store)` | **更简洁**:注入式编排层无跨组件事件桥,且独立可测 |
| R3 守卫 Naive useDialog | 一致(useDialog + 防悬挂参数) | 按方案 |
| 快照 save/reset/auto | 一致(auto 跳过),save-all 中同事务写入 | 按方案并增强(原子性) |

## 5. 测试资产

- 后端:`tests/test_history_atomic_save.py`(完整快照+快照记录、越界页零写入回滚、页集合校验、写失败整体回滚)、`tests/test_history_snapshot.py`(快照滚动/去重/来源/级联)
- 前端(node:test):`test-close-coordinator.mjs`、`test-unsaved-change-state.mjs`、`test-workspace-persistence.mjs`、`test-history-save-payload.mjs`、`test-workspace-batch-cleanup.mjs`、`test-frontend-lifecycle.mjs`、`test-backend-lifecycle.mjs`
- 验证命令:后端 `python -m pytest` 全量;前端 `pnpm typecheck` / `pnpm lint` / `pnpm check:api-types` / 工具测试

## 6. 已知限制(现状)

- **OS 关机/注销被 close 拦截**:Windows 超时强杀可能丢编辑(与同类应用一致);可后续监听 session-end。
- **识别任务进行中关闭**:后端随应用退出被杀,任务中断(既有行为)。
- **跨批次无事务**:以批次为原子单位;`saveAllUnsavedBatches` 保存期间有新编辑会整体取消关闭(D1 复查)。
- **同一历史批次被两次加载**:两个前端批次指向同一 historyBatchId 且都脏时,逐批保存,后者覆盖前者(罕见边角)。
- **渲染进程崩溃/挂起**:主进程原生 dialog 兜底询问是否直接退出(已覆盖,不再挂死)。

## 附录 A:方案期两轮审查修订记录(历史,保留以解释设计约束)

**第一轮(2026-08-25)**:

| 编号 | 级别 | 问题 | 处置 |
|---|---|---|---|
| A | 严重 | OCR 脏标志被加载态 stale 污染(workspace.ts 旧 map),保存后不清 → 全功能误报 | D7:判定与 stale 解耦(实现升级为 revision 状态机) |
| B | 严重 | save-all stale 默认 False → 只改文本会把旧渲染标新鲜 | 实现为 validator:新鲜必须带 render ids(D6) |
| C | 严重 | Naive dialog 默认可遮罩/Esc 关闭 → 守卫 Promise 悬挂 | maskClosable/closable=false + 全兜底 resolve |
| D | 中 | 关闭保存绕过 busy 守卫,与后台任务并发写 | D8:busy 时禁用"保存并关闭" |
| E | 中 | 保存委托无监听者悬挂 | 实现取消事件桥,App.vue 直接调用,天然无此问题 |
| F | 中 | 首次保存 3 次请求 | D9:创建即含 render 字段,单次 POST |
| G/H/I | 低 | 热重载间隙 / OS 关机 / 分节同步保留 | G 已修复;H 记录;I 已被全页快照取代 |

**第二轮(2026-08-25)**:

| 编号 | 级别 | 问题 | 处置 |
|---|---|---|---|
| J | 中高 | 重渲染已持久化 OCR 但标志不清 → 关窗假阳性 | 实现:`saveRenderState` 仅 acknowledge 'ocr',且以持久化成功为前提 |
| K | 中 | 文字附件编辑无脏标志 → 不可见 | 实现:revision 三类之一 `attachments`,`handleTextAttachmentUpdate` 置位 |
| L | 低 | 单事务需 conn 级 helper | 实现:`_apply_page_updates`/`_push_snapshot_locked` |
| M | 低 | resetAll 成功后清 OCR/附件标志;restore 不清 | 实现:reset 走 save-all(source='reset')后 acknowledge |
| N | 低 | saveJianpu 须总带全量 OCR 条目 | 实现:`buildBatchPersistenceSnapshot` 统一组装 |
| O | 低 | 旧 `PATCH /jianpu-text` 双快照路径 | 保留:auto 不写快照;save-all 为唯一快照写入口 |
| P/Q | 低 | 同批次双前端实例 / 模态叠加 | 记录限制 |
| R | 中 | 部分补丁沿袭"非当前页附件保存即丢" | 实现为全页快照,顺带修复 |
