import type { ApiResult } from '../api/client'
import type {
  HistoryBatch,
  HistoryBatchRenderStateUpdateRequest,
  HistoryBatchSaveRequest,
  HistoryCreateRequest,
  RenderPageOcrText,
} from '../models/types'
import type { TaskPage } from '../stores/workspace'
import type { ChangeRevision, UserChangeKind } from './unsavedChangeState'
import { buildBatchPersistenceSnapshot } from './historySavePayload'

export interface WorkspacePersistenceClient {
  saveBatch(id: number, request: HistoryBatchSaveRequest): Promise<ApiResult<HistoryBatch>>
  create(request: HistoryCreateRequest): Promise<ApiResult<HistoryBatch>>
  updateRenderState(
    id: number,
    request: HistoryBatchRenderStateUpdateRequest,
  ): Promise<ApiResult<HistoryBatch>>
}

export interface WorkspacePersistenceStore {
  pages: TaskPage[]
  currentBatchId: string | null
  hasUnsavedChanges: boolean
  batches: Array<{ id: string; pages: TaskPage[] }>
  batchRenderPageFileIds: Record<string, string[]>
  batchRenderOutputStale: Record<string, boolean>
  batchRenderLayoutKeys: Record<string, string>
  batchJianpuTextFor(batchId: string): string
  batchRenderPageOcrTextsFor(batchId: string): RenderPageOcrText[]
  captureBatchChangeRevision(batchId: string): ChangeRevision
  acknowledgeBatchChanges(
    captured: ChangeRevision,
    kinds: readonly UserChangeKind[] | undefined,
    batchId: string,
  ): void
  isBatchUnsaved(batchId: string): boolean
  patchPageById(pageId: string, patch: Partial<TaskPage>): boolean
  setBatchRenderPageFileIds(
    fileIds: string[],
    batchId: string,
    layoutKey?: string,
  ): void
  setBatchRenderPageOcrTexts(
    items: RenderPageOcrText[],
    stale: boolean,
    batchId: string,
  ): void
}

export interface RenderStateSnapshot {
  renderPageFileIds: string[]
  renderPageOcrTexts: RenderPageOcrText[]
  renderOutputStale: boolean
  renderLayoutKey: string
}

export interface BatchSaveOverrides {
  pages?: TaskPage[]
  jianpuText?: string
  renderPageFileIds?: string[]
  renderPageOcrTexts?: RenderPageOcrText[]
  renderOutputStale?: boolean
  renderLayoutKey?: string
}

function unwrap<T>(result: ApiResult<T>): T {
  if (result.error) throw result.error
  return result.data
}

function historyBatchIdForPages(pages: TaskPage[]): number | null {
  const ids = new Set(
    pages
      .map((page) => page.historyBatchId)
      .filter((id): id is number => id !== null),
  )
  return ids.size === 1 && pages.every((page) => page.historyBatchId !== null)
    ? [...ids][0]!
    : null
}

export function createWorkspacePersistence(
  client: WorkspacePersistenceClient,
  notifyHistoryUpdated: () => void = () => {},
) {
  async function saveBatch(
    store: WorkspacePersistenceStore,
    batchId: string,
    source: 'save' | 'reset' = 'save',
    overrides: BatchSaveOverrides = {},
  ): Promise<HistoryBatch> {
    const localPages = store.pages.filter((page) => page.batchId === batchId)
    const pages = overrides.pages ?? localPages
    const captured = store.captureBatchChangeRevision(batchId)
    const snapshot = buildBatchPersistenceSnapshot({
      pages,
      jianpuText: overrides.jianpuText ?? store.batchJianpuTextFor(batchId),
      renderPageFileIds: overrides.renderPageFileIds ?? store.batchRenderPageFileIds[batchId] ?? [],
      renderPageOcrTexts: overrides.renderPageOcrTexts ?? store.batchRenderPageOcrTextsFor(batchId),
      renderOutputStale: overrides.renderOutputStale ?? store.batchRenderOutputStale[batchId] ?? true,
      renderLayoutKey: overrides.renderLayoutKey ?? store.batchRenderLayoutKeys[batchId] ?? '',
      source,
    })
    const saved = snapshot.kind === 'update'
      ? unwrap(await client.saveBatch(snapshot.historyBatchId, snapshot.request))
      : unwrap(await client.create(snapshot.request))

    for (let index = 0; index < localPages.length; index += 1) {
      const localPage = localPages[index]
      const savedPage = snapshot.kind === 'update'
        ? saved.pages.find((page) => page.id === localPage?.historyPageId)
        : saved.pages[index]
      if (!localPage || !savedPage) continue
      store.patchPageById(localPage.id, {
        historyPageId: savedPage.id,
        historyBatchId: saved.id,
        jianpuText: savedPage.jianpu_text,
      })
    }
    store.setBatchRenderPageFileIds(
      saved.render_page_file_ids ?? [],
      batchId,
      saved.render_layout_key ?? '',
    )
    store.setBatchRenderPageOcrTexts(
      saved.render_page_ocr_texts ?? [],
      saved.render_output_stale ?? true,
      batchId,
    )
    store.acknowledgeBatchChanges(captured, undefined, batchId)
    notifyHistoryUpdated()
    return saved
  }

  async function saveAllUnsavedBatches(
    store: WorkspacePersistenceStore,
  ): Promise<void> {
    const ids = store.batches
      .map((batch) => batch.id)
      .filter((batchId) => store.isBatchUnsaved(batchId))
    if (store.currentBatchId && ids.includes(store.currentBatchId)) {
      ids.splice(ids.indexOf(store.currentBatchId), 1)
      ids.unshift(store.currentBatchId)
    }
    for (const batchId of ids) await saveBatch(store, batchId)
    if (store.hasUnsavedChanges) {
      throw new Error('New edits were made while saving; close was cancelled')
    }
  }

  async function saveRenderState(
    store: WorkspacePersistenceStore,
    batchId: string,
    state: RenderStateSnapshot,
  ): Promise<HistoryBatch | null> {
    const pages = store.pages.filter((page) => page.batchId === batchId)
    const historyBatchId = historyBatchIdForPages(pages)
    if (!historyBatchId) return null
    const captured = store.captureBatchChangeRevision(batchId)
    const saved = unwrap(await client.updateRenderState(historyBatchId, {
      render_page_file_ids: state.renderPageFileIds,
      render_page_ocr_texts: state.renderPageOcrTexts,
      render_output_stale: state.renderOutputStale,
      render_layout_key: state.renderPageFileIds.length ? state.renderLayoutKey : '',
    }))
    store.setBatchRenderPageFileIds(
      saved.render_page_file_ids ?? [],
      batchId,
      saved.render_layout_key ?? '',
    )
    store.setBatchRenderPageOcrTexts(
      saved.render_page_ocr_texts ?? [],
      saved.render_output_stale ?? true,
      batchId,
    )
    store.acknowledgeBatchChanges(captured, ['ocr'], batchId)
    notifyHistoryUpdated()
    return saved
  }

  return { saveBatch, saveAllUnsavedBatches, saveRenderState }
}
