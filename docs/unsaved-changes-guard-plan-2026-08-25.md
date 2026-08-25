# 未保存更改守护与保存链路原子化设计方案

- 日期:2026-08-25
- 状态:已确认(含审查修订),待实施
- 范围:桌面端(Electron 渲染进程 + 主进程)+ 后端(FastAPI 历史模块)

## 1. 背景与目标

当前应用存在四类问题:

| 编号 | 问题 | 现状依据 |
|---|---|---|
| R1 | 编辑后无未保存提示,用户不知道改动是否已持久化 | "简谱编辑"标题(ConvertView.vue:308)旁无任何状态;脏标志 `currentBatchJianpuDirty` 已存在但只用于内部逻辑 |
| R2 | 关闭窗口(标题栏/Alt+F4/任务栏)不检查未保存更改,直接丢失 | 主进程 `mainWindow.close()` 无拦截(main/index.ts:136) |
| R3 | 重置/恢复历史版本会静默覆盖未保存的编辑 | `resetAll()`、`restoreJianpuSnapshot()` 无守卫 |
| S1 | 保存链路非原子且失败被静默吞掉:点"保存"必弹"已保存",但 `persistBatchJianpuText` 失败仅 `log.addLog(warn)`(ConvertView.vue:2136);保存 = 4~5 次串行 API,中途失败留半保存状态 | `persistRenderedHistory` 串行调用 page/batchText/renderPages/ocrTexts |

目标:

1. 编辑未保存时,"简谱编辑"右侧显示"当前有更改未保存"。
2. 未保存状态下关闭软件,弹出确认:**保存并关闭 / 直接关闭 / 取消**。
3. 未保存状态下重置或恢复历史版本,先弹确认,明确告知将丢弃修改。
4. 保存链路失败必须可见(不再假成功),且单次保存整体原子(全成或全不成)。

## 2. 决策记录

| # | 决策点 | 结论 |
|---|---|---|
| D1 | 多批次脏时点"保存并关闭" | **保存所有未保存批次**(当前批次完整保存,其余脏批次逐个持久化),全部成功才关闭;任一失败则不关窗并报错 |
| D2 | 改数据目录触发的 relaunch 重启 | **不弹窗,直接关闭**(主进程 relaunch 前置 forceClose 标志) |
| D3 | 提示位置与文案 | "简谱编辑"四字右侧,文案"当前有更改未保存",warning 色 |
| D4 | S1 修复方式 | **新建单一事务端点** `PATCH /history/{batch_id}/save-all`,一次请求完成整批持久化;同时交互保存路径错误必须上浮 |
| D5 | 快照来源标记 | save-all 请求带 `source`('save'/'reset'),快照在同一事务内写入(复用既有去重/裁剪逻辑) |
| D6 | save-all 的 stale 安全默认 | `render_output_stale` 默认 **True**(需重渲染);仅当前端显式提供 `render_page_file_ids`(渲染新鲜)时传 False。防"文本更新却标记渲染新鲜"的数据错误 |
| D7 | "未保存"判定与渲染 stale 解耦 | store 新增 `batchOcrUserEdited` + `batchAttachmentUserEdited` 两个独立标志;未保存 = 简谱文本脏 ∪ OCR 用户编辑 ∪ 文字附件编辑。**不得使用** `batchRenderPageOcrDirty`/`currentBatchRenderPageOcrDirty`(它们被加载态 stale 污染,见 3 节) |
| D8 | busy 状态下的关闭保存 | `store.isBusy` 时禁用"保存并关闭"按钮并提示"任务处理中";"直接关闭/取消"不受限 |
| D9 | 创建分支收敛 | 首次保存由 POST + 2 次 PATCH 收敛为**单次 POST**(`BatchCreateRequest` 本就接受 render 字段) |

历史决策(本功能前序,快照功能已实施):快照存新值、恢复不自动渲染、空文本也入库、每批次保留 3 条。

## 3. 现状事实(代码依据)

