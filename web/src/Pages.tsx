import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, calendarDate, count, instant } from './api'
import type { DataHealth } from './api'
import { ErrorPanel, LoadingPanel } from './states'

const statuses: Record<string, string> = {
  succeeded: 'Imported',
  no_change: 'Checked · unchanged',
  reactivated: 'Previous version selected',
  failed: 'Refresh failed',
  interrupted: 'Interrupted',
  running: 'In progress',
}
const qualityLabels: Record<string, string> = {
  code_unmapped: 'Cause code absent from lookup',
  route_missing: 'Missing route label',
  route_unparsed: 'Unparsed route label',
  weekday_mismatch: 'Weekday/date disagreement',
  repeated_payload: 'Rows in repeated-payload groups',
  description_encoding_suspect: 'Published description encoding issue',
  bound_missing: 'Direction not recorded',
  bound_unrecognized: 'Unrecognized direction',
  delay_zero_reported: 'Delay recorded as zero',
  gap_zero_reported: 'Gap recorded as zero',
  vehicle_zero_reported: 'Vehicle recorded as zero',
  delay_missing: 'Duration not recorded',
}

export function Health() {
  const [data, setData] = useState<DataHealth | null>(null)
  const [error, setError] = useState('')
  const [retry, setRetry] = useState(0)
  useEffect(() => {
    const controller = new AbortController()
    setError('')
    setData(null)
    api<DataHealth>('data-health', undefined, controller.signal)
      .then(setData)
      .catch((failure) => {
        if (!controller.signal.aborted)
          setError(failure instanceof Error ? failure.message : 'Data health could not be loaded.')
      })
    return () => controller.abort()
  }, [retry])
  const delay = data?.resources.find((resource) => resource.kind === 'delays')
  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">TTC BUS DATA / PROVENANCE</p>
          <h1>Data health</h1>
          <p className="page-intro">
            Where the records came from, what loaded and what needs care.
          </p>
        </div>
        <Link to="/" className="back-link">
          ← Back to the explorer
        </Link>
      </div>
      {error ? (
        <ErrorPanel message={error} retry={() => setRetry((value) => value + 1)} />
      ) : !data ? (
        <LoadingPanel />
      ) : (
        <>
          <section className="health-overview">
            <div>
              <span className="small-dot" />
              <h2>
                {delay?.active_snapshot
                  ? 'A verified import is available.'
                  : 'No delay source has been loaded yet.'}
              </h2>
            </div>
            <p>
              Coverage dates, the publisher’s update and our import time describe different things.
              A recent import can still contain older records.
            </p>
          </section>
          <div className="health-resource-grid">
            {data.resources.map((resource) => (
              <section key={resource.resource_id} className="panel resource-panel">
                <div className="panel-heading">
                  <div>
                    <p className="eyebrow">
                      {resource.kind === 'delays' ? 'PRIMARY SOURCE' : 'CAUSE DEFINITIONS'}
                    </p>
                    <h2>
                      {resource.kind === 'delays' ? 'Bus delay records' : 'Official code lookup'}
                    </h2>
                  </div>
                  <span className="status-pill">
                    {resource.active_snapshot ? 'Selected' : 'Not loaded'}
                  </span>
                </div>
                <dl className="health-facts">
                  <div>
                    <dt>Observed record dates</dt>
                    <dd>
                      {resource.coverage.start && resource.coverage.end ? (
                        <>
                          {calendarDate(resource.coverage.start)} —{' '}
                          {calendarDate(resource.coverage.end)}
                        </>
                      ) : (
                        'Not applicable / unavailable'
                      )}
                    </dd>
                  </div>
                  <div>
                    <dt>Latest attempt</dt>
                    <dd>
                      <strong>
                        {resource.latest_attempt
                          ? statuses[resource.latest_attempt.status]
                          : 'No attempt recorded'}
                      </strong>
                      <small>
                        {instant(
                          resource.latest_attempt?.finished_at ??
                            resource.latest_attempt?.started_at,
                        )}{' '}
                        Toronto time
                      </small>
                    </dd>
                  </div>
                  <div>
                    <dt>Last successful attempt</dt>
                    <dd>
                      {instant(resource.last_successful_attempt?.finished_at)}
                      <small>Includes checks that found unchanged bytes</small>
                    </dd>
                  </div>
                  <div>
                    <dt>Selected file imported</dt>
                    <dd>{instant(resource.active_snapshot?.imported_at)}</dd>
                  </div>
                  <div>
                    <dt>Publisher file update</dt>
                    <dd>
                      {resource.active_snapshot?.source_last_modified
                        ? calendarDate(resource.active_snapshot.source_last_modified.slice(0, 10))
                        : 'Not supplied'}
                      <small>Publisher timestamp has no timezone</small>
                    </dd>
                  </div>
                  <div>
                    <dt>Accepted / rejected rows</dt>
                    <dd className="mono">
                      {resource.quality
                        ? `${count(resource.quality.accepted_count)} / ${count(resource.quality.rejected_count)}`
                        : 'No successful import'}
                    </dd>
                  </div>
                </dl>
                {resource.latest_attempt?.message && (
                  <p className="notice">{resource.latest_attempt.message}</p>
                )}
                {resource.active_snapshot && (
                  <details className="provenance-details">
                    <summary>Source file and version details</summary>
                    <dl>
                      <dt>Content SHA-256</dt>
                      <dd className="mono wrap-anywhere">
                        {resource.active_snapshot.content_sha256}
                      </dd>
                      <dt>Version</dt>
                      <dd className="mono wrap-anywhere">{resource.active_snapshot.id}</dd>
                      {resource.active_snapshot.lookup_snapshot_id && (
                        <>
                          <dt>Lookup version used</dt>
                          <dd className="mono wrap-anywhere">
                            {resource.active_snapshot.lookup_snapshot_id}
                          </dd>
                        </>
                      )}
                      <dt>Retrieved</dt>
                      <dd>{instant(resource.active_snapshot.retrieved_at)} Toronto time</dd>
                      <dt>Publisher timestamp as supplied</dt>
                      <dd className="mono wrap-anywhere">
                        {resource.active_snapshot.source_last_modified ?? 'Not supplied'}
                      </dd>
                    </dl>
                    {resource.active_snapshot.source_url && (
                      <a href={resource.active_snapshot.source_url}>
                        Download this resource from the publisher ↗
                      </a>
                    )}
                  </details>
                )}
              </section>
            ))}
          </div>
          {delay?.quality && (
            <section className="panel quality-panel">
              <div className="panel-heading">
                <div>
                  <h2>Source-wide quality flags</h2>
                  <p>
                    {count(delay.quality.warning_record_count)} of{' '}
                    {count(delay.quality.accepted_count)} accepted records have at least one flag.
                    Rows remain in the explorer.
                  </p>
                </div>
                <span className="scope-label">Entire selected file</span>
              </div>
              <div className="quality-grid">
                {Object.entries(delay.quality.warning_counts)
                  .sort((a, b) => b[1] - a[1])
                  .map(([flag, value]) => (
                    <div key={flag}>
                      <span>{qualityLabels[flag] ?? flag.replaceAll('_', ' ')}</span>
                      <strong className="mono">{count(value)}</strong>
                    </div>
                  ))}
              </div>
              <p className="chart-note">
                One row may have several flags, so these counts overlap. A flag describes a
                condition, not a data-accuracy score. Reported zeroes remain numeric zeroes;
                repeated-looking rows are kept.
              </p>
            </section>
          )}
          <section className="health-explanation">
            <h2>A failed refresh leaves the previous data available.</h2>
            <p>
              Each import builds a separate version before selecting it. Corrected cumulative files
              replace the active version; they are not appended to old records. Cause descriptions
              stay tied to the lookup version used for that import.
            </p>
            <p>
              No current service exposure or live-arrival feed is included. The source cannot
              establish a trip-level delay probability or route reliability ranking.{' '}
              <Link to="/about">Read the definitions →</Link>
            </p>
          </section>
        </>
      )}
    </>
  )
}

