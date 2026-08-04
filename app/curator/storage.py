from __future__ import annotations

import json
import shutil
import sqlite3
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .models import ImportJob, TrackRequest, TrackResult


class Store:
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.db_path = data_dir / "curator.sqlite"
        self.imports_dir = data_dir / "imports"
        self.reports_dir = data_dir / "reports"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.imports_dir.mkdir(parents=True, exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self.init()

    def connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.db_path)
        con.row_factory = sqlite3.Row
        return con

    def init(self) -> None:
        with self.connect() as con:
            con.execute(
                """
                create table if not exists jobs (
                  id text primary key,
                  name text not null,
                  created_at text not null,
                  status text not null,
                  payload text not null
                )
                """
            )

    def save_job(self, job: ImportJob) -> None:
        payload = job_to_dict(job)
        with self.connect() as con:
            con.execute(
                """
                insert into jobs(id, name, created_at, status, payload)
                values(?, ?, ?, ?, ?)
                on conflict(id) do update set
                  name=excluded.name,
                  status=excluded.status,
                  payload=excluded.payload
                """,
                (job.id, job.name, job.created_at, job.status, json.dumps(payload)),
            )

    def list_jobs(self) -> list[dict[str, Any]]:
        with self.connect() as con:
            rows = con.execute(
                "select id, name, created_at, status, payload from jobs order by created_at desc"
            ).fetchall()
        jobs = []
        for row in rows:
            payload = json.loads(row["payload"])
            jobs.append(
                {
                    "id": row["id"],
                    "name": row["name"],
                    "created_at": row["created_at"],
                    "status": row["status"],
                    "track_count": len(payload.get("tracks", [])),
                    "result_count": len(payload.get("results", [])),
                }
            )
        return jobs

    def get_job(self, job_id: str) -> ImportJob:
        with self.connect() as con:
            row = con.execute("select payload from jobs where id=?", (job_id,)).fetchone()
        if not row:
            raise KeyError(job_id)
        return job_from_dict(json.loads(row["payload"]))

    def delete_job(self, job_id: str) -> None:
        with self.connect() as con:
            result = con.execute("delete from jobs where id=?", (job_id,))
        if result.rowcount == 0:
            raise KeyError(job_id)
        shutil.rmtree(self.reports_dir / job_id, ignore_errors=True)


def job_to_dict(job: ImportJob) -> dict[str, Any]:
    return asdict(job)


def job_from_dict(payload: dict[str, Any]) -> ImportJob:
    tracks = [TrackRequest(**item) for item in payload.get("tracks", [])]
    results = []
    for item in payload.get("results", []):
        track = TrackRequest(**item["track"])
        selected = item.get("selected")
        candidates = item.get("candidates", [])
        from .models import Candidate

        results.append(
            TrackResult(
                track=track,
                status=item["status"],
                selected=Candidate(**selected) if selected else None,
                candidates=[Candidate(**candidate) for candidate in candidates],
                quality_attempted=item.get("quality_attempted", ""),
                message=item.get("message", ""),
                queued=bool(item.get("queued")),
                quality_counts=dict(item.get("quality_counts", {})),
            )
        )
    return ImportJob(
        id=payload["id"],
        name=payload["name"],
        created_at=payload["created_at"],
        mode=payload["mode"],
        quality=payload["quality"],
        fallback_order=list(payload.get("fallback_order", [])),
        target_root=payload["target_root"],
        deep_lossless_search=bool(payload.get("deep_lossless_search", False)),
        tracks=tracks,
        results=results,
        status=payload.get("status", "created"),
        active_search_id=payload.get("active_search_id", ""),
        active_query=payload.get("active_query", ""),
    )
