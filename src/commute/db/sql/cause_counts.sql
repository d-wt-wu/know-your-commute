SELECT d.incident_code,
       c.description,
       CASE WHEN c.code IS NULL THEN 'unmapped' ELSE 'mapped' END AS mapping_status,
       count(*) AS reported_records
FROM delay_records AS d
LEFT JOIN incident_codes AS c
  ON c.snapshot_id = :lookup_snapshot_id AND c.code = d.incident_code
WHERE d.snapshot_id = :snapshot_id
  AND (CAST(:route AS text) IS NULL OR d.route_identifier = :route)
  AND d.report_date >= CAST(:start AS date)
  AND d.report_date <= CAST(:end AS date)
GROUP BY d.incident_code, c.code, c.description
ORDER BY reported_records DESC, d.incident_code NULLS LAST
