from __future__ import annotations

import csv
import io
import json
import re
from pathlib import Path

from .models import TrackRequest

KNOWN_COLUMNS = {
    "artist": {"artist", "artista", "author"},
    "title": {"title", "tema", "track", "song", "cancion", "canción"},
    "album": {"album", "álbum"},
    "category": {"category", "categoria", "categoría", "style", "estilo", "folder"},
    "preferred_quality": {"preferred_quality", "quality", "calidad"},
    "fallback_quality": {"fallback_quality", "fallback"},
    "target_folder": {"target_folder", "download_folder", "carpeta", "path"},
}


def parse_track_list(filename: str, content: bytes) -> list[TrackRequest]:
    suffix = Path(filename).suffix.lower()
    text = content.decode("utf-8-sig", errors="replace")
    if suffix == ".json":
        return parse_json(text)
    if suffix == ".csv":
        return parse_csv(text)
    if suffix in {".md", ".markdown"}:
        return parse_markdown(text)
    return parse_lines(text)


def parse_json(text: str) -> list[TrackRequest]:
    payload = json.loads(text)
    items = payload.get("tracks", payload) if isinstance(payload, dict) else payload
    tracks: list[TrackRequest] = []
    if not isinstance(items, list):
        return tracks
    for item in items:
        if isinstance(item, str):
            tracks.extend(parse_lines(item))
            continue
        if not isinstance(item, dict):
            continue
        raw = item.get("raw") or " - ".join(
            v for v in [item.get("artist"), item.get("title")] if v
        )
        if raw:
            tracks.append(
                TrackRequest(
                    artist=str(item.get("artist", "")).strip(),
                    title=str(item.get("title", "")).strip(),
                    album=str(item.get("album", "")).strip(),
                    category=str(item.get("category", "Unsorted")).strip() or "Unsorted",
                    preferred_quality=str(item.get("preferred_quality", "")).strip(),
                    fallback_quality=str(item.get("fallback_quality", "")).strip(),
                    target_folder=str(item.get("target_folder", "")).strip(),
                    raw=str(raw).strip(),
                )
            )
    return tracks


def parse_csv(text: str) -> list[TrackRequest]:
    sample = text[:2048]
    dialect = csv.Sniffer().sniff(sample, delimiters=",;	") if sample.strip() else csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    fields = {field: normalize_header(field) for field in (reader.fieldnames or [])}
    mapped = {field: map_header(norm) for field, norm in fields.items()}
    tracks: list[TrackRequest] = []
    for row in reader:
        data = {target: row.get(source, "").strip() for source, target in mapped.items() if target}
        raw = " - ".join(v for v in [data.get("artist"), data.get("title")] if v)
        if not raw:
            raw = " ".join(str(v).strip() for v in row.values() if v).strip()
        if raw:
            tracks.append(
                TrackRequest(
                    artist=data.get("artist", ""),
                    title=data.get("title", ""),
                    album=data.get("album", ""),
                    category=data.get("category", "") or "Unsorted",
                    preferred_quality=data.get("preferred_quality", ""),
                    fallback_quality=data.get("fallback_quality", ""),
                    target_folder=data.get("target_folder", ""),
                    raw=raw,
                )
            )
    return tracks


def parse_markdown(text: str) -> list[TrackRequest]:
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        stripped = re.sub(r"^[-*+]\s+", "", stripped)
        stripped = re.sub(r"^\d+[.)]\s+", "", stripped)
        stripped = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", stripped)
        if stripped:
            lines.append(stripped)
    return parse_lines("\n".join(lines))


def parse_lines(text: str) -> list[TrackRequest]:
    tracks: list[TrackRequest] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        line = re.sub(r"\s+", " ", line)
        category = "Unsorted"
        if "|" in line:
            parts = [p.strip() for p in line.split("|")]
            line = parts[0]
            if len(parts) > 1 and parts[1]:
                category = parts[1]
        artist, title = split_artist_title(line)
        tracks.append(TrackRequest(artist=artist, title=title, category=category, raw=line))
    return tracks


def split_artist_title(value: str) -> tuple[str, str]:
    for sep in [" - ", " – ", " — ", ":", " by "]:
        if sep in value:
            left, right = value.split(sep, 1)
            return left.strip(), right.strip()
    return "", value.strip()


def normalize_header(value: str) -> str:
    value = value.lower().strip()
    value = value.replace("á", "a").replace("é", "e").replace("í", "i")
    value = value.replace("ó", "o").replace("ú", "u")
    return re.sub(r"[^a-z0-9]+", "_", value).strip("_")


def map_header(value: str) -> str | None:
    for target, candidates in KNOWN_COLUMNS.items():
        normalized_candidates = {normalize_header(c) for c in candidates}
        if value in normalized_candidates:
            return target
    return None