- 脏标志已存在:`workspace.ts` 的 `batchJianpuDirty`(全批次 map)、`currentBatchJianpuDirty`(当前批次 computed)、`batchRenderPageOcrDirty`(OCR 脏 map)、`jianpuDirty`(无批次兜底 ref)。
- 关闭链路:标题栏按钮 → `window.api.closeWindow()` → IPC `window:close` → `mainWindow.close()`。**Alt+F4/任务栏关闭绕过渲染进程**,必须在主进程 `close` 事件拦截。
- 视图挂载:App.vue 用 `v-show`(ConvertView 常驻),跨组件事件监听从启动即生效。
- 跨组件事件已有成熟模式:`utils/historyEvents.ts`(window CustomEvent + 返回清理函数)。
- 后端已有全局异常映射:`ValueError → 400`、`FileNotFoundError → 404`(api/app.py:169,176),exec 层抛标准异常即可。
- 首次保存(无 historyPageId)走 `POST /history`,后端 `create_batch` 本身就是单事务,天然原子;**非原子的只是更新路径**。
- `persistCorrectionState`(重置/标记修正共用)是 2 次串行调用(updatePage + updateBatchJianpuText),同样存在半保存风险。
- **审查发现的关键陷阱(OCR 脏标志语义污染)**:`isBatchRenderPageOcrDirty` 直接读 `batchRenderOutputStale`(workspace.ts:671-672),即"渲染过期"而非"用户编辑过";`loadBatch` 加载历史批次时把 DB 的 `render_output_stale=1` 灌进 OCR 脏 map(workspace.ts:1041 → `setBatchRenderPageOcrTexts` 的 `dirtyMap[i]=stale`,workspace.ts:628)。后果:加载"保存过文本但未重渲染"的批次(常见)→ 零编辑也判"未保存";且 `saveJianpu` 从不清 OCR 脏(仅 `renderFinalBatch` 清,ConvertView:1589)→ 保存后判定仍为真。**因此一切"未保存"判定必须基于新标志(D7),不得复用现有 OCR 脏 map。**
- 首次保存实际是 3 次请求:`POST /history` 后跟 `persistBatchRenderPages` + `persistBatchRenderPageOcrTexts`(ConvertView:2102-2103),而 `BatchCreateRequest` 已含 render 字段,可收敛。
- **二轮审查事实 1(OCR 渲染持久化)**:`renderFinalBatch` 成功后把渲染页与 OCR 文本持久化到历史库(ConvertView:1587-1588),即**重新渲染后 OCR 编辑已落库**;但 `markBatchRenderPageOcrClean`(1589)无条件执行(persist helper 吞错返回 void)。→ OCR 用户编辑标志的清除必须挂在"持久化成功"上,不能挂 1589。
- **二轮审查事实 2(文字附件编辑无脏标志)**:`handleTextAttachmentUpdate`(ConvertView:1963)只 `patchPageById({textAttachments})` + `setBatchRenderPageFileIds([])`,**不设任何脏标志**,且可作用于当前批次任意页(`currentBatchPages[sourcePageIndex]`)。
- **二轮审查事实 3(既有数据丢失缺陷)**:保存时仅当前页 `text_attachments` 进入 payload(`persistRenderedHistory` 的 `current_page`),其它页走 `persistOtherHistoryPageSections` **只持久化 jianpu_text**——非当前页的附件编辑"保存即丢"(今日既有 bug,本方案顺带修复,见 8.1 page_patches)。
- `persistRenderedHistory` 仅被 `saveJianpu` 调用(ConvertView:1930),迁移范围收敛;`markBatchRenderPageOcrClean` 仅在 `renderFinalBatch` 调用;其它批次 OCR 条目可经 `store.batchRenderPageOcrTextsFor(batchId)` 获取(workspace 导出,RecognizeView:1386 在用)。

## 4. 总体设计

四个子模块共用一套"脏状态"判定(D7,与渲染 stale 解耦):

```
workspace.ts 新增:
  batchOcrUserEdited: Record<batchId, boolean>   // 仅用户编辑 OCR 时置 true
  markBatchOcrUserEdited(batchId)                 // setBatchRenderPageOcrText(dirty=true) 内调用
  markBatchOcrSaved(batchId)                      // 保存成功后清
  currentBatchOcrUserEdited: computed             // 当前批次
  hasUnsavedChanges = computed(全部批次: 简谱脏 ∪ OCR 用户编辑 ∪ 无批次兜底 jianpuDirty)
```

