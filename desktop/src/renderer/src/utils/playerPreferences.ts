const PLAYER_VOLUME_KEY = 'score-trans-player-volume'
const DEFAULT_PLAYER_VOLUME = 0.8

export function parsePlayerVolume(raw: string | null): number {
  if (raw === null) return DEFAULT_PLAYER_VOLUME
  const value = Number(raw)
  if (!Number.isFinite(value) || value < 0 || value > 1) {
    return DEFAULT_PLAYER_VOLUME
  }
  return value
}

export function loadPlayerVolume(
  storage?: Pick<Storage, 'getItem'>,
): number {
  try {
    const target = storage ?? window.localStorage
    return parsePlayerVolume(target.getItem(PLAYER_VOLUME_KEY))
  } catch {
    return DEFAULT_PLAYER_VOLUME
  }
}

export function savePlayerVolume(
  value: number,
  storage?: Pick<Storage, 'setItem'>,
): void {
  const normalized = Math.max(0, Math.min(1, value))
  if (!Number.isFinite(normalized)) return
  try {
    const target = storage ?? window.localStorage
    target.setItem(PLAYER_VOLUME_KEY, String(normalized))
  } catch {
    // The current session keeps the volume when storage is unavailable.
  }
}
