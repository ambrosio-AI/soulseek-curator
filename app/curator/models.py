from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class QualityProfile:
    name: str
    extensions: list[str]
    min_bitrate: int | None = None
    max_size_mb: int | None = None
    min_size_mb: int | None = None


@dataclass
class CuratorConfig:
    slskd_url: str = "http://slskd:5030"
    download_root: str = "/downloads"
    automatic_queue_enabled: bool = False
    search_timeout: int = 15
    response_limit: int = 40
    file_limit: int = 2000
    minimum_upload_speed: int = 0
    maximum_queue_length: int = 1000000
    confidence_threshold: int = 72
    ambiguous_threshold: int = 58
    fallback_order: list[str] = field(
        default_factory=lambda: ["flac", "wav", "mp3_320", "mp3_v0", "mp3_any"]
    )
    reject_terms: list[str] = field(
        default_factory=lambda: [
            "karaoke",
            "cover",
            "slowed",
            "reverb",
            "nightcore",
            "tribute",
            "remake",
            "reaction",
        ]
    )
    category_folders: dict[str, str] = field(default_factory=dict)
    quality_profiles: dict[str, QualityProfile] = field(
        default_factory=lambda: {
            "flac": QualityProfile("flac", ["flac"]),
            "wav": QualityProfile("wav", ["wav", "wave"]),
            "mp3_320": QualityProfile("mp3_320", ["mp3"], min_bitrate=300),
            "mp3_v0": QualityProfile("mp3_v0", ["mp3"], min_bitrate=220),
            "mp3_any": QualityProfile("mp3_any", ["mp3"], min_bitrate=128),
        }
    )


@dataclass
class TrackRequest:
    artist: str
    title: str
    category: str = "Unsorted"
    album: str = ""
    preferred_quality: str = ""
    fallback_quality: str = ""
    target_folder: str = ""
    raw: str = ""

    @property
    def display_name(self) -> str:
        if self.artist and self.title:
            return f"{self.artist} - {self.title}"
        return self.raw or self.title or self.artist

    @property
    def query(self) -> str:
        parts = [self.artist, self.title]
        if self.album:
            parts.append(self.album)
        return " ".join(p for p in parts if p).strip() or self.raw


@dataclass
class Candidate:
    username: str
    filename: str
    size: int
    extension: str = ""
    bitrate: int | None = None
    length: int | None = None
    queue_length: int | None = None
    upload_speed: int | None = None
    has_free_slot: bool = False
    quality: str = ""
    score: int = 0
    reasons: list[str] = field(default_factory=list)
    search_id: str = ""
    raw_file: dict[str, Any] = field(default_factory=dict)


@dataclass
class TrackResult:
    track: TrackRequest
    status: str
    selected: Candidate | None = None
    candidates: list[Candidate] = field(default_factory=list)
    quality_attempted: str = ""
    message: str = ""
    queued: bool = False


@dataclass
class ImportJob:
    id: str
    name: str
    created_at: str
    mode: str
    quality: str
    fallback_order: list[str]
    target_root: str
    tracks: list[TrackRequest]
    results: list[TrackResult] = field(default_factory=list)
    status: str = "created"
    active_search_id: str = ""
    active_query: str = ""

    @classmethod
    def create(
        cls,
        name: str,
        tracks: list[TrackRequest],
        mode: str,
        quality: str,
        fallback_order: list[str],
        target_root: str,
    ) -> "ImportJob":
        return cls(
            id=str(uuid4()),
            name=name,
            created_at=utcnow(),
            mode=mode,
            quality=quality,
            fallback_order=fallback_order,
            target_root=target_root,
            tracks=tracks,
        )


def _safe_relative_path(value: str) -> str:
    parts = []
    for part in Path(value).parts:
        if part in {"", ".", "/", "\\"} or part == "..":
            continue
        parts.append(part)
    return "/".join(parts)


def slskd_destination(download_root: str, destination_prefix: str, folder: str, category: str) -> str:
    preferred = folder.strip() if folder else category.strip() or "Unsorted"
    full = Path(preferred)
    if full.is_absolute():
        try:
            preferred = str(full.relative_to(Path(download_root))).strip("/")
        except ValueError:
            preferred = full.name
    else:
        preferred = str(full).strip("/")

    preferred = _safe_relative_path(preferred) or "Unsorted"
    prefix = _safe_relative_path(destination_prefix.strip())
    if not prefix:
        return preferred
    if preferred == prefix or preferred.startswith(f"{prefix}/"):
        return preferred
    return f"{prefix}/{preferred}"


def relative_destination(root: str, folder: str, category: str) -> str:
    return slskd_destination(root, "", folder, category)


Json = dict[str, Any]
