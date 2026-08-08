from __future__ import annotations

import asyncio

import httpx

from .config import slskd_api_key, slskd_password, slskd_username
from .models import CuratorConfig, ImportJob, TrackResult, slskd_destination
from .reports import write_reports
from .scoring import choose_best, quality_counts
from .slskd import MockSlskdClient, SlskdClient
from .storage import Store

CANCEL_STATUSES = {"cancel_requested", "cancelled"}
QUEUEABLE_RESULT_STATUSES = {"selected", "fallback_used"}


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
        responses: list[dict] = []
        search_ids: list[str] = []
        for query in search_queries(track, qualities, job.deep_lossless_search):
            job.active_search_id = ""
            job.active_query = query
            store.save_job(job)
            search_id = await client.start_search(
                query,
                search_timeout=config.search_timeout,
                response_limit=config.response_limit,
                file_limit=config.file_limit,
                minimum_upload_speed=config.minimum_upload_speed,
                maximum_queue_length=config.maximum_queue_length,
            )
            search_ids.append(search_id)
            job.active_search_id = search_id
            job.active_query = query
            store.save_job(job)
            if await wait_for_search_or_cancel(job, config, store, client):
                job.status = "cancelled"
                job.active_search_id = ""
                job.active_query = ""
                store.save_job(job)
                write_reports(job, store.reports_dir)
                return job
            query_responses = await client.search_responses(search_id)
            for response in query_responses:
                response["_curator_search_id"] = search_id
            responses.extend(query_responses)
            job.active_search_id = ""
            job.active_query = ""
            store.save_job(job)
            if has_confident_lossless_match(track, responses, config, qualities):
                break
        if not is_cancel_requested(store, job.id):
            counts = quality_counts(responses, config)
            for quality in qualities:
                if is_cancel_requested(store, job.id):
                    break
                candidates = choose_best(track, responses, config, quality)
                for candidate in candidates:
                    if not candidate.search_id:
                        candidate.search_id = search_ids[-1] if search_ids else ""
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
                        queue_result = await client.enqueue_batch(
                            username=best.username,
                            filename=best.filename,
                            size=best.size,
                            destination=destination,
                            search_id=best.search_id,
                            external_id=job.id,
                            raw_file=best.raw_file,
                        )
                        queued = True
                        if queue_result.get("destination_supported") is False:
                            message = (
                                "queued to slskd default downloads; this slskd API does not support "
                                "per-request folders"
                            )
                        else:
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
                        quality_counts=counts,
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
                        quality_counts=counts,
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
            track_result = TrackResult(
                track=track,
                status="not_found",
                message="no valid candidate",
                quality_counts=quality_counts(responses, config),
            )
        results.append(track_result)
        job.results = results
        store.save_job(job)
    job.status = "completed"
    job.results = results
    store.save_job(job)
    write_reports(job, store.reports_dir)
    return job


async def queue_selected_results(job: ImportJob, config: CuratorConfig, store: Store) -> ImportJob:
    client = build_client(config)
    queued_count = 0
    for result in job.results:
        if result.queued or result.status == "queued":
            continue
        if result.status not in QUEUEABLE_RESULT_STATUSES or not result.selected:
            continue
        configured_folder = config.category_folders.get(result.track.category, "")
        destination = slskd_destination(
            config.download_root,
            job.target_root,
            result.track.target_folder or configured_folder,
            result.track.category,
        )
        # Candidatos a probar: el seleccionado primero, luego los alternativos (sin duplicar por filename)
        candidates = [result.selected]
        seen_filenames = {result.selected.filename}
        for candidate in result.candidates:
            if candidate.filename not in seen_filenames:
                seen_filenames.add(candidate.filename)
                candidates.append(candidate)

        queued_ok = False
        for candidate in candidates:
            if is_cancel_requested(store, job.id):
                break
            try:
                queue_result = await client.enqueue_batch(
                    username=candidate.username,
                    filename=candidate.filename,
                    size=candidate.size,
                    destination=destination,
                    search_id=candidate.search_id,
                    external_id=job.id,
                    raw_file=candidate.raw_file,
                )
            except httpx.HTTPError as exc:
                result.status = "error"
                result.message = f"slskd queue failed: {exc}"
                break
            # Esperar a que slskd procese el transfer y consultar su estado
            await asyncio.sleep(1)
            try:
                rejected = await client.is_download_rejected(candidate.filename)
            except httpx.HTTPError:
                rejected = False
            if rejected:
                result.message = f"rejected, trying next candidate"
                continue
            # Éxito: el transfer se encoló sin rechazo
            result.queued = True
            result.selected = candidate
            if queue_result.get("destination_supported") is False:
                result.message = (
                    "queued to slskd default downloads; this slskd API does not support per-request folders"
                )
            else:
                result.message = f"queued to {destination}"
            if result.status == "selected":
                result.status = "queued"
            queued_ok = True
            queued_count += 1
            break

        if not queued_ok and result.status not in ("error",):
            result.status = "error"
            result.message = "all candidates rejected"

    if queued_count:
        job.mode = "queue"
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


def search_queries(track, qualities: list[str], deep_lossless_search: bool) -> list[str]:
    base = track.query
    queries = [base]
    if deep_lossless_search and any(quality in qualities for quality in ("flac", "wav")):
        for suffix in ("flac", "wav"):
            if suffix in qualities:
                queries.append(f"{base} {suffix}")
    seen = set()
    result = []
    for query in queries:
        clean = " ".join(query.split())
        key = clean.lower()
        if clean and key not in seen:
            seen.add(key)
            result.append(clean)
    return result


def has_confident_lossless_match(
    track,
    responses: list[dict],
    config: CuratorConfig,
    qualities: list[str],
) -> bool:
    for quality in ("flac", "wav"):
        if quality not in qualities:
            continue
        candidates = choose_best(track, responses, config, quality)
        if candidates and candidates[0].score >= config.confidence_threshold:
            return True
    return False
