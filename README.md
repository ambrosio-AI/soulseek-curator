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
- Configurable quality profiles: FLAC, WAV, MP3 320, MP3 V0, MP3 fallback by default.
- Configurable fallback chain per import.
- Category-to-folder mapping.
- Match scoring with confidence and ambiguous thresholds.
- Dry-run mode.
- Running imports can be cancelled from the job page.
- Dashboard separates active jobs from finished jobs and refreshes while work is active.
- Completed, cancelled, and failed jobs can be deleted from the dashboard or job page.
- Interrupted running jobs are resumed on service startup from the last saved result.
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
90s dance,Corona,The Rhythm of the Night,flac,wav,BBQ/01_90s_dance
rock,System of a Down,Chop Suey!,flac,mp3_320,BBQ/03_rock
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

Running jobs show a `Cancel job` button. Cancelling marks the Curator job as cancelled,
stops the active slskd search when one is known, and prevents any further tracks from
being searched or queued. It does not remove already queued downloads from slskd.

Finished jobs show a `Delete` button. Deleting removes the job record and generated
reports from Curator only; it does not remove anything already queued or downloaded by
slskd.

If the Curator service restarts while an import is running, the job remains visible on the
dashboard and resumes from the last saved track result on startup.

## Download Destinations

slskd owns the real download location. If slskd is configured to download into a NAS
folder, Soulseek Curator does not need to mount that NAS itself. Curator only sends a
destination subfolder to slskd.

Use `Destination folder inside slskd downloads` when starting an import to choose a
subfolder under slskd's download root, for example:

```text
BBQ/verano-2026
```

If a track has category `rock`, and no more specific mapping is configured, Curator queues
it to:

```text
BBQ/verano-2026/rock
```

`slskd download root` in Settings is a reference path used only when list files contain
absolute paths such as `/downloads/BBQ/rock`. Curator converts those to slskd-relative
destinations like `BBQ/rock` before queueing. For normal use, prefer relative folders.

Category destination folders map imported categories to subfolders:

```text
90s dance=BBQ/01_90s_dance
rock=BBQ/03_rock
```

With a per-import destination prefix, shorter mappings also work:

```text
90s dance=01_90s_dance
rock=03_rock
```

Then an import prefix of `BBQ/verano-2026` produces
`BBQ/verano-2026/01_90s_dance` and `BBQ/verano-2026/03_rock`.

## slskd API

Soulseek Curator uses the slskd API:

- `POST /api/v0/searches`
- `GET /api/v0/searches/{id}/responses`
- `POST /api/v0/transfers/downloads/batches`

Set an API key in `.env`:

```bash
SLSKD_API_KEY=replace-with-your-slskd-api-key
```

If your slskd instance uses web login instead of API keys, set:

```bash
SLSKD_USERNAME=your-slskd-web-user
SLSKD_PASSWORD=your-slskd-web-password
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

When slskd already has a NAS download folder configured, set `slskd_url` to that existing
instance and leave folder selection to Curator's relative destination fields.

If Docker builds are blocked by the host/LXC runtime, use
[`docs/SYSTEMD_DEPLOY.md`](docs/SYSTEMD_DEPLOY.md).

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