- R1 提示:当前批次(`currentBatchJianpuDirty || currentBatchOcrUserEdited`)
- R3 守卫:同 R1
- R2 关闭:全部批次脏(`hasUnsavedChanges`),防止切批次后漏判
- S1 严格/宽松分层:
  - **严格(失败上浮,原子)**:交互保存(`saveJianpu`)、重置/标记修正持久化(`persistCorrectionState`)、关闭前保存
  - **宽松(保持 warn 日志)**:RecognizeView 后台自动保存、创建路径后的 store 状态同步、渲染流程内的持久化(`renderFinalBatch` 的 render-pages/ocr-texts 持久化,数据已随渲染落库,失败不丢数据)

## 5. R1 编辑面板未保存提示

ConvertView.vue 标题处(ConvertView.vue:308):

```html
<span>{{ isViewingFinal ? '最终渲染' : '简谱编辑' }}</span>
<span
  v-if="unsavedHintVisible"
  class="unsaved-hint"
>当前有更改未保存</span>
```

```ts
const unsavedHintVisible = computed(() =>
  store.currentBatchJianpuDirty || store.currentBatchOcrUserEdited,
)
```

样式:warning 色前缀圆点 + 10px 文字,与 `panel-filename` 同风格。编辑即亮(`setBatchJianpuText(dirty=true)` / `setBatchRenderPageOcrText(dirty=true)` 置新标志),保存成功即灭(`markBatchJianpuClean` + `markBatchOcrSaved`)。**注:最终渲染视图下同样显示**(OCR 文字层编辑也是未保存更改)。**加载"渲染过期"的历史批次不触发提示**(D7 解耦,这是与旧 OCR 脏 map 的关键区别)。

## 6. R2 关闭确认流程

### 6.1 主进程(main/index.ts)

```ts
let forceClose = false
let rendererCloseListenerReady = false

// createWindow 内:
mainWindow.on('close', (event) => {
  if (forceClose || !rendererCloseListenerReady) return  // 强关/未就绪 → 放行
  event.preventDefault()
  mainWindow?.webContents.send('app:confirm-close')
})

ipcMain.handle('window:force-close', () => {
  forceClose = true
  mainWindow?.close()
})
ipcMain.handle('app:close-listener-ready', () => { rendererCloseListenerReady = true })

// app:relaunch 改为(D2):
ipcMain.handle('app:relaunch', () => {
  forceClose = true   // 改数据目录重启不弹确认
  app.relaunch()
  app.quit()
})
```

要点:
- 拦截 `close` 事件,三路关闭(标题栏/Alt+F4/任务栏)全覆盖。
- `rendererCloseListenerReady` 防启动初期消息无处投递;渲染进程 onMounted 时置位。
- 重复触发 close(弹窗已开时再按 Alt+F4):preventDefault + 重发事件,渲染层幂等处理。

### 6.2 preload(index.ts + api.d.ts 自动获得类型)

新增三个方法:

```ts
forceCloseWindow(): Promise<void>            // invoke('window:force-close')
onConfirmClose(cb): () => void               // ipcRenderer.on('app:confirm-close')
notifyCloseListenerReady(): Promise<void>    // invoke('app:close-listener-ready')
```

### 6.3 渲染进程编排(App.vue)

- onMounted:`notifyCloseListenerReady()`
- `onConfirmClose` 处理器:

```ts
function handleConfirmClose(): void {
  if (closeConfirmVisible.value) return            // 幂等
  if (!store.hasUnsavedChanges) { void window.api.forceCloseWindow(); return }
  closeConfirmVisible.value = true
}
```

确认弹窗复用现有 `discardSettingsModal` 的 n-modal 模式,三按钮:

```
┌────────────────────────────────────────┐
│           有更改尚未保存               │
│   关闭前是否保存全部未保存的简谱修改?  │
│                                        │
│  [取消]   [直接关闭]   [保存并关闭]    │
└────────────────────────────────────────┘
```

- **取消**:仅关弹窗(close 已被 preventDefault,窗口仍在)
- **直接关闭**:`forceCloseWindow()`
- **保存并关闭**:按钮置 loading → `requestSaveAllBeforeClose()`(见 6.4)→ 成功 `forceCloseWindow()`;失败 `message.error('保存失败,已取消关闭')` + 保留窗口
- **busy 限制(D8)**:`store.isBusy` 时"保存并关闭"禁用并显示"任务处理中,完成后可保存";弹窗本身仍可"取消/直接关闭"

### 6.4 保存委托(新 util `utils/appCloseEvents.ts`)

