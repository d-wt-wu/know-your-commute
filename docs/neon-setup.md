# Verified Neon setup

Owner: Wentao Wu. Updated 5 November 2026 (Toronto).

The existing Python/FastAPI/SQLAlchemy/psycopg application now reads the hosted
Neon database. Postgres is the only declared service. The frontend/API still run
locally; `neon deploy` does not publish this FastAPI container or create a public
website URL. Render hosting and a physical iPhone install remain separate steps.

## Target and actual commands

The selected organization is `org-restless-meadow-78109744`, project
`shiny-frog-92110874`, production branch `br-rapid-mode-bcsqtc7p`. The existing
project is in **AWS US East 1 (N. Virginia)** and uses **PostgreSQL 18.6**, rather than the local PostgreSQL 17.11 server.
Its public schema was empty before the app migration. No replacement project or
database was created to work around authentication.

The requested `neon init -y --org-id ... --project-id ... --branch production
--services postgres` succeeded initially in offline mode. After CLI sign-in,
the real deploy returned:

```text
Applying to branch production (br-rapid-mode-bcsqtc7p)
No changes — branch production already matches the policy.
Utilized services: Postgres
Pulled 3 Neon variables into .env.local
  Postgres        DATABASE_URL, DATABASE_URL_UNPOOLED
  Branch          NEON_BRANCH
```

The generated `neon.ts` was retained. It declares no Auth, Functions, storage,
Gateway or Realtime service. Root dependencies `@neon/config` and `@neon/env`
support CLI configuration; they do not replace the Python database driver.

## Connection and credential choices

