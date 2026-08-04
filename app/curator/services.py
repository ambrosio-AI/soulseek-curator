from __future__ import annotations

from .config import slskd_api_key
from .models import CuratorConfig, ImportJob, TrackResult, relative_destination
from .reports import write_reports
from .scoring import choose_best
from .slskd import MockSlskdClient, SlskdClient
from .storage import Store


def build_client(config: CuratorConfig) -> SlskdClient:
    if config.slskd_url.startswith("mock://"):
        return MockSlskdClient()
    return SlskdClient(config.slskd_url, slskd_api_key())


async def process_job(job: ImportJob, config: CuratorConfig, store: Store, *, queue: bool) -> ImportJob:
    client = build_client(config)
    job.status = "running"
    store.save_job(job)
    results: list[TrackResult] = []
    for track in job.tracks:
        qualities = quality_chain(track, job, config)
        track_result: TrackResult | None = None
        for quality in qualities:
            search_id, responses = await client.search(
                track.query,
                search_timeout=config.search_timeout,
                response_limit=config.response_limit,
                file_limit=config.file_limit,
                minimum_upload_speed=config.minimum_upload_speed,
                maximum_queue_length=config.maximum_queue_length,
            )
            candidates = choose_best(track, responses, config, quality)
            for candidate in candidates:
                candidate.search_id = search_id
            if not candidates:
                continue
            best = candidates[0]
            if best.score >= config.confidence_threshold:
                status = "selected"
                if quality != job.quality:
                    status = "fallback_used"
                configured_folder = config.category_folders.get(track.category, "")
                destination = relative_destination(
                    job.target_root,
                    track.target_folder or configured_folder,
                    track.category,
                )
                queued = False
                message = "selected"
                if queue:
                    await client.enqueue_batch(
                        username=best.username,
                        filename=best.filename,
                        size=best.size,
                        destination=destination,
                        search_id=best.search_id,
                        external_id=job.id,
                    )
                    queued = True
                    message = f"queued to {destination}"
                    status = "queued" if status == "selected" else status
                track_result = TrackResult(
                    track=track,
                    status=status,
                    selected=best,
                    candidates=candidates[:5],
                    quality_attempted=quality,
                    message=message,
                    queued=queued,
                )
                break
            if best.score >= config.ambiguous_threshold:
                track_result = TrackResult(
                    track=track,
                    status="ambiguous",
                    selected=best,
                    candidates=candidates[:5],
                    quality_attempted=quality,
                    message="best result is below confidence threshold",
                )
                break
        if not track_result:
            track_result = TrackResult(track=track, status="not_found", message="no valid candidate")
        results.append(track_result)
        job.results = results
        store.save_job(job)
    job.status = "completed"
    job.results = results
    store.save_job(job)
    write_reports(job, store.reports_dir)
    return job


def quality_chain(track, job: ImportJob, config: CuratorConfig) -> list[str]:
    preferred = track.preferred_quality or job.quality or config.fallback_order[0]
    fallback = track.fallback_quality.split(",") if track.fallback_quality else job.fallback_order
    chain = [preferred.strip(), *[item.strip() for item in fallback]]
    seen = set()
    result = []
    for item in chain:
        if item and item in config.quality_profiles and item not in seen:
            seen.add(item)
            result.append(item)
    return result or config.fallback_order
