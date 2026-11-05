SELECT row_number, source_id, report_date, report_time, route_identifier,
       route_label, incident_code, delay_minutes, gap_minutes, quality_flags
FROM delay_records
WHERE snapshot_id = :snapshot_id
  AND (CAST(:route AS text) IS NULL OR route_identifier = :route)
  AND report_date >= CAST(:start AS date)
  AND report_date <= CAST(:end AS date)
ORDER BY report_date, report_time NULLS LAST, row_number
LIMIT 10
