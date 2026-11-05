import { lazy, Suspense, useEffect, useState } from 'react'
import { Link, NavLink, Route, Routes } from 'react-router-dom'
import { api } from './api'
import type { RouteCatalog } from './api'
import { LoadingPanel } from './states'

const Explorer = lazy(() => import('./Explorer'))
const About = lazy(() => import('./Pages').then((module) => ({ default: module.About })))
const Health = lazy(() => import('./Pages').then((module) => ({ default: module.Health })))

export default function App() {
  const [catalog, setCatalog] = useState<RouteCatalog | null>(null)
  const [error, setError] = useState('')
  const [retry, setRetry] = useState(0)
  useEffect(() => {
    const controller = new AbortController()
    setError('')
    api<RouteCatalog>('routes', undefined, controller.signal)
      .then(setCatalog)
      .catch((failure) => {
        if (!controller.signal.aborted)
          setError(failure instanceof Error ? failure.message : 'The source could not be loaded.')
      })
    return () => controller.abort()
  }, [retry])

  return (
    <>
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <header className="site-header">
        <div className="header-inner">
          <Link to="/" className="brand" aria-label="Know Your Commute home">
            <img src="/favicon.svg" alt="" width="37" height="37" />
            <span>
              Know Your Commute<small>TTC DELAY EXPLORER</small>
            </span>
          </Link>
          <nav aria-label="Main navigation">
            <NavLink to="/" end>
              Explorer
            </NavLink>
            <NavLink to="/data-health">Data health</NavLink>
            <NavLink to="/about">About</NavLink>
          </nav>
          <span className="historical-badge">
            <i /> Historical data
          </span>
        </div>
      </header>
      <main id="main" className="workspace">
        <Suspense fallback={<LoadingPanel />}>
          <Routes>
            <Route
              path="/"
              element={
                <Explorer
                  catalog={catalog}
                  catalogError={error}
                  retryCatalog={() => setRetry((value) => value + 1)}
                />
              }
            />
            <Route path="/data-health" element={<Health />} />
            <Route path="/about" element={<About />} />
            <Route
              path="*"
              element={
                <section className="state-panel">
                  <h1>Page not found.</h1>
                  <p>
                    <Link to="/">Return to the route explorer</Link>
                  </p>
                </section>
              }
            />
          </Routes>
        </Suspense>
      </main>
      <footer className="site-footer">
        <div>
          <strong>Know Your Commute</strong>
          <span>Independent project by Wentao Wu.</span>
        </div>
        <div>
          <a
            href="https://open.toronto.ca/dataset/ttc-bus-delay-data/"
            target="_blank"
            rel="noreferrer"
          >
            City of Toronto / TTC source <span aria-hidden="true">↗</span>
          </a>
          <span>
            Contains information licensed under the{' '}
            <a href="https://open.toronto.ca/open-data-licence/" target="_blank" rel="noreferrer">
              Open Government Licence – Toronto
            </a>
            .
          </span>
        </div>
      </footer>
    </>
  )
}
