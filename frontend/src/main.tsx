import React, { lazy, Suspense } from 'react'
import ReactDOM from 'react-dom/client'
import './index.css'
import Landing from './pages/landing'

const Workspace = lazy(() => import('./App'))
const path = window.location.pathname.replace(/\/+$/, '') || '/'
const page = path === '/' ? <Landing /> : path === '/app'
  ? <Suspense fallback={<div className="session-loading" role="status">Opening your workspace…</div>}><Workspace /></Suspense>
  : <main className="session-loading"><h1>Page not found</h1><a href="/">Back to Relay</a></main>

ReactDOM.createRoot(document.getElementById('root')!).render(<React.StrictMode>{page}</React.StrictMode>)
