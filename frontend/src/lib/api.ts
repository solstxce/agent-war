import { auth } from './firebase'

const base = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000').replace(/\/$/, '')

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const user = auth?.currentUser
  if (!user) throw new Error('Sign in to continue.')
  const token = await user.getIdToken()
  const controller = new AbortController()
  let timedOut = false
  const cancel = () => controller.abort()
  if (options.signal?.aborted) controller.abort()
  options.signal?.addEventListener('abort', cancel, { once: true })
  const timeout = window.setTimeout(() => { timedOut = true; controller.abort() }, 20000)
  try {
    let response: Response
    try {
      response = await fetch(`${base}${path}`, {
        ...options, signal: controller.signal,
        headers: { 'Content-Type': 'application/json', ...options.headers, Authorization: `Bearer ${token}` },
      })
    } catch (cause) {
      if (options.signal?.aborted) throw cause
      if (timedOut) throw new Error('The backend took too long to respond. Check the service, then refresh records before retrying a change; it may already have been saved.')
      throw new Error('Could not reach the backend. Start the Python API and check VITE_API_BASE_URL and your connection.')
    }
    if (!response.ok) {
      const body = await response.json().catch(() => null)
      const detail = body?.detail
      throw new Error(typeof detail === 'string' ? detail : Array.isArray(detail) ? detail.map((item: { msg: string }) => item.msg).join('; ') : `Request failed (${response.status}).`)
    }
    return response.status === 204 ? undefined as T : await response.json() as T
  } finally {
    window.clearTimeout(timeout)
    options.signal?.removeEventListener('abort', cancel)
  }
}

export interface Workspace { id: string; name: string; role: string }
export interface OperationRecord {
  id: string; version: number; customer_name?: string; address?: string; load_kg?: number;
  window_start?: string | null; window_end?: string | null; status?: string;
  registration?: string; driver_name?: string; capacity_kg?: number; available?: boolean;
  latitude?: number | null; longitude?: number | null;
}
export interface RecordPage { items: OperationRecord[]; next_cursor: string | null }
