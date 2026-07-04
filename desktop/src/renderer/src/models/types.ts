export type {
  AccidentalMode,
  AiChatMessage,
  AiChatRequest,
  AiChatResponse,
  AiChatSession,
  AiTranscribeRequest,
  AiTranscribeResponse,
  AiTranscribedPage,
  BatchRenderPageRequest,
  BatchRenderRequest,
  BatchRenderResponse,
  CacheCleanupResponse,
  ExportMidiTextRequest,
  ExportMusicXmlRequest,
  ExportMusicXmlTextRequest,
  ExportResponse,
  FinalOutputRequest,
  FinalOutputResponse,
  HistoryBatch,
  HistoryBatchJianpuTextUpdateRequest,
  HistoryBatchListItem,
  HistoryBatchPageOrderRequest,
  HistoryBatchRenderPageOcrTextsUpdateRequest,
  HistoryBatchRenderPagesUpdateRequest,
  HistoryCreateRequest,
  HistoryPage,
  HistoryPageUpdateRequest,
  InstrumentProfile,
  InstrumentProfileCatalog,
  LlmProviderOption,
  MeasureNumberMode,
  MusicXmlToJianpuRequest,
  MusicXmlToJianpuResponse,
  NormalizeJianpuTextRequest,
  NormalizeJianpuTextResponse,
  PerformanceMarkCatalogItem,
  PipelineByFileIdRequest,
  PipelineResponse,
  RecognizeResponse,
  RenderedSvgPage,
  RenderJianpuSvgRequest,
  RenderJianpuSvgResponse,
  RenderJianpuTextSvgRequest,
  RenderJianpuTextSvgResponse,
  RenderPageMeasureRange,
  RenderPageOcrText,
  SettingsResponse,
  SettingsUpdateRequest,
  SSEProgressEvent,
  SourceTextAttachment,
  SyntaxExample,
  TargetKey,
  TaskSubmitResponse,
  TextAnchor,
  TextPlacementAnchor,
  RenderedTextBlock,
  UploadPage,
  UploadResponse,
} from './contracts'

export type ThemeMode = 'dark' | 'light' | 'system'

export interface StoragePaths {
  dataDir: string
  cacheDir: string
  configPath: string
}

export interface LogEntry {
  id: number
  timestamp: string
  level: 'info' | 'warn' | 'error'
  message: string
}
