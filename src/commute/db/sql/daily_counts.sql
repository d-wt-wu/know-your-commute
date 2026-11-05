SELECT report_date, count(*) AS reported_records
FROM delay_records
WHERE snapshot_id = :snapshot_id
  AND (CAST(:route AS text) IS NULL OR route_identifier = :route)
  AND report_date >= CAST(:start AS date)
  AND report_date <= CAST(:end AS date)
GROUP BY report_date
ORDER BY report_date
