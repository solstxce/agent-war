import { useEffect, useState, type FormEvent } from 'react'
import { onAuthStateChanged, signOut, type User } from 'firebase/auth'
import { LayoutDashboard, Package, Route, ShieldCheck, Truck } from 'lucide-react'
import { auth } from '@/lib/firebase'
import { api, type Workspace } from '@/lib/api'
import { AuthGate } from '@/components/auth-gate'
import { OperationsWorkspace } from '@/components/operations-workspace'
import { ErrorNotice } from '@/components/error-notice'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'

export default function App() {
  const [user, setUser] = useState<User | null>(null)
  const [initializing, setInitializing] = useState(Boolean(auth))
  useEffect(() => {
    if (!auth) return
    return onAuthStateChanged(auth, next => { setUser(next); setInitializing(false) }, () => setInitializing(false))
  }, [])
  if (initializing) return <div className="session-loading" role="status"><span className="session-loading-brand">relay.</span><p>Restoring your session…</p></div>
  if (!user) return <AuthGate />
  return <SignedInWorkspace key={user.uid} user={user} />
}

function SignedInWorkspace({ user }: { user: User }) {
  const [workspaces, setWorkspaces] = useState<Workspace[]>([])
  const [activeId, setActiveId] = useState('')
  const [loading, setLoading] = useState(true)
  const [hasLoaded, setHasLoaded] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [attempt, setAttempt] = useState(0)
  const [section, setSection] = useState(window.location.hash || '#overview')
  useEffect(() => {
    const navigate = () => setSection(window.location.hash || '#overview')
    window.addEventListener('hashchange', navigate)
    return () => window.removeEventListener('hashchange', navigate)
  }, [])
  useEffect(() => {
    const controller = new AbortController()
    setLoading(true); setError('')
    api<{ workspaces: Workspace[] }>('/api/me', { signal: controller.signal }).then(data => {
      if (controller.signal.aborted) return
      setHasLoaded(true)
      setWorkspaces(data.workspaces)
      setActiveId(previous => data.workspaces.some(workspace => workspace.id === previous) ? previous : data.workspaces[0]?.id || '')
    }).catch(cause => { if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : 'Could not load workspaces.') }).finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [attempt])
  async function createWorkspace(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const name = String(new FormData(event.currentTarget).get('name')).trim()
    if (!name) return
    setBusy(true); setError('')
    try {
      const workspace = await api<Workspace>('/api/workspaces', { method: 'POST', body: JSON.stringify({ name }) })
      setWorkspaces(previous => [...previous, workspace]); setActiveId(workspace.id)
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Could not create workspace.') }
    finally { setBusy(false) }
  }
  async function logout() {
    try { if (auth) await signOut(auth) }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Could not sign out.') }
  }
  const workspace = workspaces.find(item => item.id === activeId)
  return (
    <div className="app-shell">
      <a className="skip-link" href="#overview">Skip to workspace</a>
      <aside className="sidebar">
        <a className="brand" href="#overview" aria-label="Relay home">
          <span className="brand-icon"><Route size={23} aria-hidden="true" /></span>
          relay<span className="brand-dot">.</span>
        </a>
        <div className="workspace-label">DISPATCH WORKSPACE</div>
        <nav aria-label="Main navigation">
          {[
            { href: '#overview', label: 'Overview', icon: LayoutDashboard },
            { href: '#deliveries', label: 'Deliveries', icon: Package },
            { href: '#fleet', label: 'Fleet', icon: Truck },
          ].map(({ href, label, icon: Icon }) => (
            <a key={href} className="nav-item" href={href} title={label}
              aria-current={section === href ? 'page' : undefined} aria-label={label}>
              <Icon size={18} aria-hidden="true" /><span>{label}</span>
            </a>
          ))}
        </nav>
        <div className="sidebar-note">
          <ShieldCheck size={20} aria-hidden="true" />
          <strong>Your workspace, protected</strong>
          <p>Changes are validated by the backend and scoped to your organization.</p>
        </div>
        <div className="sidebar-footer">
          <span className="avatar">{user.email?.[0]?.toUpperCase() || 'U'}</span>
          <div><strong>{workspace?.name || 'New workspace'}</strong><small>{workspace?.role || 'Signed in'}</small></div>
        </div>
      </aside>
      <div className="main-area">
        <header className="topbar">
          <div className="topbar-inner">
            <span className="signed-in-email" title={user.email || undefined}>{user.email}</span>
            <div className="workspace-controls">
              {workspaces.length > 0 && (
                <label className="workspace-picker">
                  <span className="sr-only">Active workspace</span>
                  <select value={activeId} onChange={event => setActiveId(event.target.value)}>
                    {workspaces.map(item => <option key={item.id} value={item.id}>{item.name} · {item.role}</option>)}
                  </select>
                </label>
              )}
              <Button variant="ghost" size="sm" onClick={() => void logout()}>Sign out</Button>
            </div>
          </div>
        </header>
        <main id="overview" tabIndex={-1}>
          <div className="page-heading">
            <p className="eyebrow">DELIVERY OPERATIONS</p>
            <h1>{workspace?.name || (loading ? 'Your workspace' : !hasLoaded && error ? 'Workspace unavailable' : 'Create your workspace')}</h1>
            <p className="page-description">Manage deliveries and fleet availability in one place.</p>
          </div>
          <ErrorNotice message={error}>
            <Button variant="outline" size="sm" onClick={() => setAttempt(value => value + 1)}>Retry connection</Button>
          </ErrorNotice>
          {loading ? (
            <div className="workspace-loading" role="status"><span className="loading-line" /><p>Loading your workspaces…</p></div>
          ) : workspace ? (
            <OperationsWorkspace key={workspace.id} workspace={workspace} />
          ) : hasLoaded ? (
            <Card className="onboarding-card">
              <CardHeader>
                <span className="onboarding-icon"><Truck size={28} aria-hidden="true" /></span>
                <span className="eyebrow">LET'S GET STARTED</span>
                <CardTitle>Set up your organization</CardTitle>
                <CardDescription>You will become the owner of this workspace. Deliveries and vehicles are private to its members.</CardDescription>
              </CardHeader>
              <CardContent>
                <form className="operation-form" onSubmit={createWorkspace} aria-busy={busy}>
                  <label>Organization name<input name="name" autoComplete="organization" required maxLength={120} placeholder="Your distribution business" /></label>
                  <Button disabled={busy}>{busy ? 'Creating…' : 'Create workspace'}</Button>
                </form>
              </CardContent>
            </Card>
          ) : null}
          <footer className="page-footer"><span>Relay · Delivery exception management</span><span>Every change, accountable.</span></footer>
        </main>
      </div>
    </div>
  )
}