仿 `historyEvents.ts` 的 CustomEvent + 请求序号模式:

```ts
requestSaveAllBeforeClose(): Promise<boolean>          // App.vue 调用,await 结果
listenRequestSaveAll(handler: () => Promise<boolean>)  // ConvertView 注册,返回清理函数
```

**防悬挂**:桥接层维护"已注册监听者"计数,`requestSaveAllBeforeClose` 派发时若无监听者(或派发后同步无响应标记),立即 `resolve(false)` 并 `console.warn`——绝不永久 pending。ConvertView 常驻(v-show),监听从启动即生效。

### 6.5 多批次保存(D1:保存所有未保存批次)

ConvertView 实现 `saveAllDirtyBatchesForClose(): Promise<boolean>`:

```
1. 当前批次脏(简谱 ∪ OCR 用户编辑)→ performJianpuSave()(完整保存,复用 S1 重构产物)
   成功后 markBatchOcrSaved + markBatchJianpuClean
   失败 → return false
2. 其余脏批次(简谱脏 ∪ OCR 用户编辑 的并集,排除当前批次)逐个:
   a. 已有 historyBatchId → save-all 单调用(D4):
      jianpu_text + page_texts(按分页标记拆分的各页文本)
      + (OCR 用户编辑时) render_page_ocr_texts;渲染页字段不传(D6 → stale 默认 True,正确标记需重渲染)
   b. 从未保存(无 historyBatchId)→ POST /history 创建
      (从 store.pages 组装该批次页面 + 批次文本按分页拆到各页;render 字段一并传入,D9)
   每批成功 → 清该批 dirty/ocrUserEdited 标志;失败 → log.addError + return false
3. 全部成功 → return true
```

要点:
- 每个批次一次原子调用,不存在跨批次半保存(批次间无法做事务,以"批次"为原子单位)。
- 保存当前批次复用 `performJianpuSave`,包含渲染页/OCR/标记修正上下文,与手动点保存完全一致。

## 7. R3 重置/恢复守卫

- App.vue 增加 `<n-dialog-provider>` 包裹根节点(现有 `n-message-provider` 内)。
- ConvertView 引入 `useDialog`,新增守卫:

```ts
function confirmDiscardUnsaved(action: '重置' | '恢复历史版本'): Promise<boolean> {
  if (!unsavedHintVisible.value) return Promise.resolve(true)  // 干净 → 直接过
  return new Promise((resolve) => {
    dialog.warning({
      title: '有更改尚未保存',
      content: `当前有更改未保存,${action}将丢弃这些修改,是否继续?`,
      positiveText: '继续',
      negativeText: '取消',
      maskClosable: false,          // 防 Promise 悬挂(审查修订 C)
      closable: false,
      onMaskClick: () => resolve(false),
      onEsc: () => resolve(false),
      onPositiveClick: () => resolve(true),
      onNegativeClick: () => resolve(false),
      onClose: () => resolve(false),
    })
  })
}
```

- `resetAll()` 开头:`if (!(await confirmDiscardUnsaved('重置'))) return`
- `restoreJianpuSnapshot()` 开头:`if (!(await confirmDiscardUnsaved('恢复历史版本'))) return`

守卫条件与 R1 提示同源(`unsavedHintVisible`),口径一致。

## 8. S1 保存链路原子化与失败可见化

### 8.1 后端:单一事务端点

**路由**:`PATCH /history/{batch_id}/save-all`(api/history/routes.py)

**Schema**(models/history/schemas.py):

```python
class BatchSavePageText(BaseModel):
    page_id: int
    jianpu_text: str = ""

class BatchSaveRequest(BaseModel):
    jianpu_text: str
    source: Literal["save", "reset"] = "save"
    current_page_id: int | None = None
    current_page: PageUpdate | None = None          # 当前页全量字段补丁
    page_texts: list[BatchSavePageText] = Field(default_factory=list)  # 其余页文本(重复 page_id → ValueError)
    render_page_file_ids: list[str] | None = None   # None = 不修改
    render_layout_key: str | None = None            # None = 不修改
    render_page_ocr_texts: list[RenderPageOcrText] | None = None  # None = 不修改
    render_output_stale: bool = True                # D6:安全默认=需重渲染;提供渲染页且新鲜时显式传 False
```

