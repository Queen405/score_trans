import { apiFetch, type ApiResult } from './client'
import type {
  AccidentalMode,
  InstrumentProfile,
  MeasureNumberMode,
  MeasuresPerSystem,
  PipelineByFileIdRequest,
  PolyphonyMode,
  TargetKey,
  TaskSubmitResponse,
} from '../models/types'

export const pipelineApi = {
  run(
    file: File,
    targetKey: TargetKey = 'C',
    accidentalMode: AccidentalMode = 'auto',
    instrumentProfile: InstrumentProfile = 'general',
    measureNumberMode: MeasureNumberMode = 'all',
    title?: string,
    contentScalePercent = 67,
    systemGapPercent = 92,
    shortNoteGapPercent = 90,
    beatGapPercent = 100,
    breakBeamsAtBeat = false,
    polyphonyMode: PolyphonyMode = 'auto',
    measuresPerSystem: MeasuresPerSystem = 0,
    marginTopMm = 10,
    marginBottomMm = 7,
    marginLeftMm = 12,
    marginRightMm = 12,
    headerGapMm = 5,
    footerProtectionMm = 2,
    noteSizePercent = 100,
    lyricSizePercent = 100,
    titleSizePercent = 100,
    annotationSizePercent = 100,
    partGapPercent = 100,
    voiceGapPercent = 100,
    lyricLineGapPercent = 100,
    lyricNoteGapPercent = 100,
  ): Promise<ApiResult<TaskSubmitResponse>> {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('target_key', targetKey)
    formData.append('accidental_mode', accidentalMode)
    formData.append('instrument_profile', instrumentProfile)
    formData.append('measure_number_mode', measureNumberMode)
    formData.append('jianpu_content_scale_percent', String(contentScalePercent))
    formData.append('jianpu_system_gap_percent', String(systemGapPercent))
    formData.append('jianpu_short_note_gap_percent', String(shortNoteGapPercent))
    formData.append('jianpu_beat_gap_percent', String(beatGapPercent))
    formData.append('jianpu_break_beams_at_beat', breakBeamsAtBeat ? '1' : '0')
    formData.append('jianpu_measures_per_system', String(measuresPerSystem))
    formData.append('jianpu_margin_top_mm', String(marginTopMm))
    formData.append('jianpu_margin_bottom_mm', String(marginBottomMm))
    formData.append('jianpu_margin_left_mm', String(marginLeftMm))
    formData.append('jianpu_margin_right_mm', String(marginRightMm))
    formData.append('jianpu_header_gap_mm', String(headerGapMm))
    formData.append('jianpu_footer_protection_mm', String(footerProtectionMm))
    formData.append('jianpu_note_size_percent', String(noteSizePercent))
    formData.append('jianpu_lyric_size_percent', String(lyricSizePercent))
    formData.append('jianpu_title_size_percent', String(titleSizePercent))
    formData.append('jianpu_annotation_size_percent', String(annotationSizePercent))
    formData.append('jianpu_part_gap_percent', String(partGapPercent))
    formData.append('jianpu_voice_gap_percent', String(voiceGapPercent))
    formData.append('jianpu_lyric_line_gap_percent', String(lyricLineGapPercent))
    formData.append('jianpu_lyric_note_gap_percent', String(lyricNoteGapPercent))
    formData.append('polyphony_mode', polyphonyMode)
    if (title) {
      formData.append('title', title)
    }
    return apiFetch('/pipeline', { method: 'POST', body: formData })
  },

  runByFileId(req: PipelineByFileIdRequest): Promise<ApiResult<TaskSubmitResponse>> {
    return apiFetch('/pipeline/by-file-id', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    })
  },
}
