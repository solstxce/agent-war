import { importLibrary, setOptions } from '@googlemaps/js-api-loader'

export const mapsConfigured = Boolean(import.meta.env.VITE_GOOGLE_MAPS_API_KEY?.trim())
export const mapId = import.meta.env.VITE_GOOGLE_MAPS_MAP_ID?.trim() || undefined

function coordinate(value: string | undefined, fallback: number, limit: number) {
  const parsed = value?.trim() ? Number(value) : NaN
  return Number.isFinite(parsed) && Math.abs(parsed) <= limit ? parsed : fallback
}

// Default is a viewport over India, not a depot or vehicle location.
export const mapCenter = {
  lat: coordinate(import.meta.env.VITE_MAP_CENTER_LAT, 20.5937, 90),
  lng: coordinate(import.meta.env.VITE_MAP_CENTER_LNG, 78.9629, 180),
}

let library: ReturnType<typeof importLibrary<'maps'>> | undefined
let authError: Error | undefined
const authListeners = new Set<(error: Error) => void>()

export function subscribeMapAuthError(listener: (error: Error) => void) {
  authListeners.add(listener)
  if (authError) listener(authError)
  return () => { authListeners.delete(listener) }
}

export function loadMaps() {
  if (!mapsConfigured) return Promise.reject(new Error('Google Maps browser key is missing.'))
  if (!library) {
    const mapsWindow = window as Window & { gm_authFailure?: () => void }
    const previousHandler = mapsWindow.gm_authFailure
    mapsWindow.gm_authFailure = () => {
      authError = new Error('Google Maps authorization failed. Check billing, Maps JavaScript API activation, and browser key restrictions, then reload.')
      for (const listener of authListeners) listener(authError)
      previousHandler?.()
    }
    setOptions({ key: import.meta.env.VITE_GOOGLE_MAPS_API_KEY.trim(), v: 'quarterly' })
    library = importLibrary('maps').then(async maps => { await importLibrary('marker'); return maps })
  }
  if (authError) return Promise.reject(authError)
  return library
}