**stale 语义(审查修订 B)**:凡 `render_page_file_ids` 未提供(只改文本)→ `render_output_stale` 按请求值落库(默认 True),与现有 `update_batch_jianpu_text` 无条件置 1 的语义对齐——防止"文本已更新、渲染标记新鲜、加载显示旧渲染"的数据错误。

响应:`BatchResponse`(与现有 PATCH 一致)。

**DAO**(history_dao.py 新增 `save_batch`,单事务):

```python
def save_batch(self, batch_id, *, jianpu_text, source="save",
               current_page_id=None, current_page_fields=None,
               page_texts=None, render_page_file_ids=None,
               render_layout_key=None, render_page_ocr_texts=None,
               render_output_stale=False) -> HistoryBatch | None:
    with self._connect() as conn:
        # 0) 批次不存在 → None(→404);current_page_id / page_texts 任一页
        #    不属于该批次 → ValueError(→400),此时零写入(原子性由异常回滚保证)
        # 1) UPDATE history_batch SET jianpu_text=?, render_output_stale=?
        # 2) 可选:render_page_file_ids / render_page_ocr_texts(None 不动)
        # 3) 可选:当前页动态 UPDATE(复用 update_page 的字段拼装逻辑,抽公共 helper)
        # 4) page_texts 批量 UPDATE history_page SET jianpu_text=?
        # 5) 快照写入(去重 + 插入 + 裁剪到 3 条,与 push_snapshot 同逻辑,同事务)
        conn.commit()
        return self._row_to_batch(conn, refreshed_row)
```

原子性依据:全部 UPDATE 在同一 `with self._connect()` 事务内,任一步抛异常(校验失败/SQLite 错误)→ 整体回滚,不留半保存状态。

**Service / Actions / Routes**:照三层惯例转发;actions 校验缺失批次抛 `FileNotFoundError`(→404),非法页归属抛 `ValueError`(→400),复用全局异常处理器,不新增 HTTPException。

### 8.2 前端:调用收敛与错误上浮

- `pnpm generate:api-types` 重生契约,contracts.ts/types.ts 补 `HistoryBatchSaveRequest` 别名,history.ts 加 `saveBatch(id, req)`。
- **`persistRenderedHistory` 更新分支收敛为单次 `saveBatch` 调用**:
  - 组装 `current_page_id` + `current_page`(现 payload 不变)+ `page_texts`(吸收原 `persistOtherHistoryPageSections` 的分页拆分逻辑,只拆文本不再逐页发请求;**其对 store 的 `patchPageById` 分节同步保留在客户端**,仅收敛 API 调用)+ render 字段 + OCR 文本 + 显式 `render_output_stale`(传 `store.currentBatchRenderOutputStale`)
  - 删除 `persistOtherHistoryPageSections`、更新分支内的 `persistBatchRenderPages`/`persistBatchRenderPageOcrTexts`/`persistBatchJianpuText` 串行调用
- **创建分支收敛为单次 POST(D9)**:render_page_file_ids/render_page_ocr_texts/render_output_stale/render_layout_key 直接并入 `historyApi.create` 请求(`BatchCreateRequest` 已有这些字段),删除创建后的两次 PATCH;其后的 store 同步调用维持宽松(数据已落库,失败仅影响内存态)。`renderFinalBatch` 内的 `persistBatchRenderPages`/`persistBatchRenderPageOcrTexts` 调用保留(渲染流程持久化,宽松层)
- **`persistCorrectionState`(重置/标记修正)迁移到 save-all**:
  - 重置:`jianpu_text=nextBatchText, source='reset', current_page=<页面补丁>, page_texts=[]`(其余页不动)
  - 标记修正:`source='save'`,同构
  - 由此重置路径同样获得原子性,且失败必然上浮到 `resetAll`/`applyCorrection` 的既有 catch → 错误 toast
- **`persistBatchJianpuText` 删除**(两个调用方均已迁移;RecognizeView 后台保存是直接调 API,不受影响,维持宽松 warn——后台语义正确)
- **`saveJianpu` 重构**:

```ts
async function performJianpuSave(): Promise<boolean> {
  // 原 saveJianpu 主体,失败 toast 并 return false,成功 return true
}
async function saveJianpu(): Promise<void> {
  if (!canSaveCurrentPage.value) { message.warning('暂无可保存内容'); return }
  store.setBusy(true)
  try {
    if (await performJianpuSave()) {
      store.markBatchJianpuClean()
      store.markBatchOcrSaved()      // 审查修订 A:保存成功清 OCR 用户编辑标志
      message.success('已保存')      // 只有真正成功才提示
    }
    // 失败:performJianpuSave 已 toast,dirty 保持 → R1 提示仍亮
  } finally { store.setBusy(false) }
}
```

