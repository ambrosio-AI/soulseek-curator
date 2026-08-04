# AGENTS.md - Soulseek Curator

This repository contains a local web application that controls a slskd instance for lawful
list imports, match scoring, optional queueing, and reporting.

## Core Rules

- Do not add features whose main purpose is unauthorized copyright infringement.
- Keep automatic queueing guarded by configuration.
- Keep dry-run and report generation first-class.
- Preserve `Re-run fresh search` as a new dry-run, not an in-place mutation of old
  results. Old jobs are evidence and should remain inspectable until deleted.
- Keep `quality_counts` diagnostic only. Selection should still flow through quality
  profiles, fallback order, and confidence thresholds.
- Do not commit secrets, private import lists, generated reports, or downloaded media.
- Treat download destinations as slskd-relative paths. slskd owns the real filesystem/NAS
  root; Curator should only send safe subfolders to slskd.
- Prefer small, auditable Python modules over clever abstractions.
- Use the real slskd API routes documented in code:
  - `POST /api/v0/searches`
  - `GET /api/v0/searches/{id}/responses`
  - `POST /api/v0/transfers/downloads/batches`

## Architecture

- Backend: FastAPI.
- UI: server-rendered Jinja templates and CSS.
- State: SQLite under `CURATOR_DATA_DIR`.
- Config: YAML at `CURATOR_CONFIG`.
- slskd API key: `SLSKD_API_KEY` environment variable.
- Docker: `docker-compose.yml` can run both Curator and slskd.
- Deep lossless search: a per-job flag that may add `query flac` and `query wav`
  searches before MP3 fallback. Keep it cancellable and avoid unbounded query expansion.

## Useful Commands

```bash
pip install -e ".[dev]"
pytest
CURATOR_CONFIG=config/local.yaml CURATOR_DATA_DIR=data uvicorn curator.main:app --reload --app-dir app
docker compose up -d --build
```

## Test Expectations

Before pushing meaningful changes:

```bash
pytest
```

If UI routes change, run the app locally and inspect:

```text
http://localhost:8088
```

## Data Boundaries

Generated runtime data lives under `data/` and is ignored by git. Private local config may
live in `config/local.yaml` and is ignored. Public examples belong in `config.example.yaml`
or docs.
