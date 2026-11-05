export type Coverage = { start: string | null; end: string | null; meaning: string }
export type SourceSnapshot = {
  id: string
  resource_id: string
  content_sha256: string
  lookup_snapshot_id: string | null
  source_url: string | null
  dataset_url: string
  source_last_modified: string | null
  source_metadata_modified: string | null
  retrieved_at: string
  imported_at: string
  parser_version: string
  contract_version: string
}
export type Context = {
  snapshot: SourceSnapshot
  filters: { route: string | null; start: string; end: string; date_bounds: string }
  coverage: Coverage
  extends_beyond_loaded_dates: boolean
}
export type Quality = {
  scope: string
  raw_count: number
  accepted_count: number
  rejected_count: number
  warning_record_count: number
  warning_counts: Record<string, number>
  extra_columns: string[]
}
export type Summary = {
  context: Context
  quality: Quality
  definitions: Record<string, string>
  summary: {
    reported_records: number
    valid_delay_samples: number
    zero_delay_samples: number
    median_recorded_delay_minutes: number | null
    mean_recorded_delay_minutes: number | null
    valid_gap_samples: number
    flagged_records: number
    first_matching_date: string | null
    last_matching_date: string | null
  }
}
export type Patterns = {
  context: Context
  daily_records: { report_date: string; reported_records: number }[]
  causes: {
    incident_code: string | null
    description: string | null
    mapping_status: string
    reported_records: number
  }[]
  calendar_weekdays: { iso_weekday: number; reported_records: number }[]
  missing_dates_meaning: string
  time_analysis_note: string
}
export type SourceRecord = {
  row_number: number
  source_id: string | null
  report_date: string
  report_time: string | null
  route_identifier: string | null
  route_label: string | null
  location: string | null
  incident_code: string | null
  description: string | null
  mapping_status: string
  delay_minutes: number | null
  gap_minutes: number | null
  bound: string | null
  quality_flags: string[]
}
export type RecordPage = {
  context: Context
  records: SourceRecord[]
  total_records: number
  page: number
  page_size: number
  total_pages: number
  sort: string
}
export type RouteCatalog = {
  context: Context
  routes: {
    identifier: string
    labels: string[]
    reported_records: number
    first_date: string
    last_date: string
  }[]
  unassigned_route_records: number
}
export type Attempt = {
  id: string
  status: string
  started_at: string
  finished_at: string | null
  snapshot_id: string | null
  issue: string | null
  message: string | null
}
export type DataHealth = {
  resources: {
    resource_id: string
    kind: 'codes' | 'delays'
    latest_attempt: Attempt | null
    last_successful_attempt: Attempt | null
    active_snapshot: SourceSnapshot | null
    coverage: Coverage
    quality: Quality | null
  }[]
  attribution: string
  licence_url: string
  independent_project: string
}

export class ApiError extends Error {
  constructor(
    message: string,
    public code: string,
    public status: number,
  ) {
    super(message)
  }
}

export async function api<T>(
  path: string,
  params?: URLSearchParams,
  signal?: AbortSignal,
): Promise<T> {
  const response = await fetch(`/api/v1/${path}${params?.size ? `?${params}` : ''}`, { signal })
  if (!response.ok) {
    const result = await response.json().catch(() => null)
    throw new ApiError(
      result?.error?.message ?? 'The records could not be loaded. Please try again.',
      result?.error?.code ?? 'request_failed',
      response.status,
    )
  }
  return response.json() as Promise<T>
}

export const count = (value: number) => new Intl.NumberFormat('en-CA').format(value)
export function calendarDate(value: string, short = false) {
  return new Intl.DateTimeFormat('en-CA', {
    month: short ? 'short' : 'long',
    day: 'numeric',
    ...(short ? {} : { year: 'numeric' }),
    timeZone: 'UTC',
  }).format(new Date(`${value}T12:00:00Z`))
}
export function instant(value: string | null | undefined) {
  return value
    ? new Intl.DateTimeFormat('en-CA', {
        dateStyle: 'medium',
        timeStyle: 'short',
        timeZone: 'America/Toronto',
      }).format(new Date(value))
    : 'Not available'
}
