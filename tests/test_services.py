import asyncio

from curator.models import CuratorConfig, ImportJob, TrackRequest
from curator.services import process_job
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
