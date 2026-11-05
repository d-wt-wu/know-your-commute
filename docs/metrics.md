# Report definitions

The SQL report, API and dashboard share these definitions. CLI examples return ten
source rows; the browser uses a separate bounded pagination query.

| Output | Definition |
| --- | --- |
| `reported_records` | Accepted rows in the selected active delay snapshot matching the exact derived route identifier and inclusive Date range. Identical-looking records are counted individually. Omitting route includes accepted records whose route is unknown. |
| `valid_delay_samples` | Matching records with a parsed nonnegative integer `Min Delay`. Missing/invalid values are excluded. Reported zeroes are included and separately counted. |
| `zero_delay_samples` | Valid recorded delay values exactly zero; the publisher has not documented whether some zeroes are operational placeholders. |
| `median_recorded_delay_minutes` | PostgreSQL `percentile_cont(0.5)` over valid recorded delay values. Null when no valid observations exist. It describes recorded values, not a trip's expected delay. |
| `mean_recorded_delay_minutes` | SQL average of the same valid recorded values and sample. Do not infer passenger time. |
| `valid_gap_samples` | Count of parsed nonnegative gap values. Gap is a distinct schedule-related field; it is not added to delay. |
| `flagged_records` | Matching accepted records with at least one quality flag. Snapshot-wide warning counts in `quality` describe the whole active file and can overlap. |
| Daily records | Counts for observed matching dates. Absent dates are not filled with zero without a stronger coverage contract. |
| Causes | Exact source Code, pinned lookup description if present, mapping status and matching record count. Unknown codes are retained; published encoding issues remain visible. |
| Examples | First ten matching records ordered by source Date, source Time (null last), then CSV row position. These are diagnostic examples, not full API pagination. |
| Loaded coverage | Earliest/latest accepted Date in the active file. This is independent of source modification time, download time and latest successful import attempt. |

Counts across routes cannot establish reliability rankings or delay probability without scheduled/operated service exposure. The dataset does not supply a denominator of all trips. Avoid language such as “the chance your bus is delayed”, “safest route”, “on-time rate” or “minutes passengers lost”.

For no matches, return count 0, valid sample count 0, null duration summaries, and empty observed-date/cause/example arrays. Say “No matching records in the loaded data”. A route is not proven delay-free.

An import's quality flag means a documented condition was observed. It is not a percentage score of overall truth. The source's accuracy and reporting completeness are not independently established by this project.

## First verified SQL example

The PostgreSQL report for exact identifier `102`, inclusive 2025-01-01 through 2025-01-31, returned **65 reported records**, **65 valid numeric delay values**, **one reported zero**, and a **20-minute median recorded delay**. Counts, valid-value sample size and median matched an independent calculation from the original CSV strings. Daily counts and causes each reconciled to 65. See [the captured report](evidence/route-102-2025-01.json).

This describes the recorded entries for that filter. It does not describe all route 102 trips or the probability of encountering a delay.
