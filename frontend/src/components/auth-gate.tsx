import { useState, type FormEvent } from 'react'
import { createUserWithEmailAndPassword, signInWithEmailAndPassword } from 'firebase/auth'
import { auth, firebaseConfigured } from '@/lib/firebase'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Route, ShieldCheck, Truck, ArrowRight } from 'lucide-react'
import { ErrorNotice } from './error-notice'

export function AuthGate() {
  const [register, setRegister] = useState(() => new URLSearchParams(window.location.search).get('mode') === 'signup')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!auth) return
    const values = new FormData(event.currentTarget)
    setBusy(true); setError('')
    try {
      const action = register ? createUserWithEmailAndPassword : signInWithEmailAndPassword
      await action(auth, String(values.get('email')), String(values.get('password')))
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Authentication failed.') }
    finally { setBusy(false) }
  }
  return <div className="auth-page"><a className="skip-link" href="#auth-form">Skip to sign in</a><section className="auth-story" aria-label="About Relay"><a className="brand" href="#auth-form"><span className="brand-icon"><Route size={24} aria-hidden="true" /></span>relay<span className="brand-dot">.</span></a><div className="auth-story-content"><p className="eyebrow">DELIVERY OPERATIONS, CONNECTED</p><h1>A clearer view of the road ahead.</h1><p>Bring your deliveries and fleet into one workspace. Start with the essentials. Keep your team in control.</p><div className="route-art" aria-hidden="true"><svg viewBox="0 0 460 200" fill="none"><path d="M10 150H100Q130 150 130 120V65Q130 40 160 40H260Q290 40 290 70V130Q290 160 320 160H450" stroke="currentColor" strokeWidth="3" strokeDasharray="7 7"/><circle cx="45" cy="150" r="12" fill="currentColor"/><circle cx="210" cy="40" r="12" fill="currentColor"/><circle cx="405" cy="160" r="12" fill="currentColor"/><circle cx="210" cy="40" r="24" stroke="currentColor" opacity=".35"/></svg><span className="route-art-label"><Truck size={20} />Connected operations</span></div><div className="auth-trust"><ShieldCheck size={20} aria-hidden="true" /><span>Organization access. Validated changes. Real operational data.</span></div></div><small>RELAY / DELIVERY MANAGEMENT</small></section><main className="auth-form-area"><Card className="auth-card" id="auth-form" tabIndex={-1}><CardHeader><span className="eyebrow">YOUR OPERATIONS WORKSPACE</span><CardTitle>{firebaseConfigured ? register ? 'Create your account' : 'Welcome back' : 'Connect Firebase'}</CardTitle><CardDescription>{firebaseConfigured ? register ? 'Create an account, then set up your organization.' : 'Sign in to manage your deliveries and fleet.' : 'Set the Firebase frontend environment values and restart Vite. Enable Email/Password sign-in in Firebase Authentication.'}</CardDescription></CardHeader><CardContent>{firebaseConfigured && <form onSubmit={submit} className="operation-form" aria-busy={busy}><ErrorNotice message={error} /><label>Email address<input id="email" name="email" type="email" autoComplete="email" placeholder="you@company.com" required /></label><label>Password<input id="password" name="password" type="password" minLength={6} autoComplete={register ? 'new-password' : 'current-password'} required aria-describedby={register ? 'password-help' : undefined} />{register && <span id="password-help" className="field-help">Use at least 6 characters.</span>}</label><Button disabled={busy}>{busy ? 'Please wait…' : register ? 'Create account' : 'Sign in'}{!busy && <ArrowRight aria-hidden="true" size={18} />}</Button><div className="auth-switch"><span>{register ? 'Already have an account?' : 'New to Relay?'}</span><Button variant="ghost" type="button" disabled={busy} onClick={() => { setRegister(!register); setError('') }}>{register ? 'Sign in' : 'Create an account'}</Button></div></form>}</CardContent></Card><p className="auth-footer">Your team’s operation starts here.</p></main></div>
}
