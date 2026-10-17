import { useEffect, useRef, useState, type KeyboardEvent } from 'react'
import { Button } from '@/components/ui/button'
import photoCredits from '../../public/images/credits.json'
import highwayPhoto from '@/assets/landing/provincial-highway-66-interchange-with-city-highway.jpg'
import warehousePhoto from '@/assets/landing/modern-warehouse-with-pallet-rack-storage-system.jpg'
import loadingPhoto from '@/assets/landing/pallets-imported-fruit-await-distribution.webp'
import valleyPhoto from '@/assets/landing/aerial-view-of-glenn-highway-and-old.jpg'
import './landing.css'

const stages = [
  { title: 'Your workspace', text: 'Create an organization for the people and information behind your deliveries. Workspace membership controls who can manage its records.' },
  { title: 'Your fleet', text: 'Add each vehicle, its driver, carrying capacity, and availability. Keep those details current as the day changes.' },
  { title: 'Your deliveries', text: 'Record the customer, destination, load, and delivery window. Add coordinates when you want a location on the map.' },
]

const questions = [
  { question: 'What can I use today?', answer: 'You can create a workspace, manage delivery and vehicle records, and view saved coordinates on Google Maps when Maps is configured.' },
  { question: 'Does Relay dispatch for me?', answer: 'Not yet. Vehicle assignment, fleet route optimization, and approved breakdown recovery are planned. Today, Relay helps you organize the records those workflows need.' },
  { question: 'Who can change my records?', answer: 'The backend checks your signed-in identity and organization membership. Workspace owners and dispatchers can manage records; driver workflows are planned.' },
  { question: 'Do I need a Maps key?', answer: 'You can manage deliveries and vehicles without one. A Google Maps browser key is needed to show saved locations, and separate server configuration enables address and route tools.' },
]

function Arrow({ large = false }: { large?: boolean }) {
  return <svg className={large ? 'lp-arrow-large' : 'lp-arrow'} viewBox="0 0 32 32" fill="none" aria-hidden="true"><path d="M7 25 25 7M7 7h18v18" stroke="currentColor" strokeWidth="2" /></svg>
}

function WorkspaceExplorer() {
  const [view, setView] = useState<'deliveries' | 'fleet'>('deliveries')
  const delivery = view === 'deliveries'
  function navigate(event: KeyboardEvent<HTMLButtonElement>) {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return
    event.preventDefault()
    const next = event.key === 'Home' ? 'deliveries' : event.key === 'End' ? 'fleet' : delivery ? 'fleet' : 'deliveries'
    setView(next)
    document.getElementById(`lp-tab-${next}`)?.focus()
  }
  return <div className="lp-explorer" data-ui>
    <div className="lp-explorer-top"><span>relay.</span><span>Workspace preview</span></div>
    <div className="lp-preview-tabs" role="tablist" aria-label="Explore the workspace">
      {(['deliveries', 'fleet'] as const).map(item => <button key={item} type="button" id={`lp-tab-${item}`} role="tab" aria-selected={view === item} aria-controls="lp-preview-panel" tabIndex={view === item ? 0 : -1} onKeyDown={navigate} onClick={() => setView(item)}>{item === 'deliveries' ? 'Deliveries' : 'Fleet'}</button>)}
    </div>
    <div className="lp-preview-panel" role="tabpanel" id="lp-preview-panel" aria-labelledby={`lp-tab-${view}`} tabIndex={0}>
      <h3>{delivery ? 'Delivery details' : 'Vehicle details'}</h3>
      <p>{delivery ? 'The information behind every stop.' : 'Know what each vehicle can carry.'}</p>
      <fieldset disabled aria-label="Read-only product preview">
        <label>{delivery ? 'Customer name' : 'Registration'}<input placeholder={delivery ? 'Customer name' : 'Vehicle registration'} /></label>
        <label>{delivery ? 'Delivery address' : 'Driver name'}<input placeholder={delivery ? 'Street, area, and city' : 'Driver name'} /></label>
        <div className="lp-preview-pair">
          <label>{delivery ? 'Load (kg)' : 'Capacity (kg)'}<input placeholder="Weight in kilograms" /></label>
          <label>{delivery ? 'Delivery window' : 'Availability'}<input placeholder={delivery ? 'Start and end time' : 'Available / unavailable'} /></label>
        </div>
      </fieldset>
      <p className="lp-preview-note">A preview of the current fields. No live records are shown.</p>
    </div>
  </div>
}