export function About() {
  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">TTC BUS DATA / DEFINITIONS</p>
          <h1>About the data</h1>
          <p className="page-intro">
            A careful look at historical records, with the limits kept visible.
          </p>
        </div>
        <Link to="/" className="back-link">
          ← Explore the records
        </Link>
      </div>
      <section className="about-lead">
        <span className="section-number">01</span>
        <div>
          <h2>What this explorer shows</h2>
          <p>
            Select a bus route and a date range to explore historical reported delay records from
            the City of Toronto’s TTC dataset. See when records appeared, their recorded causes and
            durations, and the source rows behind each result.
          </p>
          <p>
            This is an independent project by{' '}
            <a href="https://github.com/d-wt-wu" target="_blank" rel="noreferrer">
              Wentao Wu
            </a>
            . It is not affiliated with or endorsed by the TTC or the City of Toronto.
          </p>
        </div>
      </section>
      <div className="definition-grid">
        <section>
          <span className="section-number">02</span>
          <h2>A record is not a trip.</h2>
          <p>
            A count means matching source rows. The source does not establish that every row is a
            unique incident or that every disruption was recorded. Identical-looking rows remain
            separate and are flagged for inspection.
          </p>
          <p>
            There is no denominator of all scheduled or operated trips here. More records can
            reflect more service, so counts cannot rank route reliability or estimate a trip’s
            chance of delay. This is not live-arrival data.
          </p>
        </section>
        <section>
          <span className="section-number">03</span>
          <h2>What “recorded delay” means</h2>
          <p>
            The publisher’s README defines <strong>Min Delay</strong> as minutes of delay to the
            schedule for the following bus. <strong>Min Gap</strong> is a separate schedule-related
            field. They are not added together or interpreted as passenger time lost.
          </p>
          <p>
            The median includes valid nonnegative numeric values, including reported zeroes, and
            always shows its sample count. Missing or invalid durations are excluded, never turned
            into zero. The source does not explain whether some zeroes are operational placeholders.
          </p>
        </section>
        <section>
          <span className="section-number">04</span>
          <h2>Dates and missing periods</h2>
          <p>
            Filters include both the start and end date, using the Date field as recorded. Record
            times stay separate. The source’s timezone and overnight service-day rules are
            unconfirmed, so an hour heatmap is not shown.
          </p>
          <p>
            A chart omits dates without matching rows. An absent date is not proof of zero
            disruptions. An empty result means no matching records in the loaded data.
          </p>
        </section>
        <section>
          <span className="section-number">05</span>
          <h2>Labels and unknown values</h2>
          <p>
            Route identifiers come from historical route labels; branches such as 102 and 102D
            remain separate. Shuttle/free-text labels and missing route values remain available in
            the all-routes view.
          </p>
          <p>
            Cause codes use a versioned official lookup. Unknown codes are shown as unmapped, and
            published description-encoding issues are flagged rather than silently corrected.
            Coverage bounds do not guarantee complete reporting.
          </p>
        </section>
      </div>
      <section className="about-source">
        <span className="section-number">06</span>
        <div>
          <h2>Follow a result back to its source</h2>
          <p>
            Each table entry includes its CSV row position. That position belongs to the selected
            file version, not a permanent incident ID. <Link to="/data-health">Data health</Link>{' '}
            shows the file’s source, hash, coverage, import attempts and flags.
          </p>
          <p>
            <a
              href="https://open.toronto.ca/dataset/ttc-bus-delay-data/"
              target="_blank"
              rel="noreferrer"
            >
              Official TTC Bus Delay Data ↗
            </a>
            <br />
            Contains information licensed under the{' '}
            <a href="https://open.toronto.ca/open-data-licence/" target="_blank" rel="noreferrer">
              Open Government Licence – Toronto
            </a>
            .
          </p>
        </div>
      </section>
    </>
  )
}
