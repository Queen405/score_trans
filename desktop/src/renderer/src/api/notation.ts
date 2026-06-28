import { apiFetch, type ApiResult } from './client'
import type { InstrumentProfileCatalog } from '../models/types'

export const notationApi = {
  listInstrumentProfiles(): Promise<ApiResult<InstrumentProfileCatalog[]>> {
    return apiFetch('/notation/instrument-profiles')
  },
}
