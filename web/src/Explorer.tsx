import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api, calendarDate, count, instant } from './api'
import { ErrorPanel, LoadingPanel } from './states'
import type { Patterns, RecordPage, RouteCatalog, Summary } from './api'

type View = { summary: Summary; patterns: Patterns; records: RecordPage }
const chartTooltip = {
  background: '#fffdf8',
  border: '1px solid #d8d6cd',
  borderRadius: 6,
  color: '#262c28',
  fontSize: 13,
}

export default function Explorer({
  catalog,
  catalogError,
  retryCatalog,
}: {
  catalog: RouteCatalog | null
  catalogError: string
  retryCatalog: () => void
}) {
  if (catalogError) return <ErrorPanel message={catalogError} retry={retryCatalog} />
  if (!catalog) return <LoadingPanel />
  return <ExplorerReady catalog={catalog} />
}

function ExplorerReady({ catalog }: { catalog: RouteCatalog }) {
  const [params, setParams] = useSearchParams()
  const coverage = catalog.context.coverage
  const route = params.get('route') ?? ''
  const start = params.get('start') ?? `${coverage.end!.slice(0, 7)}-01`
  const end = params.get('end') ?? coverage.end!
  const page = params.get('page') ?? '1'
  const sort = params.get('sort') ?? 'date_desc'
  const [draft, setDraft] = useState({ route, start, end })
  const [view, setView] = useState<View | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [refresh, setRefresh] = useState(0)
  const pinned = useRef<{ key: string; id: string } | null>(null)
  const key = JSON.stringify({ route, start, end })
  const sameSelection =
    view?.summary.context.filters.route === (route.trim() || null) &&
    view?.summary.context.filters.start === start &&
    view?.summary.context.filters.end === end

  useEffect(() => {
    setDraft({ route, start, end })
  }, [route, start, end])
  useEffect(() => {
    if (!params.has('start') || !params.has('end')) {
      const explicit = new URLSearchParams(params)
      explicit.set('start', start)
      explicit.set('end', end)
      setParams(explicit, { replace: true })
    }
  }, [params, start, end, setParams])

  useEffect(() => {
    const controller = new AbortController()
    setLoading(true)
    setError('')
    const selected = new URLSearchParams({ start, end })
    if (route) selected.set('route', route)
    if (pinned.current?.key === key) selected.set('snapshot_id', pinned.current.id)
    void (async () => {
      try {
        const summary = await api<Summary>('summary', selected, controller.signal)
        selected.set('snapshot_id', summary.context.snapshot.id)
        const recordParams = new URLSearchParams(selected)
        recordParams.set('page', page)
        recordParams.set('page_size', '25')
        recordParams.set('sort', sort)
        const [patterns, records] = await Promise.all([
          api<Patterns>('patterns', selected, controller.signal),
          api<RecordPage>('records', recordParams, controller.signal),
        ])
        if (!controller.signal.aborted) {
          pinned.current = { key, id: summary.context.snapshot.id }
          setView({ summary, patterns, records })
          setLoading(false)
        }
      } catch (failure) {
        if (!controller.signal.aborted) {
          setError(failure instanceof Error ? failure.message : 'Please try again.')
          setLoading(false)
        }
      }
    })()
    return () => controller.abort()
  }, [route, start, end, page, sort, key, refresh])

  function apply(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const submitted = new FormData(event.currentTarget)
    const next = new URLSearchParams({
      start: String(submitted.get('start')),
      end: String(submitted.get('end')),
    })
    const submittedRoute = String(submitted.get('route') ?? '').trim()
    if (submittedRoute) next.set('route', submittedRoute)
    if (sort !== 'date_desc') next.set('sort', sort)
    setParams(next)
  }
  function changePage(value: number) {
    const next = new URLSearchParams(params)
    value === 1 ? next.delete('page') : next.set('page', String(value))
    setParams(next)
  }
  function changeSort(value: string) {
    const next = new URLSearchParams(params)
    next.set('sort', value)
    next.delete('page')
    setParams(next)
  }
  function retry() {
    pinned.current = null
    setRefresh((value) => value + 1)
  }

  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">TTC BUS DATA / EXPLORER</p>
          <h1>Route explorer</h1>
          <p className="page-intro">
            Look through reported disruptions and the records behind them.
          </p>
        </div>
        <div className="coverage-block">
          <span className="eyebrow">LOADED RECORD DATES</span>
          <strong>
            {calendarDate(coverage.start!, true)}, {coverage.start!.slice(0, 4)} <span>—</span>{' '}
            {calendarDate(coverage.end!, true)}, {coverage.end!.slice(0, 4)}
          </strong>
          <span className="quiet">Historical records · refreshed by the publisher monthly</span>
        </div>
      </div>

      <form className="filter-panel" onSubmit={apply}>
        <div className="route-field">
          <label htmlFor="route">Bus route</label>
          <input
            name="route"
            id="route"
            list="route-options"
            placeholder="All recorded routes"
            value={draft.route}
            autoComplete="off"
            onChange={(e) => setDraft({ ...draft, route: e.target.value })}
          />
          <datalist id="route-options">
            {catalog.routes.map((r) => (
              <option key={r.identifier} value={r.identifier}>
                {r.labels[0]}
              </option>
            ))}
          </datalist>
          <span className="field-help">Type a route number. Branches stay separate.</span>
        </div>
        <div>
          <label htmlFor="start">From</label>
          <input
            name="start"
            id="start"
            type="date"
            required
            value={draft.start}
            max={draft.end || undefined}
            onChange={(e) => setDraft({ ...draft, start: e.target.value })}
          />
          <span className="field-help">Recorded date, inclusive</span>
        </div>
        <div>
          <label htmlFor="end">To</label>
          <input
            name="end"
            id="end"
            type="date"
            required
            value={draft.end}
            min={draft.start || undefined}
            onChange={(e) => setDraft({ ...draft, end: e.target.value })}
          />
          <span className="field-help">Recorded date, inclusive</span>
        </div>
        <button className="button primary" type="submit">
          Explore records <span aria-hidden="true">→</span>
        </button>
      </form>

      {error ? (
        <ErrorPanel message={error} retry={retry} />
      ) : (loading && !sameSelection) || !view ? (
        <LoadingPanel />
      ) : (
        <>
          {loading && (
            <span className="sr-only" role="status">
              Updating matching records…
            </span>
          )}
          <div className="result-heading">
            <h2>
              {route ? (
                <>
                  Route <span className="route-badge">{route}</span>
                </>
              ) : (
                'All recorded routes'
              )}{' '}
              <span className="date-heading">
                / {calendarDate(start, start.slice(0, 4) === end.slice(0, 4))} – {calendarDate(end)}
              </span>
            </h2>
            <button
              className="text-button"
              onClick={retry}
              aria-label="Check for a newer imported source"
            >
              ↻ <span>Check for updated data</span>
            </button>
          </div>
          {view.summary.context.extends_beyond_loaded_dates && (
            <p className="notice" role="status">
              Your range extends beyond the loaded record dates. Results include only the available
              records.
            </p>
          )}
          <div className="metric-grid">
            <Metric
              label="Reported records"
              value={count(view.summary.summary.reported_records)}
              note="Matching rows in the selected source"
            />
            <Metric
              label="Median recorded delay"
              value={
                view.summary.summary.median_recorded_delay_minutes === null
                  ? '—'
                  : `${view.summary.summary.median_recorded_delay_minutes.toLocaleString('en-CA')} min`
              }
              note="Delay to the following bus’s schedule"
            />
            <Metric
              label="Numeric duration samples"
              value={count(view.summary.summary.valid_delay_samples)}
              note={`${count(view.summary.summary.zero_delay_samples)} reported zero${view.summary.summary.zero_delay_samples === 1 ? '' : 'es'} included; missing values excluded`}
            />
          </div>
          <p className="metric-footnote">
            Record counts describe what was reported. They do not estimate a trip’s chance of delay.{' '}
            <Link to="/about">
              How to read this data <span aria-hidden="true">↗</span>
            </Link>
          </p>
          {view.summary.summary.reported_records === 0 ? (
            <section className="state-panel empty-panel">
              <span className="state-symbol" aria-hidden="true">
                ∅
              </span>
              <h2>No matching records in the loaded data.</h2>
              <p>
                Try another route or date range. An empty result does not mean that a route never
                has delays.
              </p>
            </section>
          ) : (
            <Charts patterns={view.patterns} />
          )}
          <RecordTable
            data={view.records}
            onPage={changePage}
            onSort={changeSort}
            loading={loading}
          />
          <div className="source-strip">
            <div>
              <span className="small-dot" />
              <span>
                <strong>Traceable to the source.</strong>{' '}
                {count(view.summary.summary.flagged_records)} matching records carry one or more
                quality flags.
              </span>
            </div>
            <Link to="/data-health">
              Inspect data health <span aria-hidden="true">↗</span>
            </Link>
          </div>
          <p className="source-timestamp">
            Selected file imported {instant(view.summary.context.snapshot.imported_at)} Toronto
            time. Source date coverage and import time are separate.{' '}
            <Link to="/about">Definitions</Link>
          </p>
        </>
      )}
    </>
  )
}

