export interface ErrorResponse {
  error: string
  detail?: string
  stage?: 'audiveris' | 'musescore' | 'ocr' | 'convert' | 'render' | 'upload'
}

export interface UploadResponse {
  file_id: string
  filename: string
  size: number
}

export interface MusicXmlToJianpuRequest {
  musicxml_file_id: string
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
  title?: string
}

export interface RenderJianpuTextSvgResponse {
  svg_file_id: string
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

export interface ExportRequest {
  musicxml_file_id: string
  output_format?: 'pdf' | 'png' | 'mid'
  filename?: string
}

export interface ExportResponse {
  file_id: string
  filename: string
}

export interface SettingsResponse {
  audiveris_path: string
  musescore_path: string
  java_home: string
  work_dir: string
  target_key?: string
  output_dir?: string
  ocr_api_key_set?: boolean
  ocr_base_url?: string
  ocr_model?: string
}

export interface SettingsUpdateRequest {
  audiveris_path?: string
  musescore_path?: string
  java_home?: string
  output_dir?: string
  ocr_api_key?: string
  ocr_base_url?: string
  ocr_model?: string
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
