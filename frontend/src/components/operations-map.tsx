import { useEffect, useRef, useState } from 'react'
import { MapPin } from 'lucide-react'
import { loadMaps, mapCenter, mapId, mapsConfigured, subscribeMapAuthError } from '@/lib/maps'

type MapState = { status: 'loading' | 'ready' | 'error'; message?: string }

export function OperationsMap({ locations = [] }: { locations?: { id: string; lat: number; lng: number; title: string }[] }) {
  const container = useRef<HTMLDivElement>(null)
  const [state, setState] = useState<MapState>({ status: 'loading' })
  const mapInstance = useRef<google.maps.Map | null>(null)

  useEffect(() => {
    if (state.status !== 'ready' || !mapInstance.current) return
    const markers = locations.map(location => new google.maps.Marker({ map: mapInstance.current, position: location, title: location.title }))
    if (locations.length) {
      const bounds = new google.maps.LatLngBounds()
      locations.forEach(location => bounds.extend(location))
      mapInstance.current.fitBounds(bounds, 50)
      if (locations.length === 1) mapInstance.current.setZoom(13)
    }
    return () => markers.forEach(marker => marker.setMap(null))
  }, [locations, state.status])

  useEffect(() => {
    if (!mapsConfigured) return
    let cancelled = false
    let failed = false
    let map: google.maps.Map | undefined
    const fail = (error: Error) => {
      if (cancelled) return
      failed = true
      setState({ status: 'error', message: error.message })
    }
    const unsubscribe = subscribeMapAuthError(fail)
    const timeout = window.setTimeout(() => fail(new Error('Google Maps took too long to load. Check your connection and browser restrictions, then reload.')), 20000)
    loadMaps().then(({ Map }) => {
      if (cancelled || failed || !container.current) return
      map = new Map(container.current, {
        center: mapCenter, zoom: 5, mapId,
        mapTypeControl: false, streetViewControl: false,
        gestureHandling: 'cooperative', fullscreenControl: true,
      })
      window.clearTimeout(timeout)
      mapInstance.current = map
      if (!failed) setState({ status: 'ready' })
    }).catch(error => {
      window.clearTimeout(timeout)
      fail(new Error(error instanceof Error ? error.message : 'Google Maps could not load.'))
    })
    return () => {
      cancelled = true
      unsubscribe()
      window.clearTimeout(timeout)
      if (map) google.maps.event.clearInstanceListeners(map)
      mapInstance.current = null
      container.current?.replaceChildren()
    }
  }, [])

  const missing = !mapsConfigured
  return <div className="operations-map">
    <div ref={container} className="google-map-canvas" aria-label="Delivery operations map" />
    {(missing || state.status !== 'ready') && <div className="map-state" role="status">
      <span className="empty-icon"><MapPin size={28} /></span>
      <h3>{missing ? 'Connect Google Maps' : state.status === 'error' ? 'Map unavailable' : 'Loading Google Maps...'}</h3>
      <p>{missing ? 'Add VITE_GOOGLE_MAPS_API_KEY to the frontend environment and restart the app.' : state.message || 'Preparing the operations map.'}</p>
      {state.status === 'error' && <button type="button" className="map-reload" onClick={() => window.location.reload()}>Reload page</button>}
    </div>}
    {!missing && state.status === 'ready' && <p className="map-data-note">{locations.length ? `${locations.length} loaded locations shown.` : 'No coordinates in the loaded records.'}</p>}
  </div>
}