function Metric({ label, value, note }: { label: string; value: string; note: string }) {
  return (
    <section className="metric">
      <h3>{label}</h3>
      <p className="metric-value">{value}</p>
      <p className="metric-note">{note}</p>
    </section>
  )
}

function Charts({ patterns }: { patterns: Patterns }) {
  const causes = patterns.causes.slice(0, 8)
  return (
    <div className="chart-grid">
      <section className="panel trend-panel">
        <div className="panel-heading">
          <div>
            <h2>Records over time</h2>
            <p>Daily counts · dates as recorded</p>
          </div>
          <span className="legend">
            <i /> Reported records
          </span>
        </div>
        <div
          className="chart"
          role="img"
          aria-label={`Daily reported record counts for ${patterns.daily_records.length} observed dates. A complete data table follows.`}
        >
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={patterns.daily_records}
              margin={{ top: 12, right: 9, bottom: 4, left: -23 }}
            >
              <CartesianGrid vertical={false} stroke="#e9e6de" />
              <XAxis
                dataKey="report_date"
                tickFormatter={(value) => calendarDate(String(value), true)}
                tick={{ fill: '#6c6d64', fontSize: 11 }}
                minTickGap={40}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                tick={{ fill: '#6c6d64', fontSize: 11 }}
                allowDecimals={false}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip
                cursor={{ fill: '#f2eee3' }}
                contentStyle={chartTooltip}
                labelFormatter={(label) => calendarDate(String(label))}
                formatter={(value) => [count(Number(value)), 'Reported records']}
              />
              <Bar
                dataKey="reported_records"
                fill="#c68c34"
                radius={[2, 2, 0, 0]}
                isAnimationActive={false}
                maxBarSize={28}
              />
            </BarChart>
          </ResponsiveContainer>
        </div>
        <p className="chart-note">
          Dates without matching records are omitted, rather than filled with zero.
        </p>
        <details className="chart-details">
          <summary>
            View daily counts <span>({patterns.daily_records.length} dates)</span>
          </summary>
          <div className="detail-scroll">
            <table>
              <thead>
                <tr>
                  <th>Date</th>
                  <th className="number">Reported records</th>
                </tr>
              </thead>
              <tbody>
                {patterns.daily_records.map((row) => (
                  <tr key={row.report_date}>
                    <td>{calendarDate(row.report_date)}</td>
                    <td className="number">{count(row.reported_records)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      </section>
      <section className="panel causes-panel">
        <div className="panel-heading">
          <div>
            <h2>Recorded causes</h2>
            <p>
              {causes.length === patterns.causes.length
                ? 'All'
                : `Top ${causes.length} of ${patterns.causes.length}`}{' '}
              source codes · by record count
            </p>
          </div>
        </div>
        <div
          className="chart"
          role="img"
          aria-label="Reported records by source cause code. Descriptions and counts are in the following table."
        >
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              layout="vertical"
              data={causes}
              margin={{ top: 6, bottom: 0, left: -4, right: 30 }}
            >
              <XAxis type="number" hide />
              <YAxis
                type="category"
                dataKey="incident_code"
                width={63}
                tick={{ fill: '#5d625b', fontSize: 11, fontFamily: 'ui-monospace, monospace' }}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip
                cursor={{ fill: '#f2eee3' }}
                contentStyle={chartTooltip}
                formatter={(value) => [count(Number(value)), 'Reported records']}
              />
              <Bar
                dataKey="reported_records"
                fill="#535d50"
                radius={[0, 3, 3, 0]}
                maxBarSize={17}
                isAnimationActive={false}
                label={{ position: 'right', fill: '#535d50', fontSize: 11 }}
              />
            </BarChart>
          </ResponsiveContainer>
        </div>
        <p className="chart-note">
          Unmapped codes remain in the results. Descriptions are published values.
        </p>
        <details className="chart-details">
          <summary>
            View all cause descriptions <span>({patterns.causes.length})</span>
          </summary>
          <div className="detail-scroll">
            <table>
              <thead>
                <tr>
                  <th>Cause / source code</th>
                  <th className="number">Records</th>
                </tr>
              </thead>
              <tbody>
                {patterns.causes.map((row) => (
                  <tr key={row.incident_code ?? 'missing'}>
                    <td>
                      <strong className="mono">{row.incident_code ?? 'Missing code'}</strong>
                      <small>{row.description ?? 'Unmapped code'}</small>
                    </td>
                    <td className="number">{count(row.reported_records)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      </section>
    </div>
  )
}

const flagLabels: Record<string, string> = {
  description_encoding_suspect: 'Published code description has an encoding issue',
  code_unmapped: 'Code is absent from the official lookup',
  route_missing: 'No route label recorded',
  route_unparsed: 'Route label cannot be parsed as an identifier',
  weekday_mismatch: 'Source weekday and calendar date disagree',
  repeated_payload: 'Another row has the same recorded values; both are kept',
  bound_missing: 'No direction recorded',
  bound_unrecognized: 'Direction value is unrecognized',
  delay_zero_reported: 'Delay is recorded as zero',
  gap_zero_reported: 'Gap is recorded as zero',
  vehicle_zero_reported: 'Vehicle is recorded as zero',
  delay_missing: 'No delay duration recorded',
  delay_invalid: 'Delay duration is not a valid nonnegative integer',
  time_invalid: 'Time value cannot be parsed',
}

function RecordTable({
  data,
  onPage,
  onSort,
  loading,
}: {
  data: RecordPage
  onPage: (page: number) => void
  onSort: (sort: string) => void
  loading: boolean
}) {
  const first = data.records.length ? (data.page - 1) * data.page_size + 1 : 0
  const last = data.records.length ? first + data.records.length - 1 : 0
  return (
    <section className="panel records-panel" aria-busy={loading}>
      <div className="panel-heading">
        <div>
          <h2>Matching source records</h2>
          <p>Inspect the entries behind the charts. Missing durations are shown as a dash.</p>
        </div>
        <label className="sort-label">
          Order{' '}
          <select
            aria-label="Sort records"
            value={data.sort}
            onChange={(event) => onSort(event.target.value)}
          >
            <option value="date_desc">Newest date first</option>
            <option value="date_asc">Oldest date first</option>
          </select>
        </label>
      </div>
      <div
        className="table-scroll"
        tabIndex={0}
        role="region"
        aria-label="Matching source records table"
      >
        <table className="record-table">
          <thead>
            <tr>
              <th>Recorded date / time</th>
              <th>Route / location</th>
              <th>Reported cause</th>
              <th className="number">Delay</th>
              <th className="number">Gap</th>
              <th>Source row / notes</th>
            </tr>
          </thead>
          <tbody>
            {data.records.map((row) => (
              <tr key={row.row_number}>
                <td className="date-cell">
                  {calendarDate(row.report_date, true)}, {row.report_date.slice(0, 4)}
                  <small className="mono">
                    {row.report_time?.slice(0, 5) ?? 'Time unavailable'}
                  </small>
                </td>
                <td>
                  <span className="route-table-label">{row.route_label ?? 'Unassigned route'}</span>
                  <small>{row.location ?? 'Location not recorded'}</small>
                </td>
                <td>
                  <span className="mono code-label">{row.incident_code ?? 'Missing code'}</span>
                  <small>{row.description ?? 'Unmapped code'}</small>
                </td>
                <td className="number duration-cell">
                  {row.delay_minutes === null ? (
                    <span aria-label="Duration unavailable">—</span>
                  ) : (
                    <>
                      {count(row.delay_minutes)}
                      <small>min</small>
                    </>
                  )}
                </td>
                <td className="number duration-cell">
                  {row.gap_minutes === null ? (
                    <span aria-label="Gap unavailable">—</span>
                  ) : (
                    <>
                      {count(row.gap_minutes)}
                      <small>min</small>
                    </>
                  )}
                </td>
                <td>
                  <span className="mono quiet">#{row.row_number}</span>
                  {row.quality_flags.length > 0 && (
                    <details className="row-flags">
                      <summary aria-label={`Quality flags for source row ${row.row_number}`}>
                        {row.quality_flags.length} flag{row.quality_flags.length === 1 ? '' : 's'}
                      </summary>
                      <ul>
                        {row.quality_flags.map((flag) => (
                          <li key={flag}>{flagLabels[flag] ?? flag.replaceAll('_', ' ')}</li>
                        ))}
                      </ul>
                    </details>
                  )}
                </td>
              </tr>
            ))}
            {data.records.length === 0 && (
              <tr>
                <td colSpan={6} className="no-table-records">
                  {data.total_records
                    ? 'No records on this page. Return to an earlier page.'
                    : 'No matching source records.'}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <div className="pagination">
        <span aria-live="polite">
          {count(first)}–{count(last)} of {count(data.total_records)} records
        </span>
        <div>
          <button
            aria-label="Previous page"
            className="page-button"
            onClick={() => {
              if (!loading) onPage(data.page - 1)
            }}
            aria-disabled={loading || data.page <= 1}
            disabled={data.page <= 1}
          >
            ← <span>Previous</span>
          </button>
          <span className="page-count">
            {data.total_pages ? `Page ${data.page} of ${data.total_pages}` : 'No pages'}
          </span>
          <button
            aria-label="Next page"
            className="page-button"
            onClick={() => {
              if (!loading) onPage(data.page + 1)
            }}
            aria-disabled={loading || data.page >= data.total_pages}
            disabled={data.page >= data.total_pages}
          >
            Next <span aria-hidden="true">→</span>
          </button>
        </div>
      </div>
    </section>
  )
}
