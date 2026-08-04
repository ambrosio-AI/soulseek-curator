from __future__ import annotations

import csv
from pathlib import Path

from .models import ImportJob


def write_reports(job: ImportJob, reports_dir: Path) -> dict[str, Path]:
    target = reports_dir / job.id
    target.mkdir(parents=True, exist_ok=True)
    paths = {
        "found": target / "found.csv",
        "not_found": target / "not-found.csv",
        "fallback": target / "fallback-used.csv",
        "ambiguous": target / "ambiguous.csv",
        "report": target / "report.md",
    }
    write_csv(paths["found"], job, {"queued", "selected", "fallback_used"})
    write_csv(paths["not_found"], job, {"not_found"})
    write_csv(paths["fallback"], job, {"fallback_used"})
    write_csv(paths["ambiguous"], job, {"ambiguous"})
    write_markdown(paths["report"], job)
    return paths


def write_csv(path: Path, job: ImportJob, statuses: set[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            [
                "status",
                "artist",
                "title",
                "category",
                "quality",
                "score",
                "username",
                "filename",
                "message",
            ]
        )
        for result in job.results:
            if result.status not in statuses:
                continue
            selected = result.selected
            writer.writerow(
                [
                    result.status,
                    result.track.artist,
                    result.track.title,
                    result.track.category,
                    result.quality_attempted,
                    selected.score if selected else "",
                    selected.username if selected else "",
                    selected.filename if selected else "",
                    result.message,
                ]
            )


def write_markdown(path: Path, job: ImportJob) -> None:
    counts: dict[str, int] = {}
    for result in job.results:
        counts[result.status] = counts.get(result.status, 0) + 1
    lines = [
        f"# {job.name}",
        "",
        f"- Job: `{job.id}`",
        f"- Status: `{job.status}`",
        f"- Mode: `{job.mode}`",
        f"- Tracks: {len(job.tracks)}",
        "",
        "## Summary",
        "",
    ]
    for status, count in sorted(counts.items()):
        lines.append(f"- {status}: {count}")
    lines += ["", "## Results", ""]
    for result in job.results:
        selected = result.selected
        line = f"- **{result.status}**: {result.track.display_name}"
        if selected:
            line += f" -> `{selected.filename}` ({selected.quality}, score {selected.score})"
        if result.message:
            line += f" - {result.message}"
        lines.append(line)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

