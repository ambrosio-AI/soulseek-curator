# Soulseek Curator

Soulseek Curator is a local web application for controlled, reviewable imports into
[slskd](https://slskd.com/). It reads track lists, searches through your own slskd
instance, scores candidate files by quality and match confidence, optionally queues
approved matches, and writes reports for found, ambiguous, fallback, and not-found items.

This project is intended for lawful use: your own library, freely licensed music, public
domain material, promos, purchases, and content you have permission to obtain or manage.
It is not designed as a piracy automation tool.

## Features

- Local web UI for imports, settings, jobs, and reports.
- CSV, TXT, Markdown, and JSON list imports.
- Configurable quality profiles: FLAC, MP3 320, MP3 V0, MP3 fallback by default.
- Configurable fallback chain per import.
- Category-to-folder mapping.
- Match scoring with confidence and ambiguous thresholds.
- Dry-run mode.
- Optional slskd queue mode, disabled by default.
- Reports: `report.md`, `found.csv`, `not-found.csv`, `fallback-used.csv`, `ambiguous.csv`.
- Docker Compose deployment with a bundled slskd service.

## Quick Start

```bash
cp .env.example .env
cp config.example.yaml config/curator.yaml
docker compose up -d --build
```

Open:

```text
http://localhost:8088
```

If running on a LAN server, replace `localhost` with the server IP.

## Import Formats

TXT:

```text
Corona - The Rhythm of the Night | 90s dance
System of a Down - Chop Suey! | rock
```

CSV:

```csv
category,artist,title,preferred_quality,fallback_quality,target_folder
90s dance,Corona,The Rhythm of the Night,flac,mp3_320,/downloads/01_90s_dance
rock,System of a Down,Chop Suey!,flac,mp3_320,/downloads/03_rock
```

JSON:

```json
[
  {
    "category": "90s dance",
    "artist": "Corona",
    "title": "The Rhythm of the Night",
    "preferred_quality": "flac"
  }
]
```

Markdown lists are also supported:

```markdown
- Corona - The Rhythm of the Night
- System of a Down - Chop Suey!
```

## Operating Modes

Dry-run mode searches and scores results without queueing anything.

Queue mode sends selected matches to slskd using:

```text
POST /api/v0/transfers/downloads/batches
```

Queue mode only works when `automatic_queue_enabled` is enabled in settings.

## slskd API

Soulseek Curator uses the slskd API:

- `POST /api/v0/searches`
- `GET /api/v0/searches/{id}/responses`
- `POST /api/v0/transfers/downloads/batches`

Set your API key in `.env`:

```bash
SLSKD_API_KEY=replace-with-your-slskd-api-key
```

Secrets should not be committed.

## Deployment Next To slskd

The provided compose file runs both services:

```yaml
services:
  curator:
    ports:
      - "8088:8088"
    volumes:
      - ./config:/config
      - ./data:/data
      - /mnt/music:/downloads

  slskd:
    ports:
      - "5030:5030"
      - "50300:50300"
    volumes:
      - ./slskd:/app
      - /mnt/music:/downloads
```

On a server where slskd already exists, remove the bundled `slskd` service and set:

```yaml
slskd_url: http://existing-slskd-host:5030
```

## Reports

Each job writes reports under:

```text
data/reports/<job-id>/
```

Files:

- `report.md`: human summary.
- `found.csv`: selected or queued matches.
- `not-found.csv`: tracks with no acceptable result.
- `fallback-used.csv`: tracks found using a lower fallback quality.
- `ambiguous.csv`: tracks needing manual review.

## Development

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
CURATOR_CONFIG=config/local.yaml CURATOR_DATA_DIR=data uvicorn curator.main:app --reload --app-dir app
pytest
```

For local development without slskd, set:

```yaml
slskd_url: mock://slskd
```

## Safety Notes

- Keep the UI on your LAN unless you add proper authentication and TLS.
- Keep `automatic_queue_enabled` off until scoring has been validated with dry-runs.
- Review ambiguous results.
- Never commit `.env`, API keys, private lists, generated reports, or downloaded files.

