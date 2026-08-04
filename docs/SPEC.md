# Soulseek Curator Specification

## Goal

Provide a local web environment for importing track lists, choosing quality preferences and
fallbacks, mapping categories to slskd-relative destination folders, searching slskd,
queueing selected matches when explicitly enabled, and generating not-found/ambiguous/found
reports.

## Non-Goals

- Replacing slskd.
- Exposing a public internet service.
- Automatically accepting low-confidence results.
- Bypassing copyright or access controls.
- Managing credentials in the web UI.

## Inputs

- CSV with columns such as `artist`, `title`, `album`, `category`, `preferred_quality`,
  `fallback_quality`, `target_folder`.
- TXT lines in `Artist - Title | Category` format.
- Markdown bullet or numbered lists.
- JSON list of strings or track objects.

## Quality Selection

Each track uses this order:

1. Track-specific `preferred_quality`, if present.
2. Job/import preferred quality.
3. Configured fallback order.

Default profiles:

- `flac`: `.flac`.
- `wav`: `.wav` or `.wave`.
- `mp3_320`: `.mp3` with bitrate >= 300.
- `mp3_v0`: `.mp3` with bitrate >= 220.
- `mp3_any`: `.mp3` with bitrate >= 128.

Default fallback order:

```text
flac,wav,mp3_320,mp3_v0,mp3_any
```

## Result States

- `selected`: selected during dry-run.
- `queued`: selected and sent to slskd.
- `cancel_requested`: user requested cancellation; worker should stop at the next safe point.
- `cancelled`: job was stopped before completion.
- `fallback_used`: selected using a non-primary quality.
- `ambiguous`: best candidate is below confidence but above ambiguity threshold.
- `not_found`: no acceptable candidate.
- `error`: reserved for failed processing.

## Reports

Reports are written to `data/reports/<job-id>/`:

- `report.md`
- `found.csv`
- `not-found.csv`
- `fallback-used.csv`
- `ambiguous.csv`

## slskd Integration

Search:

```text
POST /api/v0/searches
GET /api/v0/searches/{id}/responses
PUT /api/v0/searches/{id}
```

Queue:

```text
POST /api/v0/transfers/downloads/batches
```

Compatibility queue fallback:

```text
POST /api/v0/transfers/downloads/{username}
```

The fallback endpoint queues files on older slskd instances, but it does not support the
destination option. Curator should surface that limitation in the job result message
instead of failing the whole queue action.

Dry-run promotion:

- A completed dry-run may queue stored `selected` and `fallback_used` results.
- Already queued results are skipped so repeated clicks do not duplicate transfers.
- This manual queue action does not require `automatic_queue_enabled`; that setting only
  gates imports started directly in queue mode.

`PUT /api/v0/searches/{id}` is used to stop the active slskd search when cancelling a
running Curator job. Cancelling a Curator job is not the same as cancelling downloads that
were already queued in slskd.

Queue destination is relative to slskd's configured download directory. slskd owns the
real filesystem path and NAS mount. Curator does not need to see or mount that path when
slskd is remote.

Destination resolution:

1. Start with the import-level destination prefix, if any.
2. Use `target_folder` from the list when present.
3. Otherwise use the configured category destination folder.
4. Otherwise use the imported category name.
5. If an absolute path is supplied, convert it relative to `download_root`; if it is
   outside that root, keep only the final safe path segment.

Examples, assuming slskd downloads to its own NAS-backed root:

```text
import prefix: BBQ/verano-2026
category: rock
destination sent to slskd: BBQ/verano-2026/rock
```

```text
category mapping: rock=03_rock
import prefix: BBQ/verano-2026
destination sent to slskd: BBQ/verano-2026/03_rock
```

```text
target_folder: /downloads/BBQ/03_rock
download_root: /downloads
destination sent to slskd: BBQ/03_rock
```
