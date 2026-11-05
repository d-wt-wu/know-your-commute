import { Link } from 'react-router-dom'

export function ErrorPanel({ message, retry }: { message: string; retry: () => void }) {
  return (
    <section className="state-panel error-panel" role="alert">
      <span className="state-symbol" aria-hidden="true">
        !
      </span>
      <h2>We couldn’t load the records.</h2>
      <p>{message}</p>
      <button className="button secondary" onClick={retry}>
        Try again
      </button>
      <Link to="/data-health">
        Check data health <span aria-hidden="true">↗</span>
      </Link>
    </section>
  )
}

export function LoadingPanel() {
  return (
    <section className="loading-panel" aria-busy="true">
      <p role="status">Loading historical records…</p>
      <div className="skeleton-metrics">
        <i />
        <i />
        <i />
      </div>
      <div className="skeleton-chart" />
    </section>
  )
}
