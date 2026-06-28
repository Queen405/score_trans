import { apiFetch } from './client'
import type { InstrumentProfileCatalog } from '../models/types'

export const notationApi = {
  listInstrumentProfiles(): Promise<InstrumentProfileCatalog[]> {
    return apiFetch('/notation/instrument-profiles')
  },
}
