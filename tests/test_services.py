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
