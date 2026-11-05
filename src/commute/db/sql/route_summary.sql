-- One row per ingested CSV record, including identical-looking payloads.
SELECT count(*) AS reported_records,
       count(delay_minutes) AS valid_delay_samples,
       count(*) FILTER (WHERE delay_minutes = 0) AS zero_delay_samples,
       percentile_cont(0.5) WITHIN GROUP (ORDER BY delay_minutes)
           FILTER (WHERE delay_minutes IS NOT NULL) AS median_recorded_delay_minutes,
       avg(delay_minutes) AS mean_recorded_delay_minutes,
       count(gap_minutes) AS valid_gap_samples,
       count(*) FILTER (WHERE jsonb_array_length(quality_flags) > 0) AS flagged_records,
       min(report_date) AS first_matching_date,
       max(report_date) AS last_matching_date
FROM delay_records
WHERE snapshot_id = :snapshot_id
  AND (CAST(:route AS text) IS NULL OR route_identifier = :route)
  AND report_date >= CAST(:start AS date)
  AND report_date <= CAST(:end AS date)
