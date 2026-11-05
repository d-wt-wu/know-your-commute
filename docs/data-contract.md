# Source contract, version 1

Verified 5 November 2026 by opening the official resources, not by assuming the proposed schema. Contract/parser versions are stored with every successful snapshot. A changed interpretation must increment a version and deliberately reprocess the source.

## Evidence and scope

- [Official dataset](https://open.toronto.ca/dataset/ttc-bus-delay-data/), dataset ID `e271cdae-8788-4980-96ce-6a5c95bc6618`.
- CSV resource `b5725365-9252-4bfe-b6f4-cda7ddf74341`, resource metadata last modified `2026-10-26T12:32:23.781000` (publisher string has no timezone).
- README resource `71bb1283-7388-4d23-aa4e-0f393a80abce`, last modified in 2022; its terminology predates this CSV schema.
- Lookup resource `874ae66c-9f6f-443f-91e0-1d37d416e0d8`, last modified in April 2025.
- Exact URLs, SHA-256 hashes, byte counts and UTC retrieval timestamps: [source-manifest.json](source-manifest.json). Full observed profile and the README's cells: [source-profile.json](source-profile.json).

The current resource URLs have lowercase hyphenated filenames, rather than the older human-readable bookmarks in the plan. The registry fixes resource IDs; downloads resolve their current URLs from official CKAN metadata. A missing ID requires inspection, not guessing a replacement.

The CSV is UTF-8, without a required BOM; the reader also accepts a UTF-8 BOM. Header order is recorded, and name-based mapping permits a reordered header. Duplicate/empty headers or a missing expected column block the entire import. Extra named columns are retained in raw payloads and listed on the snapshot.

## Exact observed schema

```text
_id,Date,Line,Time,Day,Station,Code,Min Delay,Min Gap,Bound,Vehicle
```

All source values remain strings in `raw_records.payload`. Downloaded originals retain their exact bytes and hashes in ignored `data/`.

| CSV field | Observed format / older README counterpart | Typed meaning and treatment |
| --- | --- | --- |
| `_id` | Sequential-looking strings, 1–107349 in these bytes; absent from README | Retain as `source_id`. No publisher guarantee of a stable business incident ID; never use it to deduplicate or reconcile versions. |
| `Date` | `YYYY-MM-DDT00:00:00`; README calls this Report Date | Date attached to the reported record. Strictly validate the observed midnight form and a real calendar date on/after 2025-01-01. Store SQL `date`. Invalid dates quarantine the row. |
| `Line` | `102 MARKHAM ROAD`, branch identifiers, shuttle/free-text labels, blank; README Route | Keep the full trimmed label and all original whitespace in raw. Derive an identifier only from a full match of 1–4 ASCII digits, optional ASCII letter, then optional whitespace/label. Preserve the identifier as text, including leading zeroes/case. `102D` stays separate from `102`. Unparsed/blank labels remain accepted with null identifier and a flag. This is a conservative parsing rule, not an official route-name catalogue. |
| `Time` | `HH:MM`, 00:00–23:59 observed; README has AM/PM examples | SQL `time without time zone`. Invalid/missing times become null with flags. Never combine with Date and pretend it is UTC. |
| `Day` | English weekday | Preserve original. Compare against calendar Date and flag disagreement; calendar Date drives date filters. Do not repair the source. |
| `Station` | Location text; README Location | Reported location text, not a geographic coordinate or necessarily a station. Blank is usable but flagged. |
| `Code` | Uppercase category codes; README Incident | Exact trimmed code joined to the pinned official lookup. Preserve unknown values, return unmapped status; never drop them or invent a cause. |
| `Min Delay` | Nonnegative integer strings, 0–999 observed | Recorded minutes of delay to the following bus's schedule, following the README definition. Missing/invalid becomes SQL null with a flag; original remains raw. Zero stays numeric zero with a separate flag because no documented missing-value code was supplied. |
| `Min Gap` | Nonnegative integer strings, 0–997 observed | Distinct schedule-related gap field. The README describes total scheduled time relative to the bus ahead of the following bus. It does not justify treating this as observed trip duration, adding it to delay, or subtracting it to infer an undocumented headway. Same numeric validation as delay. |
| `Bound` | N/S/E/W, blank, several other values; README Direction | Keep trimmed text. README documents B/b/BW for both ways and NB/SB/EB/WB; these and N/S/E/W are accepted as recognized. Other values are retained and flagged. |
| `Vehicle` | Identifier strings; 0 occurs | Preserve text, including 0 and any leading zeroes. Flag blank/0; no claim that 0 is a documented missing sentinel. |

Integer parsing accepts digits after trimming, within PostgreSQL signed integer range. Negatives, decimals, nonnumbers and overflow become null with a field-specific flag. There is no invented outlier cutoff.

## Meaning of a row and unresolved semantics

Call each accepted source row a **reported delay record**. The README describes incident-related entries but does not establish event uniqueness, reporting completeness, stable IDs across refreshes, or whether two similar rows refer to one event. Raw source row position identifies an ingested row within a snapshot; it is not an incident ID.

The README does not specify timezone, daylight-saving disambiguation or an overnight service-day rule. Date/Time remain separate source values. No wall-time-to-UTC conversion, derived chronological instant, service-day adjustment or time-based heatmap is implemented in this slice. Import timestamps alone are UTC-aware instants. Weekday disagreement is a warning, not proof that either source field is wrong.

Zeros and extreme durations may reflect operational recording conventions that the supplied README does not explain. Retain and disclose them. A nonnegative numeric value is usable for a *recorded-value* statistic, not independent confirmation that an actual delay was zero or that every minute was measured accurately.

## Lookup contract

Exact columns: `_id,CODE,DESCRIPTION`. All 46 entries are retained, together with their original strings. Missing codes/descriptions, malformed widths or duplicate codes fail a lookup import because an ambiguous mapping would alter interpretation. Unknown extra columns are preserved/reported.

The file is valid UTF-8 but several descriptions already contain mojibake, including C1 control characters around a dash. Preserve the published value and flag `description_encoding_suspect`; do not automatically decode it a second time. Of 75 codes in the delay CSV, 35 are absent from this lookup (6,925 records). This is a source-quality limitation, not a reason to remove rows.

The lookup can change independently. A delay snapshot stores the exact lookup snapshot ID used for validation/reporting. An import with unchanged delay bytes and a different lookup version is deliberately reprocessed. Until then, old reports retain the older meaning.

## Acceptance, reconciliation and failures

1. A usable dated row is accepted even if route, category, duration, time or direction is unknown. Warnings are queryable JSON arrays. A row with an unusable/out-of-scope Date or wrong cell count is quarantined with raw values and reasons. Wrong-width payloads use a wrapper containing the complete `__cells__` array and the available named `__fields__`, so no source extra column can collide with internal bookkeeping.
2. Empty physical lines outside quoted fields are explicitly counted and excluded from raw row totals. A delimiter-only row is a record, not a blank line. Logical CSV row numbers begin at 2 after the header; physical start/end line numbers also survive, including multiline fields.
3. Valid CSV headers with no records, or no accepted dated records, cannot replace usable data. Broken CSV quoting blocks the snapshot because reliable row boundaries cannot be recovered.
4. Every successful snapshot reconciles `raw = accepted + rejected`, checked again against inserted PostgreSQL rows. Warnings count accepted records; one record may have several flags, so flag counts do not add up to unique flagged records.
5. Fingerprints exclude `_id` when looking for repeated payloads within one file. Every matching row is kept and flagged. No uniqueness constraint on source ID or payload removes records.
6. Same content + resource + parser/contract + lookup reuses the successful snapshot. Each attempt still gets an audit entry. A revision is a complete replacement for this cumulative resource, never an append. A byte-for-byte reversion can reactivate the earlier snapshot.
7. Per-resource session advisory locks exclude competing importers. Snapshot rows, raw/typed/rejected rows, active-pointer update and success audit commit together. Any exception rolls back that transaction. Audit failures commit separately; the previous active pointer survives.
8. A process death can leave an audit row `running`; the next successful lock holder marks abandoned attempts `interrupted`. No partially committed snapshot is promoted. This recovery protocol requires PostgreSQL integration verification before Phase 1 is accepted.

## Verified source profile

These are Python validation results for the archived bytes, not database-load or performance claims:

| Observation | Count |
| --- | ---: |
| CSV records / accepted by contract / rejected | 107,349 / 107,349 / 0 |
| Observed dates | 2025-01-01 through 2026-09-30 (638 distinct) |
| Records with one or more quality flags | 46,723 |
| Blank route labels / unparsed nonblank labels | 1,314 / 462 |
| Unmapped-code records | 6,925 |
| Weekday/date disagreements | 130 |
| Repeated payload extra rows / all rows in repeated groups | 300 / 599 |
| Reported zero delay / reported zero gap | 13,787 / 14,036 |

Observed date bounds do not establish complete incident reporting or known exposure. The project imports only this cumulative resource; older overlapping sources have no precedence rule yet and must not be added to reports.

## Attribution

Contains information licensed under the [Open Government Licence – Toronto](https://open.toronto.ca/open-data-licence/). Source: City of Toronto / TTC. Independent project by Wentao Wu; no official endorsement.
