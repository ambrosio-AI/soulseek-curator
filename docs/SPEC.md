# Soulseek Curator Specification

## Goal

Provide a local web environment for importing track lists, choosing quality preferences and
fallbacks, mapping categories to folders, searching slskd, queueing selected matches when
explicitly enabled, and generating not-found/ambiguous/found reports.

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
- `mp3_320`: `.mp3` with bitrate >= 300.
- `mp3_v0`: `.mp3` with bitrate >= 220.
- `mp3_any`: `.mp3` with bitrate >= 128.

## Result States

- `selected`: selected during dry-run.
- `queued`: selected and sent to slskd.
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
```

Queue:

```text
POST /api/v0/transfers/downloads/batches
```

Queue destination is relative to slskd's configured download directory. If an absolute
folder is supplied, Curator attempts to convert it relative to the configured Curator
download root. If that fails, it uses the final path segment to avoid unsafe traversal.

