# Website and iPhone release preparation

Owner: Wentao Wu. Provider information checked **5 November 2026**. This is a
reviewable deployment configuration. The [source repository](https://github.com/d-wt-wu/know-your-commute) is public and its [container/build checks](https://github.com/d-wt-wu/know-your-commute/actions/runs/42126800606) passed. No public app service exists yet.

## First release

Publish the responsive web app at one HTTPS address. The same app can be added to
an iPhone Home Screen and opened in a separate window. The repository includes a
web app manifest, 192/512-pixel PNG icons, a 180-pixel Apple touch icon, standalone
display metadata and installation guidance under About. The records still require
an internet connection. There is no offline dataset or background/live-arrival
service. No service worker caches API responses.

[Apple's iPhone guide](https://support.apple.com/en-lamr/guide/iphone/iphea86e5236/ios)
documents Safari → Share → Add to Home Screen (Open as Web App if shown). Actual
installation on a physical iPhone remains a release check after an HTTPS URL
exists; a desktop mobile viewport is not proof of iPhone installation.

A native SwiftUI or React Native client could reuse the existing read-only API
later. App Store distribution is a separate decision. Apple's ordinary developer
membership is currently [US$99 per year, with regional pricing](https://developer.apple.com/programs/enroll/).
[Review guideline 4.2](https://developer.apple.com/app-store/review/guidelines/#minimum-functionality)
expects useful functionality beyond a repackaged website. No membership, native
project, TestFlight upload or App Store approval is claimed.

## Candidate host and cost limits

| Component | Proposed setting | Verified limits and consequence |
| --- | --- | --- |
| Web/API | One Render Docker web service, Free, Virginia | 750 free instance hours per workspace/month. Idle after 15 minutes; waking takes about a minute. Files disappear across restarts/redeploys. Bandwidth/build limits also apply. |
| Database | Separate Neon Free PostgreSQL 17 project, AWS US East 1 (N. Virginia), matching the existing project | $0, no card required, 100 CU-hours/project/month and 1 GB/project. Autosuspends after five idle minutes. Check the console's actual quota and region before creation. |
| Address | Host-provided HTTPS address | No domain purchase needed. No project hostname is invented in this repository. |

Sources: [Render Free limits](https://render.com/docs/free), [Neon pricing](https://neon.com/pricing).
Render's free database expires after 30 days; it is not the persistent database
candidate. Without a payment method, Render documents suspension when certain
allowances are exhausted; adding a card can permit supplementary charges. Do not
add a card or upgrade a plan as part of this preparation. A free account may still
require verification; stop for the owner's decision if payment is required.

The current local database is roughly 79 MB, but immutable cumulative snapshots
will grow. A 1 GB allowance is an initial fit, not an indefinite capacity promise.
Inspect storage before enabling scheduled refreshes. Old snapshots are not silently
deleted. A retained-data policy or higher quota is a future deliberate decision.

## Package and credential boundary

`Dockerfile` builds the frontend with Node 22, installs locked Python dependencies
and a noneditable wheel, then runs the API/static server as a non-root user. Node,
the source CSVs, local database, test fixtures, `.env` and build tools are excluded
from the final image. Base images track the Python 3.13/Node 22 Bookworm lines;
dependency lockfiles do not pin the base OS digest.

`render.yaml` declares a free web service, external secret `DATABASE_URL`, manual
deploys and a process health check. It does not create a Render database. The
process-only health check avoids a frequent platform probe keeping Neon compute
awake. `/api/v1/ready` separately verifies a database connection; Data health
shows whether an import actually exists.

Use two independently authenticated credentials:

- **API login:** dedicated unprivileged role, explicit SELECT on five reporting
  tables, no raw/rejected access, no schema creation or record writes. Set only
  this TLS connection URL on the public web service.
- **Owner/import login:** private migration/import connection, stored locally or
  as the GitHub production environment secret `IMPORT_DATABASE_URL`. Never pass
  it to the frontend, the web service or public workflow artifacts.

The database owner's connection can grant reads to a host-created API login with
`python scripts/grant_api_reads.py --role commute_api`. The helper refuses an
administrative, schema-owning or already write-capable role. The existing database
tests verify every API projection with a SELECT-only role and prove writes, raw
reads and schema creation fail. Revisit explicit grants after schema changes.

Host-generated URLs beginning `postgresql://` are normalized to the installed
psycopg driver. Preserve host-provided TLS/channel-binding parameters. The API pool
is bounded to three persistent plus two temporary connections per process, with a
10-second connection timeout and five-second analytical statement timeout.

## Deliberate release sequence

1. Publish the reviewed repository and require the real GitHub checks to pass.
   CI runs PostgreSQL tests, browser tests, builds the image and starts it against
   the isolated synthetic fixture. A prepared YAML file is not a successful run.
2. With the owner's account/plan choice, create a Neon Free PostgreSQL 17 project
   and a dedicated unprivileged API login in the provider console. Confirm the
   region, quota and absence of a payment commitment. Keep credentials private.
3. From the checkout, apply `alembic upgrade head` using the owner connection,
   run one deliberate official import and grant the dedicated API role reads.
   Verify the source version/counts in Data health; they may differ from the
   original local source if the City published a correction.
4. Connect Render to this repository and review `render.yaml`. Confirm **Free**,
   external Neon storage, manual deploys and the API-only TLS URL. Do not expose a
   local database or copy the local example password into the host.
5. Deploy and verify the actual HTTPS URL: root, About/Data health direct links,
   readiness, real route/date totals, snapshot-pinned records, missing API JSON
   404s and Home Screen PNG/manifest paths. Use `scripts/check_deployment.py` with
   the verified expected route-102 January count; do not assume 65 for a changed
   source. Test a physical iPhone's installation and browser history.
6. Take a private durable backup before risky schema/release changes. Configure
   the production refresh secret, run the manual workflow, inspect the active
   source/last-success statuses, then set `COMMUTE_REFRESH_ENABLED=true` only when
   storage and source checks are satisfactory.

There is no automatic migration or import on app startup or visitor requests.
Keep the existing portfolio separate until a verified public app/repository link
exists and a portfolio update is requested.

The owner-selected Neon project was verified in `aws-us-east-1` on 5 November 2026. The prepared Render region was updated from Ohio to Virginia to match that existing database; the database was not moved or recreated. See `neon-setup.md` for actual migration/import/browser evidence.
