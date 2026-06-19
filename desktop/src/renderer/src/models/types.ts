export interface ErrorResponse {
  error: string
  detail?: string
  stage?: 'audiveris' | 'ocr' | 'ai' | 'convert' | 'render' | 'export' | 'upload'
}

export interface UploadPage {
  file_id: string
  filename: string
  page_index: number
}

export interface UploadResponse {
  file_id: string
  filename: string
  size: number
  pages?: UploadPage[]
}

export interface MusicXmlToJianpuRequest {
  musicxml_file_id: string
  page_image_file_id?: string
  target_key?: TargetKey
  accidental_mode?: AccidentalMode
  start_measure_number?: number
}

export interface MusicXmlToJianpuResponse {
  jianpu_text: string
  jianpu_file_id?: string
}

export interface RenderJianpuSvgRequest {
  musicxml_file_id: string
  page_image_file_id?: string
  target_key?: TargetKey
  accidental_mode?: AccidentalMode
  show_measure_numbers?: boolean
  measure_number_mode?: MeasureNumberMode
  start_measure_number?: number
  title?: string
}

export interface RenderPageMeasureRange {
  source_page_index: number
  start_measure_number?: number | null
  end_measure_number?: number | null
}

export interface RenderPageOcrText {
  page_index: number
  ocr_text: string
}

export interface RenderedSvgPage {
  svg_file_id: string
  page_index: number
  page_width: number
  page_height: number
  measure_ranges?: RenderPageMeasureRange[]
  ocr_text?: string | null
}

export interface RenderJianpuSvgResponse {
  svg_file_id: string
  pages?: RenderedSvgPage[]
}

export interface RenderJianpuTextSvgRequest {
  jianpu_text?: string
  jianpu_file_id?: string
  page_image_file_id?: string
  ocr_text?: string
  include_ocr_text?: boolean
  show_measure_numbers?: boolean
  measure_number_mode?: MeasureNumberMode
  title?: string
  start_measure_number?: number
}

export interface RenderJianpuTextSvgResponse {
  svg_file_id: string
  pages?: RenderedSvgPage[]
  ocr_text?: string
  jianpu_text?: string
}

export interface NormalizeJianpuTextRequest {
  jianpu_text: string
  title?: string
}

export interface NormalizeJianpuTextResponse {
  jianpu_text: string
}

export interface FinalOutputRequest {
  musicxml_file_id: string
  page_image_file_id?: string
  target_key?: TargetKey
  accidental_mode?: AccidentalMode
  show_measure_numbers?: boolean
  measure_number_mode?: MeasureNumberMode
  start_measure_number?: number
  title?: string
}

export interface FinalOutputResponse {
  svg_file_id: string
  pages?: RenderedSvgPage[]
  page_width: number
  page_height: number
}

export interface BatchRenderPageRequest {
  musicxml_file_id?: string
  jianpu_text?: string
  jianpu_file_id?: string
  input_file_name?: string
  page_image_file_id?: string
  ocr_text?: string
  include_ocr_text?: boolean
  start_measure_number?: number
  title?: string
}

export interface BatchRenderRequest {
  pages: BatchRenderPageRequest[]
  source_pages?: BatchRenderPageRequest[]
  render_page_ocr_texts?: RenderPageOcrText[]
  target_key?: TargetKey
  accidental_mode?: AccidentalMode
  show_measure_numbers?: boolean
  measure_number_mode?: MeasureNumberMode
  title?: string
}

export interface BatchRenderResponse {
  svg_file_id: string
  pages: RenderedSvgPage[]
  page_width: number
  page_height: number
}

export interface RecognizeResponse {
  musicxml_file_id: string
  musicxml_filename: string
}

export interface TaskSubmitResponse {
  task_id: string
  status: 'pending' | 'running' | 'completed' | 'failed'
}

export interface PipelineByFileIdRequest {
  file_id: string
  target_key: TargetKey
  accidental_mode?: AccidentalMode
  show_measure_numbers?: boolean
  measure_number_mode?: MeasureNumberMode
  start_measure_number?: number | null
  title?: string | null
}

export interface PipelineResponse {
  musicxml_file_id: string
  jianpu_text: string
  jianpu_file_id: string
  svg_file_id: string
  render_pages?: RenderedSvgPage[]
  ocr_measure_numbers: number[]
  ocr_text?: string | null
}

export interface AiTranscribeRequest {
  file_id: string
  target_key?: TargetKey
  accidental_mode?: AccidentalMode
  title?: string
  render_dpi?: number
  max_pages?: number
  prompt?: string
  normalize?: boolean
}

export interface AiTranscribedPage {
  page_index: number
  page_image_file_id: string
  page_image_filename: string
  title?: string | null
  key?: string | null
  meter?: string | null
  tempo?: string | null
  jianpu_text: string
  measure_number_candidates: number[]
  warnings: string[]
  validation_errors: string[]
  confidence?: number | null
}

export interface AiTranscribeResponse {
  source_file_id: string
  source_filename: string
  target_key: string
  title?: string | null
  merged_jianpu_text: string
  jianpu_file_id: string
  pages: AiTranscribedPage[]
  warnings: string[]
}