export default function Landing() {
  const root = useRef<HTMLDivElement>(null)
  const [stage, setStage] = useState(0)
  const [question, setQuestion] = useState(0)
  useEffect(() => {
    const preference = window.matchMedia('(prefers-reduced-motion: reduce)')
    if (preference.matches || !('IntersectionObserver' in window)) return
    const animations: Animation[] = []
    const observer = new IntersectionObserver(entries => {
      for (const entry of entries) {
        if (!entry.isIntersecting) continue
        const element = entry.target as HTMLElement
        const shutter = element.hasAttribute('data-shutter')
        animations.push(element.animate(shutter
          ? [{ clipPath: 'inset(0 100% 0 0)', transform: 'scale(1.04)' }, { clipPath: 'inset(0 0 0 0)', transform: 'scale(1)' }]
          : [{ opacity: 0.25, transform: 'translateY(18px)' }, { opacity: 1, transform: 'translateY(0)' }],
        { duration: shutter ? 1050 : 560, delay: Number(element.dataset.enter || 0), easing: 'cubic-bezier(.22,1,.36,1)' }))
        observer.unobserve(element)
      }
    }, { threshold: 0.1 })
    root.current?.querySelectorAll('[data-enter], [data-shutter]').forEach(element => observer.observe(element))
    const stop = () => { if (preference.matches) { animations.forEach(animation => animation.cancel()); observer.disconnect() } }
    preference.addEventListener('change', stop)
    return () => { observer.disconnect(); animations.forEach(animation => animation.cancel()); preference.removeEventListener('change', stop) }
  }, [])

  return <div className="relay-landing" ref={root}>
    <a className="lp-skip" href="#landing-main">Skip to content</a>
    <header className="lp-header">
      <a className="lp-wordmark" href="/" aria-label="Relay home">relay.</a>
      <nav className="lp-navigation" aria-label="Landing page"><a href="#workspace">The workspace</a><a href="#getting-started">Getting started</a><a href="#questions">Questions</a></nav>
      <a className="lp-signin" href="/app">Sign in <Arrow /></a>
    </header>

    <main id="landing-main">
      <section className="lp-board lp-hero" aria-labelledby="lp-headline">
        <div className="lp-tile lp-hero-copy">
          <h1 id="lp-headline" data-enter="0">A better<br />handoff.</h1>
          <p data-enter="70">Bring your deliveries and fleet into one workspace, so the next decision starts with the right information.</p>
          <Button asChild className="lp-button lp-hero-enter" data-enter="140"><a href="/app">Open your workspace <Arrow /></a></Button>
        </div>
        <figure className="lp-tile lp-hero-photo" data-shutter>
          <img src={highwayPhoto} alt="An aerial view of roads connecting fields and neighborhoods in Taiwan" width="1280" height="853" fetchPriority="high" />
          <figcaption>The work between here and there.</figcaption>
        </figure>
        <div className="lp-tile lp-hero-facts" data-enter="100">
          <p>Every stop has details.<br />Every vehicle has limits.</p>
          <span>Keep them together.</span>
        </div>
        <a className="lp-tile lp-action-tile" href="/app" data-enter="160">
          <Arrow large />
          <span>Open your<br />workspace</span>
          <small>Sign in or create an account</small>
        </a>
      </section>

      <section className="lp-board lp-workspace" id="workspace" aria-labelledby="lp-workspace-title">
        <div className="lp-tile lp-workspace-copy">
          <h2 id="lp-workspace-title" data-enter="0">The day,<br />in one place.</h2>
          <p data-enter="70">Customer details, delivery windows, vehicle capacity, and availability. A shared starting point for the people making the calls.</p>
          <p className="lp-small" data-enter="140">Explore the current delivery and fleet fields. Your own workspace starts empty, ready for your operation.</p>
        </div>
        <div className="lp-tile lp-demo-tile" data-enter="100"><WorkspaceExplorer /></div>
        <figure className="lp-tile lp-depot-photo" data-enter="0"><img src={warehousePhoto} alt="Pallet racks and boxed goods inside a distribution warehouse" width="1920" height="1496" loading="lazy" /><figcaption>A place for what needs to move.</figcaption></figure>
        <div className="lp-tile lp-record-note" data-enter="80"><p>Change a detail.<br />Keep the context.</p><span>When another person has changed a record, Relay asks you to refresh before saving over it.</span></div>
      </section>

      <section className="lp-process" id="getting-started" aria-labelledby="lp-process-title">
        <div className="lp-section-intro"><h2 id="lp-process-title" data-enter="0">Start with<br />what you know.</h2><p data-enter="70">Build the picture of your operation before planning the next move.</p></div>
        <div className="lp-stage-board">
          {stages.map((item, index) => <article key={item.title} className={`lp-stage lp-stage-${index} ${stage === index ? 'is-open' : ''}`} data-enter={String(index * 70)}>
            <button type="button" aria-expanded={stage === index} aria-controls={`lp-stage-${index}`} onClick={() => setStage(index)}>{item.title}<span aria-hidden="true">{stage === index ? '−' : '+'}</span></button>
            <div id={`lp-stage-${index}`} hidden={stage !== index}><p>{item.text}</p><a href="/app?mode=signup">Create your workspace <span aria-hidden="true">↗</span></a></div>
          </article>)}
        </div>
      </section>

      <section className="lp-board lp-next" aria-labelledby="lp-next-title">
        <figure className="lp-tile lp-loading-photo" data-enter="0"><img src={loadingPhoto} alt="A forklift moving fruit pallets at a distribution facility" width="1024" height="662" loading="lazy" /></figure>
        <div className="lp-tile lp-next-copy"><h2 id="lp-next-title" data-enter="0">The next move.</h2><p data-enter="70">Assignment, fleet route optimization, and breakdown recovery are the next stage of Relay.</p><p className="lp-small" data-enter="140">Today, the workspace manages delivery and vehicle records. Dispatch and recovery workflows are planned, with dispatcher approval before assignments change.</p></div>
      </section>

      <section className="lp-questions" id="questions" aria-labelledby="lp-questions-title">
        <div className="lp-question-list"><h2 id="lp-questions-title" data-enter="0">Good questions.</h2>{questions.map((item, index) => <button key={item.question} type="button" aria-pressed={question === index} aria-controls="lp-answer" onClick={() => setQuestion(index)} data-enter={String(index * 65)}><span aria-hidden="true" />{item.question}</button>)}</div>
        <div className="lp-answer" id="lp-answer" role="region" aria-label={questions[question].question} aria-live="polite" aria-atomic="true"><p key={question}>{questions[question].answer}</p></div>
      </section>

      <section className="lp-board lp-close" aria-labelledby="lp-close-title">
        <figure className="lp-tile lp-close-photo" data-enter="0"><img src={valleyPhoto} alt="A highway interchange crossing a green valley below mountains in Alaska" width="1872" height="1376" loading="lazy" /></figure>
        <div className="lp-tile lp-close-action"><h2 id="lp-close-title" data-enter="0">Put the day<br />in order.</h2><p data-enter="70">Start with your organization, your vehicles, and the deliveries ahead.</p><Button asChild className="lp-button" data-enter="140"><a href="/app?mode=signup">Create your workspace <Arrow /></a></Button></div>
        <div className="lp-tile lp-close-note" data-enter="90"><p>Your information.<br />A shared starting point.</p><a href="/app">Already have a workspace? Sign in <span aria-hidden="true">↗</span></a></div>
      </section>
    </main>

    <footer className="lp-footer">
      <div className="lp-footer-mark" aria-hidden="true">{'relay'.split('').map((letter, index) => <span key={letter} className={`lp-letter-${index}`}>{letter}</span>)}</div>
      <div className="lp-footer-links"><a href="/app">Workspace</a><a href="#questions">Questions</a><a href="https://github.com/solstxce/agent-war" target="_blank" rel="noreferrer">Source code ↗</a><span>© {new Date().getFullYear()} Relay</span></div>
      <details className="lp-image-credits"><summary>Photography credits</summary><p>These photographs show the wider world of transport and distribution, not Relay customers or facilities. Images are displayed with responsive cropping and retain their listed licenses.</p><ul>{photoCredits.map(photo => <li key={photo.ref}><a href={photo.page} target="_blank" rel="noreferrer">{photo.title}</a>{photo.creator ? ` — ${photo.creator}` : ''}. <a href={photo.licenseUrl} target="_blank" rel="noreferrer">{photo.license}</a>, via {photo.via}.</li>)}</ul></details>
    </footer>
  </div>
}
