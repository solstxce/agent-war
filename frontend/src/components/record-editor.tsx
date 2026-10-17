import { useState, type FormEvent } from 'react'
import { api, type OperationRecord } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { ErrorNotice } from './error-notice'

export type RecordKind = 'deliveries' | 'vehicles'
function localDate(value?: string | null) {
  if (!value) return ''
  const date = new Date(value)
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16)
}
export function RecordEditor({ organization, kind, record, onSaved, onCancel }: { organization: string; kind: RecordKind; record: OperationRecord | null; onSaved: () => void; onCancel: () => void }) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})
  const delivery = kind === 'deliveries'
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const data = new FormData(event.currentTarget)
    const latitude = String(data.get('latitude') || '')
    const longitude = String(data.get('longitude') || '')
    const start = String(data.get('window_start') || '')
    const end = String(data.get('window_end') || '')
    const invalid: Record<string, string> = {}
    if (Boolean(latitude) !== Boolean(longitude)) invalid[latitude ? 'longitude' : 'latitude'] = 'Enter both coordinates, or leave both empty.'
    if (delivery && Boolean(start) !== Boolean(end)) invalid[start ? 'window_end' : 'window_start'] = 'Enter both window dates, or leave both empty.'
    if (delivery && start && end && new Date(start) >= new Date(end)) invalid.window_end = 'End must be after the start.'
    setFieldErrors(invalid)
    if (Object.keys(invalid).length) { setError('Check the highlighted fields before saving.'); return }
    const coordinates = { latitude: latitude ? Number(latitude) : null, longitude: longitude ? Number(longitude) : null }
    const body = delivery ? {
      customer_name: String(data.get('customer_name')).trim(), address: String(data.get('address')).trim(),
      load_kg: Number(data.get('load_kg')), status: 'pending',
      window_start: start ? new Date(start).toISOString() : null, window_end: end ? new Date(end).toISOString() : null,
      ...coordinates,
    } : {
      registration: String(data.get('registration')).trim(), driver_name: String(data.get('driver_name')).trim(),
      capacity_kg: Number(data.get('capacity_kg')), available: data.get('available') === 'on', ...coordinates,
    }
    setBusy(true); setError('')
    try {
      await api(`/api/organizations/${encodeURIComponent(organization)}/${kind}${record ? `/${encodeURIComponent(record.id)}` : ''}`, { method: record ? 'PUT' : 'POST', body: JSON.stringify({ ...body, ...(record ? { version: record.version } : {}) }) })
      onSaved()
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Could not save.'); setBusy(false) }
  }
  const fieldProps = (name: string) => ({ id: name, 'aria-invalid': Boolean(fieldErrors[name]), 'aria-describedby': fieldErrors[name] ? `${name}-error` : undefined })
  const inlineError = (name: string) => fieldErrors[name] ? <span className="field-error" id={`${name}-error`}>{fieldErrors[name]}</span> : null
  return <section className="editor-panel" aria-label={`${record ? 'Edit' : 'Create'} ${delivery ? 'delivery' : 'vehicle'}`}><h3>{record ? 'Edit' : 'New'} {delivery ? 'delivery' : 'vehicle'}</h3><p className="field-help">{delivery ? 'Add customer details and the load to be delivered.' : 'Register a vehicle and its available carrying capacity.'} Fields are required unless marked optional.</p><form onSubmit={submit} className="operation-form" aria-busy={busy}><ErrorNotice message={error}>{Object.entries(fieldErrors).map(([name, detail]) => <a key={name} href={`#${name}`} onClick={event => { event.preventDefault(); document.getElementById(name)?.focus() }}>{detail}</a>)}</ErrorNotice><fieldset disabled={busy}><legend>{delivery ? 'Delivery details' : 'Vehicle details'}</legend><div className="form-grid">{delivery ? <>
    <label>Customer name<input name="customer_name" defaultValue={record?.customer_name} required maxLength={200} /></label>
    <label>Load (kg)<input name="load_kg" type="number" min="0.01" step="any" defaultValue={record?.load_kg} required /></label>
    <label className="full-field">Delivery address<input name="address" defaultValue={record?.address} required maxLength={1000} /></label>
    <label>Window start (optional, local time)<input {...fieldProps('window_start')} name="window_start" type="datetime-local" defaultValue={localDate(record?.window_start)} />{inlineError('window_start')}</label>
    <label>Window end (optional, local time)<input {...fieldProps('window_end')} name="window_end" type="datetime-local" defaultValue={localDate(record?.window_end)} />{inlineError('window_end')}</label>
  </> : <>
    <label>Registration<input name="registration" defaultValue={record?.registration} required maxLength={80} /></label>
    <label>Driver name<input name="driver_name" defaultValue={record?.driver_name} required maxLength={200} /></label>
    <label>Capacity (kg)<input name="capacity_kg" type="number" min="0.01" step="any" defaultValue={record?.capacity_kg} required /></label>
    <label className="checkbox-field"><input name="available" type="checkbox" defaultChecked={record?.available ?? true} />Available for dispatch</label>
  </>}
  </div><details className="optional-details" open={Boolean(record?.latitude != null || fieldErrors.latitude || fieldErrors.longitude)}><summary>Map location (optional)</summary><p className="field-help">Enter a coordinate pair to show this record on the map.</p><div className="form-grid">
    <label>Latitude<input {...fieldProps('latitude')} name="latitude" type="number" min="-90" max="90" step="any" defaultValue={record?.latitude ?? ''} />{inlineError('latitude')}</label>
    <label>Longitude<input {...fieldProps('longitude')} name="longitude" type="number" min="-180" max="180" step="any" defaultValue={record?.longitude ?? ''} />{inlineError('longitude')}</label>
  </div></details></fieldset><div className="action-row"><Button disabled={busy}>{busy ? 'Saving...' : 'Save'} {delivery ? 'delivery' : 'vehicle'}</Button><Button variant="outline" type="button" disabled={busy} onClick={onCancel}>Cancel</Button></div></form></section>
}