export interface AiChatMessage {
  id: number
  session_id: string
  role: 'user' | 'assistant'
  content: string
  created_at: string
}

export interface AiChatSession {
  id: string
  title: string
  created_at: string
  updated_at: string
}

export interface AiChatRequest {
  message: string
  session_id?: string
  jianpu_text?: string
  enable_thinking?: boolean
}

export interface AiChatResponse {
  session_id: string
  message: AiChatMessage
  messages: AiChatMessage[]
}

export interface ExportResponse {
  file_id: string
  filename: string
}

export interface ExportMidiTextRequest {
  jianpu_text: string
  filename?: string
  title?: string
}

export type ThemeMode = 'dark' | 'light' | 'system'
export type AccidentalMode = 'auto' | 'sharp' | 'flat'
export type MeasureNumberMode = 'all' | 'row_start' | 'none'
export type TargetKey =
  | 'Cb'
  | 'Gb'
  | 'Db'
  | 'Ab'
  | 'Eb'
  | 'Bb'
  | 'F'
  | 'C'
  | 'G'
  | 'D'
  | 'A'
  | 'E'
  | 'B'
  | 'F#'
  | 'C#'

export interface LlmProviderOption {
  id: string
  label: string
  provider: string
  base_url: string
  model: string
  description?: string
}

export interface SettingsResponse {
  audiveris_path: string
  java_home: string
  data_dir: string
  cache_dir: string
  cache_size_bytes: number
  work_dir: string
  target_key?: TargetKey
  accidental_mode?: AccidentalMode
  show_measure_numbers?: boolean
  measure_number_mode?: MeasureNumberMode
  confirm_start_measure_number?: boolean
  jianpu_syntax_highlight?: boolean
  output_dir?: string
  ocr_provider?: string
  ocr_provider_options?: LlmProviderOption[]
  ocr_api_key?: string
  ocr_api_key_set?: boolean
  ocr_base_url?: string
  ocr_model?: string
  ai_provider?: string
  ai_provider_options?: LlmProviderOption[]
  ai_api_key?: string
  ai_api_key_set?: boolean
  ai_base_url?: string
  ai_model?: string
  assistant_provider?: string
  assistant_provider_options?: LlmProviderOption[]
  assistant_api_key?: string
  assistant_api_key_set?: boolean
  assistant_base_url?: string
  assistant_model?: string
}

export interface SettingsUpdateRequest {
  audiveris_path?: string
  java_home?: string
  output_dir?: string
  target_key?: TargetKey
  accidental_mode?: AccidentalMode
  show_measure_numbers?: boolean
  measure_number_mode?: MeasureNumberMode
  confirm_start_measure_number?: boolean
  jianpu_syntax_highlight?: boolean
  work_dir?: string
  ocr_provider?: string
  ocr_api_key?: string
  ai_provider?: string
  ai_api_key?: string
  assistant_provider?: string
  assistant_api_key?: string
}

export interface CacheCleanupResponse {
  cache_dir: string
  before_bytes: number
  after_bytes: number
  freed_bytes: number
  removed_items: number
  preserved_uploads: number
}

export interface StoragePaths {
  dataDir: string
  cacheDir: string
  configPath: string
}

export interface SSEProgressEvent {
  task_id: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  stage: string
  percent: number
  message: string
  error?: string
  result?: Record<string, unknown>
}

export interface LogEntry {
  timestamp: string
  level: 'info' | 'warn' | 'error'
  message: string
}

// ── History ──

export interface HistoryPage {
  id: number
  batch_id: number
  input_file_name: string
  input_file_id: string
  musicxml_file_id: string
  jianpu_text: string
  ocr_text: string
  svg_file_id: string
  start_measure_number: number | null
  status: string
  error_message: string
}

export interface HistoryBatch {
  id: number
  created_at: string
  page_count: number
  status: string
  jianpu_text: string
  render_page_file_ids: string[]
  render_page_ocr_texts: RenderPageOcrText[]
  pages: HistoryPage[]
}

export interface HistoryBatchListItem {
  id: number
  created_at: string
  page_count: number
  status: string
  first_file_name: string
}

export interface HistoryCreateRequest {
  render_page_file_ids?: string[]
  render_page_ocr_texts?: RenderPageOcrText[]
  jianpu_text?: string
  pages: {
    input_file_name?: string
    input_file_id?: string
    musicxml_file_id?: string
    jianpu_text?: string
    ocr_text?: string
    svg_file_id?: string
    start_measure_number?: number | null
    status?: string
    error_message?: string
  }[]
}

export interface HistoryPageUpdateRequest {
  musicxml_file_id?: string
  jianpu_text?: string
  ocr_text?: string
  svg_file_id?: string
  start_measure_number?: number | null
  status?: string
  error_message?: string
}

export interface HistoryBatchRenderPagesUpdateRequest {
  render_page_file_ids: string[]
}

export interface HistoryBatchJianpuTextUpdateRequest {
  jianpu_text: string
}

export interface HistoryBatchRenderPageOcrTextsUpdateRequest {
  pages: RenderPageOcrText[]
}
