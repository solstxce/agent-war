import { useEffect, useState } from 'react'
import { ArrowRight, Check, CircleAlert, LayoutDashboard, Package, Radio, RotateCw, Route, ShieldCheck, Truck } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { firebaseConfigured } from '@/lib/firebase'
import { OperationsMap } from '@/components/operations-map'

type Connection = 'checking' | 'connected' | 'unavailable'
const apiBase = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/$/, '')

export default function App() {
  const [connection, setConnection] = useState<Connection>('checking')
  const [attempt, setAttempt] = useState(0)
  useEffect(() => {
    const controller = new AbortController()
    const timeout = window.setTimeout(() => controller.abort(), 5000)
    let cancelled = false
    fetch(`${apiBase}/api/health`, { signal: controller.signal }).then(async response => {
      if (!response.ok) throw new Error('Health check failed')
      const health: unknown = await response.json()
      if (typeof health !== 'object' || health === null || !('status' in health) || health.status !== 'ok') throw new Error('Unexpected health response')
      if (!cancelled) setConnection('connected')
    }).catch(() => { if (!cancelled) setConnection('unavailable') }).finally(() => window.clearTimeout(timeout))
    return () => { cancelled = true; controller.abort(); window.clearTimeout(timeout) }
  }, [attempt])

  function reconnect() { setConnection('checking'); setAttempt(value => value + 1) }
  return <div className="app-shell">
    <aside className="sidebar">
      <a className="brand" href="#overview" aria-label="Relay home"><span className="brand-icon"><Route size={23} /></span>relay<span className="brand-dot">.</span></a>
      <div className="workspace-label">DISPATCH WORKSPACE</div>
      <nav aria-label="Main navigation"><a className="nav-item active" href="#overview"><LayoutDashboard size={18} /> Overview</a><a className="nav-item" href="#operations"><Package size={18} /> Deliveries</a><a className="nav-item" href="#operations"><Truck size={18} /> Fleet</a><a className="nav-item" href="#recovery"><CircleAlert size={18} /> Recovery</a></nav>
      <div className="sidebar-note"><ShieldCheck size={20} /><strong>You stay in control</strong><p>Recovery plans require dispatcher approval before assignments change.</p></div>
      <div className="sidebar-footer"><span className="avatar">D</span><div><strong>Dispatcher workspace</strong><small>Setup in progress</small></div></div>
    </aside>
    <div className="main-area">
      <header className="topbar"><span className="text-muted-foreground">Operations <span className="mx-3">/</span> <span className="text-foreground">Overview</span></span><span className="environment"><span /> Development</span></header>
      <main id="overview">
        <div className="page-heading"><div><p className="eyebrow">DELIVERY RECOVERY</p><h1>Keep the day moving.</h1><p className="page-description">One place to see deliveries, manage your fleet, and recover from disruptions.</p></div><span className="setup-badge"><Radio size={14} /> Workspace setup</span></div>
        <div className="status-strip" role="status"><span className={`status-dot ${connection === 'connected' ? 'online' : ''}`} /><strong>{connection === 'checking' ? 'Connecting to backend...' : connection === 'connected' ? 'Backend connected' : 'Backend unavailable'}</strong><span>{connection === 'connected' ? 'The service is responding. Configure Firebase to continue setup.' : 'Operational data will appear after services and authentication are configured.'}</span><Button variant="ghost" size="sm" onClick={reconnect} disabled={connection === 'checking'}><RotateCw size={14} /> Retry</Button></div>
        <section className="metrics" aria-label="Operations summary">{[{ label: 'Deliveries today', icon: Package, note: 'Awaiting delivery data' }, { label: 'Available vehicles', icon: Truck, note: 'Awaiting fleet data' }, { label: 'Open incidents', icon: CircleAlert, note: 'Awaiting incident data' }].map(({label, icon: Icon, note}) => <Card key={label}><CardContent className="metric-content"><div className="metric-label">{label}<Icon size={18}/></div><div className="metric-value">—</div><p>{note}</p></CardContent></Card>)}</section>
        <section className="content-grid" id="operations">
          <Card className="operations-card"><CardHeader><CardTitle>Today's operation</CardTitle><CardDescription>Your deliveries and vehicle assignments will appear here.</CardDescription></CardHeader><CardContent><OperationsMap /></CardContent></Card>
          <Card id="setup"><CardHeader><span className="eyebrow">GETTING STARTED</span><CardTitle>Connect your workspace</CardTitle><CardDescription>The foundation is ready. Connect services before dispatching.</CardDescription></CardHeader><CardContent className="setup-list"><SetupStep number="1" ready={connection === 'connected'} title="Backend service" description={connection === 'connected' ? 'Health endpoint is responding.' : 'Start the Python API to connect.'}/><SetupStep number="2" ready={firebaseConfigured} title="Firebase project" description={firebaseConfigured ? 'Client configuration is present.' : 'Add Firebase configuration to your environment.'}/><SetupStep number="3" ready={false} title="Your first delivery" description="Delivery management is the next implementation step."/><div className="setup-footnote"><ShieldCheck size={16}/><span>No sample shipments or simulated fleet counts are shown.</span></div></CardContent></Card>
        </section>
        <Card className="recovery-card" id="recovery"><CardContent className="recovery-content"><span className="recovery-icon"><Route size={25}/></span><div><span className="eyebrow">WHEN PLANS CHANGE</span><h2>Recover with a plan you can trust.</h2><p>Report a breakdown, review feasible reassignments, and approve the next move. Agent recovery tools will be connected in the next phase.</p></div><span className="coming-next">Next phase <ArrowRight size={16}/></span></CardContent></Card>
        <footer className="page-footer">Relay · Delivery exception management<span>Every change, accountable.</span></footer>
      </main>
    </div>
  </div>
}

function SetupStep({ number, ready, title, description }: {number: string; ready: boolean; title: string; description: string}) {
  return <div className="setup-step"><span className={`step-number ${ready ? 'ready' : ''}`}>{ready ? <Check size={15}/> : number}</span><div><h3>{title}</h3><p>{description}</p></div></div>
}