`performJianpuSave` 同时是 6.5 关闭保存的当前批次入口。

### 8.3 修复后的行为对照

| 场景 | 修复前 | 修复后 |
|---|---|---|
| 批次文本写库失败 | 静默 warn,弹"已保存"(假成功) | 保存失败 toast,不弹成功,提示仍亮 |
| 保存中途异常 | 部分字段已写,状态不一致 | 整体回滚,与保存前完全一致 |
| 快照与文本不一致 | 快照可能先于失败写入 | 同事务,快照=文本,不可能脱节 |
| 重置持久化失败 | 静默 warn | "重置失败" toast |

## 9. 触及文件清单

**后端(4 + 测试 1)**
| 文件 | 改动 |
|---|---|
| `models/history/schemas.py` | `BatchSavePageText`、`BatchSaveRequest` |
| `dao/history/history_dao.py` | `save_batch` 单事务方法 + 抽取页更新拼装 helper |
| `services/history/history_service.py` | 转发 |
| `exec/history/actions.py` | `save_batch` action(校验/异常) |
| `api/history/routes.py` | `PATCH /{batch_id}/save-all` |
| `tests/test_history_save_batch.py`(新增) | 原子性/归属校验/快照同事务/None 不动/404 |

**主进程 + preload(2)**
| 文件 | 改动 |
|---|---|
| `desktop/src/main/index.ts` | close 拦截、force-close/ready IPC、relaunch 置 forceClose |
| `desktop/src/preload/index.ts` | `forceCloseWindow` / `onConfirmClose` / `notifyCloseListenerReady` |

**渲染进程(6)**
| 文件 | 改动 |
|---|---|
| `utils/appCloseEvents.ts`(新增) | 保存请求/结果事件桥(含无监听者防悬挂) |
| `stores/workspace.ts` | `batchOcrUserEdited` 标志族 + `hasUnsavedChanges` computed |
| `App.vue` | n-dialog-provider、关闭确认弹窗、confirm-close 编排、ready 上报 |
| `views/ConvertView.vue` | R1 提示、R3 守卫、performJianpuSave 重构、persistRenderedHistory/persistCorrectionState 迁移 save-all、saveAllDirtyBatchesForClose、删除 persistBatchJianpuText/persistOtherHistoryPageSections |
| `api/history.ts` | `saveBatch` |
| `models/openapi.ts` + `contracts.ts` + `types.ts` | 契约重生成 + 别名 |

## 10. 实施顺序

1. **S1 后端**:schemas → dao(save_batch + helper)→ service → actions → routes → pytest 全绿
2. **契约**:`pnpm generate:api-types` → `pnpm check:api-types` 绿
3. **S1 前端**:history.ts `saveBatch` → ConvertView 迁移(persistRenderedHistory/persistCorrectionState/saveJianpu 重构、删旧 helper)→ typecheck/lint
4. **R1**:标题提示(最小改动)
5. **R3**:n-dialog-provider + confirmDiscardUnsaved 守卫接入 resetAll/restoreJianpuSnapshot
6. **R2**:主进程拦截 + preload + appCloseEvents + App.vue 编排 + ConvertView 关闭保存
7. 全量验证(见 11)

## 11. 验证矩阵

**自动化**
- 后端:`python -m pytest` 全量(新增 save_batch 测试);`ruff check/format`
- 前端:`pnpm typecheck`、`pnpm lint`、`pnpm check:api-types`

