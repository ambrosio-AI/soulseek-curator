from __future__ import annotations

import re
from pathlib import PureWindowsPath

from .models import Candidate, CuratorConfig, QualityProfile, TrackRequest


WORD_RE = re.compile(r"[a-z0-9]+")


def normalize_text(value: str) -> str:
    value = value.lower()
    value = value.replace("&", " and ")
    value = re.sub(r"\([^)]*\)|\[[^\]]*\]", " ", value)
    return " ".join(WORD_RE.findall(value))


def words(value: str) -> set[str]:
    return set(normalize_text(value).split())


def infer_quality(file: dict, profiles: dict[str, QualityProfile]) -> str:
    extension = str(file.get("extension") or PureWindowsPath(file.get("filename", "")).suffix).lower()
    extension = extension.lstrip(".")
    bitrate = file.get("bitRate") or file.get("bitrate")
    for name, profile in profiles.items():
        if extension not in profile.extensions:
            continue
        if profile.min_bitrate and (not bitrate or int(bitrate) < profile.min_bitrate):
            continue
        size = int(file.get("size") or 0)
        if profile.min_size_mb and size < profile.min_size_mb * 1024 * 1024:
            continue
        if profile.max_size_mb and size > profile.max_size_mb * 1024 * 1024:
            continue
        return name
    return extension or "unknown"


def score_candidate(
    track: TrackRequest,
    response: dict,
    file: dict,
    config: CuratorConfig,
    quality_name: str,
) -> Candidate:
    filename = str(file.get("filename", ""))
    filename_words = words(filename)
    artist_words = words(track.artist)
    title_words = words(track.title or track.raw)
    reject_hits = [term for term in config.reject_terms if term.lower() in filename.lower()]
    score = 0
    reasons: list[str] = []

    if title_words:
        overlap = len(title_words & filename_words) / max(len(title_words), 1)
        points = int(overlap * 38)
        score += points
        reasons.append(f"title +{points}")
    if artist_words:
        overlap = len(artist_words & filename_words) / max(len(artist_words), 1)
        points = int(overlap * 30)
        score += points
        reasons.append(f"artist +{points}")

    quality = infer_quality(file, config.quality_profiles)
    if quality == quality_name:
        score += 18
        reasons.append("quality +18")

    bitrate = file.get("bitRate") or file.get("bitrate")
    if bitrate and int(bitrate) >= 300:
        score += 6
        reasons.append("bitrate +6")

    if response.get("hasFreeUploadSlot"):
        score += 4
        reasons.append("slot +4")
    if int(response.get("uploadSpeed") or 0) >= 100:
        score += 4
        reasons.append("speed +4")
    if int(response.get("queueLength") or 0) <= 25:
        score += 3
        reasons.append("queue +3")

    if reject_hits:
        penalty = min(35, 12 * len(reject_hits))
        score -= penalty
        reasons.append(f"reject_terms -{penalty}")

    score = max(0, min(100, score))
    return Candidate(
        username=str(response.get("username", "")),
        filename=filename,
        size=int(file.get("size") or 0),
        extension=str(file.get("extension") or PureWindowsPath(filename).suffix).lower().lstrip("."),
        bitrate=int(bitrate) if bitrate else None,
        length=file.get("length"),
        queue_length=response.get("queueLength"),
        upload_speed=response.get("uploadSpeed"),
        has_free_slot=bool(response.get("hasFreeUploadSlot")),
        quality=quality,
        score=score,
        reasons=reasons,
    )


def choose_best(
    track: TrackRequest,
    responses: list[dict],
    config: CuratorConfig,
    quality_name: str,
) -> list[Candidate]:
    candidates: list[Candidate] = []
    profile = config.quality_profiles.get(quality_name)
    if not profile:
        return []
    for response in responses:
        for file in response.get("files", []) or []:
            quality = infer_quality(file, config.quality_profiles)
            if quality != quality_name:
                continue
            candidate = score_candidate(track, response, file, config, quality_name)
            candidates.append(candidate)
    return sorted(candidates, key=lambda item: item.score, reverse=True)

