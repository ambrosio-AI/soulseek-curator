from __future__ import annotations

import asyncio

from .config import slskd_api_key, slskd_password, slskd_username
from .models import CuratorConfig, ImportJob, TrackResult, slskd_destination
from .reports import write_reports
from .scoring import choose_best
from .slskd import MockSlskdClient, SlskdClient
from .storage import Store


CANCEL_STATUSES = {"cancel_requested", "cancelled"}


def build_client(config: CuratorConfig) -> SlskdClient:
    if config.slskd_url.startswith("mock://"):
        return MockSlskdClient()
    return SlskdClient(
        config.slskd_url,
        api_key=slskd_api_key(),
        username=slskd_username(),
        password=slskd_password(),
    )


async def process_job(job: ImportJob, config: CuratorConfig, store: Store, *, queue: bool) -> ImportJob:
    client = build_client(config)
    if is_cancel_requested(store, job.id):
        job.status = "cancelled"
        store.save_job(job)
        write_reports(job, store.reports_dir)
        return job
    job.status = "running"
    store.save_job(job)
    results: list[TrackResult] = list(job.results)
    for track in job.tracks[len(results) :]:
        if is_cancel_requested(store, job.id):
            job.status = "cancelled"
            job.active_search_id = ""
            job.active_query = ""
            store.save_job(job)
            write_reports(job, store.reports_dir)
            return job
        track_result: TrackResult | None = None
        preferred_quality = track.preferred_quality or job.quality or config.fallback_order[0]
        qualities = quality_chain(track, job, config)
        job.active_search_id = ""
        job.active_query = track.query
        store.save_job(job)
        search_id = await client.start_search(
            track.query,
            search_timeout=config.search_timeout,
            response_limit=config.response_limit,
            file_limit=config.file_limit,
            minimum_upload_speed=config.minimum_upload_speed,
            maximum_queue_length=config.maximum_queue_length,
        )
        job.active_search_id = search_id
        job.active_query = track.query
        store.save_job(job)
        if await wait_for_search_or_cancel(job, config, store, client):
            job.status = "cancelled"
            job.active_search_id = ""
            job.active_query = ""
            store.save_job(job)
            write_reports(job, store.reports_dir)
            return job
        responses = await client.search_responses(search_id)
        job.active_search_id = ""
        job.active_query = ""
        store.save_job(job)
        if not is_cancel_requested(store, job.id):
            for quality in qualities:
                if is_cancel_requested(store, job.id):
                    break
                candidates = choose_best(track, responses, config, quality)
                for candidate in candidates:
                    candidate.search_id = search_id
                if not candidates:
                    continue
                best = candidates[0]
                if best.score >= config.confidence_threshold:
                    status = "selected"
                    if quality != preferred_quality:
                        status = "fallback_used"
                    configured_folder = config.category_folders.get(track.category, "")
                    destination = slskd_destination(
                        config.download_root,
                        job.target_root,
                        track.target_folder or configured_folder,
                        track.category,
                    )
                    queued = False
                    message = "selected"
                    if queue:
                        if is_cancel_requested(store, job.id):
                            break
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
                    ambiguous_result = TrackResult(
                        track=track,
                        status="ambiguous",
                        selected=best,
                        candidates=candidates[:5],
                        quality_attempted=quality,
                        message="best result is below confidence threshold",
                    )
                    if not track_result or best.score > (track_result.selected.score if track_result.selected else 0):
                        track_result = ambiguous_result
        if is_cancel_requested(store, job.id):
            job.status = "cancelled"
            job.active_search_id = ""
            job.active_query = ""
            store.save_job(job)
            write_reports(job, store.reports_dir)
            return job
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


def is_cancel_requested(store: Store, job_id: str) -> bool:
    try:
        return store.get_job(job_id).status in CANCEL_STATUSES
    except KeyError:
        return False


async def wait_for_search_or_cancel(
    job: ImportJob,
    config: CuratorConfig,
    store: Store,
    client: SlskdClient,
) -> bool:
    wait_seconds = max(1, min(config.search_timeout, 20))
    for _ in range(wait_seconds):
        if is_cancel_requested(store, job.id):
            await client.stop_search(job.active_search_id)
            return True
        await asyncio.sleep(1)
    return False


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
