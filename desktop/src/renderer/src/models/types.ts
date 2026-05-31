export interface ErrorResponse {
  error: string
  detail?: string
  stage?: 'audiveris' | 'ocr' | 'convert' | 'render' | 'export' | 'upload'
}

export interface UploadResponse {
  file_id: string
  filename: string
  size: number
}

export interface MusicXmlToJianpuRequest {
  musicxml_file_id: string
  page_image_file_id?: string
  target_key?: string
  start_measure_number?: number
}

export interface MusicXmlToJianpuResponse {
  jianpu_text: string
  jianpu_file_id?: string
}

export interface JianpuToMusicXmlRequest {
  jianpu_text?: string
  jianpu_file_id?: string
  title?: string
}

export interface JianpuToMusicXmlResponse {
  musicxml_text: string
  musicxml_file_id: string
}

export interface RenderJianpuSvgRequest {
  musicxml_file_id: string
  page_image_file_id?: string
  target_key?: string
  start_measure_number?: number
  title?: string
}

export interface RenderJianpuSvgResponse {
  svg_file_id: string
}

export interface RenderJianpuTextSvgRequest {
  jianpu_text?: string
  jianpu_file_id?: string
  page_image_file_id?: string
  ocr_text?: string
  include_ocr_text?: boolean
  title?: string
}

export interface RenderJianpuTextSvgResponse {
  svg_file_id: string
  ocr_text?: string
}

export interface FinalOutputRequest {
  musicxml_file_id: string
  page_image_file_id?: string
  target_key?: string
  start_measure_number?: number
  title?: string
}

export interface FinalOutputResponse {
  svg_file_id: string
  page_width: number
  page_height: number
}

export interface RecognizeResponse {
  task_id?: string
  musicxml_file_id: string
  musicxml_filename: string
}

export interface PipelineResponse {
  task_id?: string
  musicxml_file_id: string
  jianpu_text: string
  jianpu_file_id: string
  svg_file_id: string
}

export interface ExportResponse {
  file_id: string
  filename: string
}

export interface SettingsResponse {
  audiveris_path: string
  java_home: string
  work_dir: string
  target_key?: string
  output_dir?: string
  ocr_api_key?: string
  ocr_api_key_set?: boolean
  ocr_base_url?: string
  ocr_model?: string
  omr_preprocess?: boolean
  omr_preprocess_long_edge?: number
  omr_preprocess_binarize?: boolean
}

export interface SettingsUpdateRequest {
  audiveris_path?: string
  java_home?: string
  output_dir?: string
  ocr_api_key?: string
  ocr_base_url?: string
  ocr_model?: string
  omr_preprocess?: boolean
  omr_preprocess_long_edge?: number
  omr_preprocess_binarize?: boolean
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
  input_file_name: string
  input_file_id: string
  musicxml_file_id: string
  jianpu_text: string
  ocr_text: string
  svg_file_id: string
  status: string
  error_message: string
}

export interface HistoryBatch {
  id: number
  created_at: string
  page_count: number
  status: string
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
  pages: {
    input_file_name?: string
    input_file_id?: string
    musicxml_file_id?: string
    jianpu_text?: string
    ocr_text?: string
    svg_file_id?: string
    status?: string
    error_message?: string
  }[]
}

export interface HistoryPageUpdateRequest {
  musicxml_file_id?: string
  jianpu_text?: string
  ocr_text?: string
  svg_file_id?: string
  status?: string
  error_message?: string
}
