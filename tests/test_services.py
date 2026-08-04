import asyncio

from curator.models import Candidate, CuratorConfig, ImportJob, TrackRequest, TrackResult
from curator.services import process_job, queue_selected_results
from curator.storage import Store


def test_process_job_respects_cancel_request_before_start(tmp_path):
    store = Store(tmp_path)
    job = ImportJob.create(
        name="cancel.csv",
        tracks=[TrackRequest(artist="Demo", title="Track")],
        mode="dry-run",
        quality="flac",
        fallback_order=["flac"],
        target_root="",
    )
    store.save_job(job)
    job.status = "cancel_requested"
    store.save_job(job)

    result = asyncio.run(
        process_job(job, CuratorConfig(slskd_url="mock://slskd"), store, queue=False)
    )

    assert result.status == "cancelled"
    assert result.results == []


def test_process_job_searches_once_per_track_for_quality_fallback(tmp_path, monkeypatch):
    class FallbackClient:
        def __init__(self):
            self.starts = 0

        async def start_search(self, query, **kwargs):
            self.starts += 1
            return "search-1"

        async def search_responses(self, search_id):
            return [
                {
                    "username": "demo",
                    "hasFreeUploadSlot": True,
                    "queueLength": 0,
                    "uploadSpeed": 512,
                    "files": [
                        {
                            "filename": "Demo - Track.mp3",
                            "extension": "mp3",
                            "bitRate": 320,
                            "size": 9000000,
                        }
                    ],
                }
            ]

        async def stop_search(self, search_id):
            return True

    client = FallbackClient()
    monkeypatch.setattr("curator.services.build_client", lambda config: client)
    store = Store(tmp_path)
    job = ImportJob.create(
        name="fallback.csv",
        tracks=[TrackRequest(artist="Demo", title="Track")],
        mode="dry-run",
        quality="flac",
        fallback_order=["flac", "wav", "mp3_320"],
        target_root="",
    )
    store.save_job(job)

    result = asyncio.run(process_job(job, CuratorConfig(search_timeout=1), store, queue=False))

    assert client.starts == 1
    assert result.status == "completed"
    assert result.results[0].status == "fallback_used"
    assert result.results[0].quality_attempted == "mp3_320"


def test_process_job_uses_later_confident_fallback_over_early_ambiguous(tmp_path, monkeypatch):
    class FallbackClient:
        async def start_search(self, query, **kwargs):
            return "search-1"

        async def search_responses(self, search_id):
            return [
                {
                    "username": "demo",
                    "hasFreeUploadSlot": True,
                    "queueLength": 0,
                    "uploadSpeed": 512,
                    "files": [
                        {
                            "filename": "Track.flac",
                            "extension": "flac",
                            "size": 32100000,
                        },
                        {
                            "filename": "Demo - Track.mp3",
                            "extension": "mp3",
                            "bitRate": 320,
                            "size": 9000000,
                        },
                    ],
                }
            ]

        async def stop_search(self, search_id):
            return True

    monkeypatch.setattr("curator.services.build_client", lambda config: FallbackClient())
    store = Store(tmp_path)
    job = ImportJob.create(
        name="fallback.csv",
        tracks=[TrackRequest(artist="Demo", title="Track")],
        mode="dry-run",
        quality="flac",
        fallback_order=["flac", "mp3_320"],
        target_root="",
    )
    store.save_job(job)

    result = asyncio.run(
        process_job(
            job,
            CuratorConfig(search_timeout=1, confidence_threshold=90, ambiguous_threshold=50),
            store,
            queue=False,
        )
    )

    assert result.status == "completed"
    assert result.results[0].status == "fallback_used"
    assert result.results[0].quality_attempted == "mp3_320"


def test_process_job_resumes_after_existing_results(tmp_path, monkeypatch):
    class ResumeClient:
        def __init__(self):
            self.queries = []

        async def start_search(self, query, **kwargs):
            self.queries.append(query)
            return f"search-{len(self.queries)}"

        async def search_responses(self, search_id):
            return []

        async def stop_search(self, search_id):
            return True

    client = ResumeClient()
    monkeypatch.setattr("curator.services.build_client", lambda config: client)
    store = Store(tmp_path)
    first = TrackRequest(artist="Done", title="Already")
    second = TrackRequest(artist="Needs", title="Search")
    job = ImportJob.create(
        name="resume.csv",
        tracks=[first, second],
        mode="dry-run",
        quality="flac",
        fallback_order=["flac"],
        target_root="",
    )
    job.status = "running"
    job.results = [TrackResult(track=first, status="not_found")]
    store.save_job(job)

    result = asyncio.run(process_job(job, CuratorConfig(search_timeout=1), store, queue=False))

    assert client.queries == ["Needs Search"]
    assert result.status == "completed"
    assert len(result.results) == 2


def test_queue_selected_results_queues_existing_dry_run_matches(tmp_path, monkeypatch):
    class QueueClient:
        def __init__(self):
            self.enqueued = []

        async def enqueue_batch(self, **kwargs):
            self.enqueued.append(kwargs)
            return {"batch": {"id": "batch-1"}, "failures": []}

    client = QueueClient()
    monkeypatch.setattr("curator.services.build_client", lambda config: client)
    store = Store(tmp_path)
    selected_track = TrackRequest(artist="Demo", title="Track", category="rock")
    queued_track = TrackRequest(artist="Already", title="Queued", category="rock")
    job = ImportJob.create(
        name="dry-run.csv",
        tracks=[selected_track, queued_track],
        mode="dry-run",
        quality="flac",
        fallback_order=["flac"],
        target_root="BBQ",
    )
    job.status = "completed"
    job.results = [
        TrackResult(
            track=selected_track,
            status="selected",
            selected=Candidate(
                username="demo",
                filename="Demo - Track.flac",
                size=1234,
                quality="flac",
                search_id="search-1",
            ),
        ),
        TrackResult(
            track=queued_track,
            status="queued",
            selected=Candidate(
                username="demo",
                filename="Already - Queued.flac",
                size=1234,
                quality="flac",
                search_id="search-2",
            ),
            queued=True,
        ),
    ]
    store.save_job(job)

    result = asyncio.run(
        queue_selected_results(
            job,
            CuratorConfig(slskd_url="mock://slskd", category_folders={"rock": "01_rock"}),
            store,
        )
    )

    assert len(client.enqueued) == 1
    assert client.enqueued[0]["destination"] == "BBQ/01_rock"
    assert client.enqueued[0]["filename"] == "Demo - Track.flac"
    assert result.mode == "queue"
    assert result.results[0].status == "queued"
    assert result.results[0].queued is True
