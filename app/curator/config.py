from __future__ import annotations

import os
from dataclasses import asdict
from pathlib import Path
from typing import Any

import yaml

from .models import CuratorConfig, QualityProfile


DEFAULT_CONFIG_PATH = Path(os.getenv("CURATOR_CONFIG", "config/curator.yaml"))


def _quality_from_dict(name: str, payload: dict[str, Any]) -> QualityProfile:
    return QualityProfile(
        name=name,
        extensions=[str(e).lower().lstrip(".") for e in payload.get("extensions", [])],
        min_bitrate=payload.get("min_bitrate"),
        max_size_mb=payload.get("max_size_mb"),
        min_size_mb=payload.get("min_size_mb"),
    )


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> CuratorConfig:
    if not path.exists():
        config = CuratorConfig()
        save_config(config, path)
        return config

    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    profiles = raw.get("quality_profiles") or {}
    quality_profiles = {
        name: _quality_from_dict(name, payload or {}) for name, payload in profiles.items()
    }
    base = CuratorConfig()
    return CuratorConfig(
        slskd_url=raw.get("slskd_url", base.slskd_url),
        download_root=raw.get("download_root", base.download_root),
        automatic_queue_enabled=bool(
            raw.get("automatic_queue_enabled", base.automatic_queue_enabled)
        ),
        search_timeout=int(raw.get("search_timeout", base.search_timeout)),
        response_limit=int(raw.get("response_limit", base.response_limit)),
        file_limit=int(raw.get("file_limit", base.file_limit)),
        minimum_upload_speed=int(raw.get("minimum_upload_speed", base.minimum_upload_speed)),
        maximum_queue_length=int(raw.get("maximum_queue_length", base.maximum_queue_length)),
        confidence_threshold=int(raw.get("confidence_threshold", base.confidence_threshold)),
        ambiguous_threshold=int(raw.get("ambiguous_threshold", base.ambiguous_threshold)),
        fallback_order=list(raw.get("fallback_order", base.fallback_order)),
        reject_terms=list(raw.get("reject_terms", base.reject_terms)),
        category_folders=dict(raw.get("category_folders", base.category_folders)),
        quality_profiles=quality_profiles or base.quality_profiles,
    )


def save_config(config: CuratorConfig, path: Path = DEFAULT_CONFIG_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = asdict(config)
    payload["quality_profiles"] = {
        name: {
            "extensions": profile.extensions,
            "min_bitrate": profile.min_bitrate,
            "min_size_mb": profile.min_size_mb,
            "max_size_mb": profile.max_size_mb,
        }
        for name, profile in config.quality_profiles.items()
    }
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def slskd_api_key() -> str:
    return os.getenv("SLSKD_API_KEY", "").strip()