- Keep SQLAlchemy Core and native psycopg for this long-running Python backend.
  [Neon recommends native drivers for non-JavaScript servers](https://neon.com/docs/connect/choose-connection).
- API reads prefer `COMMUTE_API_DATABASE_URL`, a separate ordinary SQL-created
  login named `commute_api`. It has explicit SELECT on five reporting tables,
  no raw/rejected-table access, and no record-write or schema-create permissions.
  Creating an ordinary SQL role avoids the administrative privileges given to
  default Console/API-created roles. [Neon role guidance](https://neon.com/docs/manage/roles).
- Migrations/imports/backups prefer `IMPORT_DATABASE_URL`, then the generated
  `DATABASE_URL_UNPOOLED`. Imports use session advisory locks, which require a
  direct connection. Pooled writer connections are refused before starting work.
  [Pooling limitations](https://neon.com/docs/connect/connection-pooling).
- The private `.env.local` retains the three generated values and adds only the
  API-role connection. Its permissions are `0600`; values never enter the
  frontend, tracked source, evidence JSON or public artifacts. A setup rerun
  preserved the exact file hash and did not reset the role password. A repeated
  `neon deploy` also preserved all existing environment values, including the
  custom API connection.
- Runtime startup can require a read-only role and refuses an administrative or
  write-capable credential. The proposed Render service has that guard enabled.
- Client-side libpq TLS was confirmed. Neon can terminate TLS at its proxy, so
  the backend's `pg_stat_ssl` row alone does not prove the client's TLS state.

## Start and reproduce

With the configured private environment and Python environment in this checkout:

```sh
npm run build
npm start
```

`npm run build` checks `neon.ts`, TypeScript and Vite's production build. `npm start`
loads `.env.local` explicitly, selects the read-only API login and serves the app
on loopback port 8000. `npm start -- --port 8004` selects another port. The original
local-database workflow remains `npm run start:local`; no Neon env file is loaded
implicitly by that command.

For a fresh checkout, install both root and frontend dependencies with `npm ci`
and `npm --prefix web ci`, and restore Python dependencies with `uv sync --locked`.
Use Node 22.20+ for Neon skills; the application build also passed with the existing
Node 22.17.1. No global Node upgrade was performed.

`scripts/setup_neon_database.py --manifest <actual archived manifest>` applies
Alembic, verifies metadata agreement, imports the attributed lookup/delay bundle,
checks identical reruns and provisions/reuses the API login. It never truncates
production tables or resets an existing login password. If a login already exists
without a configured credential, it stops for review instead of guessing a reset.

Opt-in browser verification against this hosted source:

```sh
npm --prefix web run test:neon
```

This starts the app with the private Neon file and performs only reads. It never
seeds, truncates, migrates or modifies the production database. The ordinary
eight-case browser suite remains isolated on its synthetic local/CI database.

## Actual results

- Root `npm run build` passed: Neon config typecheck, frontend TypeScript and
  Vite's production build (`built in 111ms` for the final observed Vite stage).
- **73 Python cases passed locally, zero skipped**, including role-password
  preservation, direct-vs-pooled selection and the existing recovery cases.
- **Two real-Neon browser cases passed**, desktop and 375-pixel mobile, in 17.1s.
  They checked actual API summary/pattern reconciliation, route/date filters,
  pagination, reload/back history, data health, layout and About/install guidance.
- **107,349 official delay records** and 46 code entries imported. Identical
  resource reruns returned `no_change`; repeating the complete setup reused the
  API login and preserved private credentials.
- Exact route 102, January 2025: **65 records**, numeric n=65, one reported zero,
  median recorded delay **20 minutes**. Shortening the range to January 15
  returned **39** in the browser. These remain historical reported rows, not a
  trip delay probability or route reliability score.
- The actual `commute_api` connection used TLS and was refused record writes and
  raw-record reads. Source hashes/provenance were retained in the hosted import.

The [GitHub run](https://github.com/d-wt-wu/know-your-commute/actions/runs/42140733466) also passed on PostgreSQL 17 and 18. Each job ran 73 Python cases, eight synthetic browser cases, the root build, Docker build and a running-container check. This is separate from the two real-Neon browser checks.

Evidence: `evidence/neon-github-ci.json`, `evidence/neon-database.json`, `evidence/neon-rerun.json` and
`evidence/neon-checks.json`. Existing portfolio/paper/photo hashes remain unchanged.
The local suite has one previously known Starlette/httpx deprecation warning.

## Agent skills and MCP check

Fetched the exact requested skill:
`https://neon.com/.well-known/agent-skills/neon/SKILL.md`.
Its SHA-256 is `a92323993a4071fed1c670ccd21efb638c55bf3412a45daf4d5e08a1b92a4523`.
It matched the existing project copy byte for byte. `neon skills status` reported
all seven skills up to date; no skill copy was replaced.

The earlier requested `init` installed the user-level Neon plugin for Codex,
Claude Code/Desktop and VS Code, plus skills/OAuth MCP configuration for Copilot
CLI because that CLI was absent. The pre-existing global Codex server configuration
was retained; the Neon plugin is enabled.

The plugin directory contains an MCP definition, but the current Codex CLI
inventory did not expose a Neon server. Added only the missing project-specific
entry with:

```sh
npx neon@latest mcp --oauth --project --agent codex --project-id shiny-frog-92110874 -y
```

This created `.codex/config.toml` with server `Neon` and a project-pinned HTTPS URL.
No API key was minted or stored. Agent files (`.agents/`, `.codex/`) and `.neon`
are local/ignored; `skills-lock.json` records installable public skill versions.
Existing global configuration was not rewritten for this project entry.

The current chat/CLI inventory has not loaded that project MCP entry, so an
authenticated MCP tool call is **not** claimed. Open/reload Codex in this project
to activate its project configuration and complete OAuth on first use. The
application's separate CLI/database connection is already verified end to end.

## Failures and limits

The first browser authorization expired after the CLI's 60-second window. Running
login from Wentao's own Terminal supplied usable credentials. Installing globally
in the ordinary `/usr/local` npm location failed with `EACCES`, so the working
fallback is `npx neon@latest`; a compatible temporary Node runtime was used for
the skill installer. No `sudo` installation or broad permission change was used.

The first local integration attempt was blocked by the app's network restriction;
after local/network access was granted, all 73 checks ran and passed. No skipped
database group was counted as a pass.

The hosted database is PostgreSQL 18.6. Backup/restore now checks the server's major
and requires matching client tools. The existing local dump/restore drill is on
PostgreSQL 17; a hosted PostgreSQL 18 backup drill has not been run because only
the local 17 client tools are installed. No hosted recovery time is claimed.

The candidate Render region was aligned from Ohio to Virginia after verifying
the existing Neon project region. No database move/recreation occurred.

No new paid plan, domain, public web deployment, App Store app or portfolio edit
was created during this setup.