**手测**
| 用例 | 期望 |
|---|---|
| 编辑文本 | "简谱编辑"右侧立即出现"当前有更改未保存" |
| 编辑最终视图 OCR 文字层 | 同样出现提示 |
| 点保存(成功) | 提示消失,弹"已保存" |
| **加载"渲染过期"的历史批次(未编辑)** | **不出现提示**(D7 解耦验证) |
| 模拟保存失败(停后端再保存) | 弹"保存失败",**不弹"已保存"**,提示仍亮 |
| 编辑后标题栏关闭 | 弹三按钮确认窗 |
| 编辑后 Alt+F4 / 任务栏关闭 | 同上(三路全覆盖) |
| 确认窗-取消 | 窗口保留,提示仍亮 |
| 确认窗-直接关闭 | 立即退出 |
| 确认窗-保存并关闭(脏批次 A+B) | A、B 均落库(历史里查得到)后退出 |
| 保存并关闭-某批次失败 | 报错不关窗,脏提示保持 |
| **busy(后台渲染中)点关闭** | "保存并关闭"禁用并提示任务处理中 |
| 干净状态直接关闭 | 无弹窗直接退出 |
| 设置页改数据目录(重启) | 不弹确认直接重启(D2) |
| 脏状态点重置 | 弹"有更改尚未保存…是否继续" |
| **脏状态点重置确认窗的遮罩/Esc** | **等同取消,重置不执行,无悬挂** |
| 脏状态点恢复历史版本 | 弹确认;取消后编辑内容原样保留 |
| 干净状态重置/恢复 | 无弹窗,行为同现在 |
| 保存后快照列表 | 新快照与文本一致(同事务) |
| **只改文本保存(未重渲染)后重新加载该批次** | **stale=1,自动重渲染**(D6 验证) |

## 12. 边界与已知限制

- **渲染进程挂死时窗口关不掉**(confirm-close 无人响应):暂不加超时强关(超时强杀可能截断正当的慢保存);极端情况用任务管理器。可作后续增强(如 10s 无响应放行)。
- **dev 热重载间隙**:开发态热重载后、App 重新挂载前,`rendererCloseListenerReady` 仍为 true 但监听未注册,此时关闭窗口会发送无人接收的 confirm-close(窗口暂不关闭,再次点击即恢复)。仅影响开发模式,生产无此路径。
- **OS 关机/注销被 close 拦截**:Windows 会在超时后强制结束进程,未保存编辑可能丢失(与 VSCode 等应用同类行为)。可作后续增强(监听 session-end 直接待遇)。
- **识别任务进行中关闭**:后端进程随应用退出被杀,任务中断——既有行为,不在本方案范围(后台任务已有历史状态持久化)。
- **"合入识别结果"pending 页**不属于"未保存编辑"(是待合并的识别产物,有独立交互),不纳入脏判定。
- **跨批次无事务**:多批次保存以"批次"为原子单位,批次 A 成功、批次 B 失败时 A 已落库——但关闭被阻止,用户可重试,无数据丢失。
- **后台 auto 保存失败仍为 warn 日志**(RecognizeView):后台语义,无用户动作可失败,维持现状。
- 平台:仅 Windows(项目现状)。

## 13. 审查修订记录(2026-08-25)

| 编号 | 级别 | 问题 | 修订 |
|---|---|---|---|
| A | 严重 | OCR 脏标志被加载态 stale 污染(workspace.ts:671/628/1041),`saveJianpu` 不清 OCR 脏 → R1/R2/R3 全部误报(零编辑提示未保存、保存后提示不灭) | 新增 `batchOcrUserEdited` 独立标志族,未保存判定与渲染 stale 解耦(D7);保存成功清标志 |
| B | 严重 | save-all `render_output_stale` 默认 False → 只改文本的保存会把旧渲染标记为新鲜,加载显示旧渲染 | 默认改 True,显式提供渲染页时才传 False(D6) |
| C | 严重 | Naive dialog 默认 mask/Esc 可关 → R3 守卫 Promise 悬挂 | `maskClosable/closable: false` + onMaskClick/onEsc/onClose 兜底 resolve(false) |
| D | 中 | 关闭保存绕过保存按钮的 isBusy 守卫,与后台任务并发写 | busy 时禁用"保存并关闭"(D8) |
| E | 中 | `requestSaveAllBeforeClose` 无监听者时永久 pending | 桥接层检测无监听者 → resolve(false) + warn |
| F | 中 | 首次保存为 POST + 2 PATCH,非单请求 | 创建分支收敛为单次 POST(D9) |
| G | 低 | dev 热重载 ready 间隙 | 记录限制,接受 |
| H | 低 | OS 关机被拦截 → 强杀丢编辑 | 记录限制,接受 |
| I | 低 | `persistOtherHistoryPageSections` 的客户端分节同步需保留 | 已在 8.2 明确:仅收敛 API 调用 |
