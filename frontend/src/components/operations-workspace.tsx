import { useCallback, useEffect, useState } from 'react'
import { api, type OperationRecord, type RecordPage, type Workspace } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { RecordEditor, type RecordKind } from './record-editor'
import { OperationsMap } from './operations-map'
import { ErrorNotice } from './error-notice'
import { Package, Truck, Plus, RefreshCw } from 'lucide-react'

function message(cause: unknown) { return cause instanceof Error ? cause.message : 'Something went wrong.' }
export function OperationsWorkspace({ workspace }: { workspace: Workspace }) {
  const [kind, setKind] = useState<RecordKind>(window.location.hash === '#fleet' ? 'vehicles' : 'deliveries')
  const [records, setRecords] = useState<OperationRecord[]>([])
  const [cursor, setCursor] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [editor, setEditor] = useState<OperationRecord | null | undefined>(undefined)
  const [deleting, setDeleting] = useState<OperationRecord | null>(null)
  const [saving, setSaving] = useState(false)
  const canWrite = ['owner', 'dispatcher'].includes(workspace.role)
  const path = `/api/organizations/${encodeURIComponent(workspace.id)}/${kind}`
  useEffect(() => {
    const navigate = () => { if (editor !== undefined || saving) return; if (window.location.hash === '#fleet') setKind('vehicles'); else if (window.location.hash === '#deliveries') setKind('deliveries') }
    window.addEventListener('hashchange', navigate)
    return () => window.removeEventListener('hashchange', navigate)
  }, [editor, saving])
  const load = useCallback(async (next?: string, signal?: AbortSignal) => {
    setLoading(true); setError('')
    try {
      const page = await api<RecordPage>(`${path}?limit=100${next ? `&cursor=${encodeURIComponent(next)}` : ''}`, { signal })
      if (signal?.aborted) return
      setRecords(previous => next ? [...previous, ...page.items.filter(item => !previous.some(old => old.id === item.id))] : page.items)
      setCursor(page.next_cursor)
    } catch (cause) { if (!signal?.aborted) setError(message(cause)) }
    finally { if (!signal?.aborted) setLoading(false) }
  }, [path])
  useEffect(() => {
    const controller = new AbortController()
    setRecords([]); setCursor(null); setEditor(undefined); setDeleting(null)
    void load(undefined, controller.signal)
    return () => controller.abort()
  }, [load])
  async function remove() {
    if (!deleting) return
    setSaving(true); setError('')
    try { await api(`${path}/${encodeURIComponent(deleting.id)}?expected_version=${deleting.version}`, { method: 'DELETE' }); setDeleting(null); await load() }
    catch (cause) { setError(message(cause)) }
    finally { setSaving(false) }
  }
  const delivery = kind === 'deliveries'
  function selectKind(next: RecordKind) {
    setKind(next)
    window.location.hash = next === 'deliveries' ? 'deliveries' : 'fleet'
  }
  return <>
    <div className="action-row section-tabs" role="group" aria-label="Operational records"><Button aria-pressed={delivery} variant={delivery ? 'default' : 'ghost'} disabled={editor !== undefined || saving} onClick={() => selectKind('deliveries')}>Deliveries</Button><Button aria-pressed={!delivery} variant={!delivery ? 'default' : 'ghost'} disabled={editor !== undefined || saving} onClick={() => selectKind('vehicles')}>Fleet</Button></div>
    <Card id="operations" tabIndex={-1}><CardHeader><div className="section-heading"><div><CardTitle>{delivery ? 'Deliveries' : 'Fleet'}</CardTitle><CardDescription>{records.length} loaded {kind}{cursor ? ' · More available' : ''}. {delivery ? 'Pending deliveries awaiting dispatch.' : `${records.filter(record => record.available).length} loaded vehicles available.`}</CardDescription></div><div className="action-row"><Button variant="outline" disabled={loading || saving || editor !== undefined} onClick={() => { setEditor(undefined); setDeleting(null); void load() }}><RefreshCw size={16} aria-hidden="true" />Refresh</Button>{canWrite && <Button disabled={editor !== undefined} onClick={() => { setEditor(null); setDeleting(null) }}><Plus size={16} aria-hidden="true" />Add {delivery ? 'delivery' : 'vehicle'}</Button>}</div></div></CardHeader><CardContent>
      {!canWrite && <p className="info-note">Your {workspace.role} role cannot change these records.</p>}
      {editor !== undefined && <RecordEditor key={editor?.id ?? 'new'} organization={workspace.id} kind={kind} record={editor} onCancel={() => setEditor(undefined)} onSaved={() => { setEditor(undefined); void load() }} />}
      <ErrorNotice message={error ? `${error} Refresh to load current records before retrying a conflicting change.` : ''} />
      {deleting && <section className="delete-confirm" aria-label="Confirm deletion"><p>Delete {deleting.customer_name || deleting.registration}? This removes the record from active operations.</p><div className="action-row"><Button disabled={saving} className="danger-button" onClick={() => void remove()}>{saving ? 'Deleting…' : 'Confirm delete'}</Button><Button variant="outline" disabled={saving} onClick={() => setDeleting(null)}>Cancel</Button></div></section>}
      {loading && <p role="status" className="info-note">Loading {kind}…</p>}
      {!loading && !error && records.length === 0 && <div className="records-empty">{delivery ? <Package size={32} aria-hidden="true" /> : <Truck size={32} aria-hidden="true" />}<h3>No {kind} yet</h3>{canWrite ? ` Add your first ${delivery ? 'delivery' : 'vehicle'} to get started.` : ''}</div>}
      {records.length > 0 && <div className="table-wrap"><table className="records-table"><caption className="sr-only">Loaded {kind} for {workspace.name}</caption><thead><tr><th scope="col">{delivery ? 'Customer / address' : 'Vehicle / driver'}</th><th scope="col">{delivery ? 'Load' : 'Capacity'}</th><th scope="col">{delivery ? 'Delivery window' : 'Availability'}</th><th scope="col">Status</th>{canWrite && <th scope="col">Actions</th>}</tr></thead><tbody>{records.map(record => <tr key={record.id}><td data-label={delivery ? 'Customer / address' : 'Vehicle / driver'}><strong>{delivery ? record.customer_name : record.registration}</strong><small>{delivery ? record.address : record.driver_name}</small></td><td data-label={delivery ? 'Load' : 'Capacity'}>{delivery ? record.load_kg : record.capacity_kg} kg</td><td data-label={delivery ? 'Delivery window' : 'Availability'}>{delivery ? record.window_start && record.window_end ? `${new Date(record.window_start).toLocaleString()} – ${new Date(record.window_end).toLocaleString()}` : 'No window' : record.available ? 'Available' : 'Unavailable'}</td><td data-label="Status"><span className="record-status">{delivery ? record.status : 'Registered'}</span></td>{canWrite && <td data-label="Actions"><div className="action-row"><Button size="sm" variant="ghost" disabled={saving || editor !== undefined} onClick={() => { setEditor(record); setDeleting(null) }}>Edit</Button><Button size="sm" variant="ghost" className="danger-text" disabled={saving || editor !== undefined} onClick={() => setDeleting(record)}>Delete</Button></div></td>}</tr>)}</tbody></table></div>}
      {cursor && <Button variant="outline" disabled={loading} onClick={() => void load(cursor)}>Load more</Button>}
    </CardContent></Card>
    <Card className="map-card"><CardHeader><CardTitle>Operation locations</CardTitle><CardDescription>Locations from the loaded {kind}. Add coordinates to display a record.</CardDescription></CardHeader><CardContent><OperationsMap locations={records.filter(record => record.latitude != null && record.longitude != null).map(record => ({ id: record.id, lat: record.latitude!, lng: record.longitude!, title: record.customer_name || record.registration || record.id }))} /></CardContent></Card>
  </>
}

