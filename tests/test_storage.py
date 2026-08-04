from curator.models import ImportJob
from curator.storage import Store, job_from_dict


def test_job_from_dict_defaults_active_search_fields_for_old_payloads():
    job = job_from_dict(
        {
            "id": "job-1",
            "name": "old.csv",
            "created_at": "2026-08-04T10:00:00+00:00",
            "mode": "dry-run",
            "quality": "flac",
            "fallback_order": ["flac"],
            "target_root": "",
            "tracks": [],
            "results": [],
            "status": "completed",
        }
    )

    assert job.active_search_id == ""
    assert job.active_query == ""


def test_delete_job_removes_database_row_and_reports(tmp_path):
    store = Store(tmp_path)
    job = ImportJob.create(
        name="done.csv",
        tracks=[],
        mode="dry-run",
        quality="flac",
        fallback_order=["flac"],
        target_root="",
    )
    job.status = "completed"
    store.save_job(job)
    report_dir = store.reports_dir / job.id
    report_dir.mkdir(parents=True)
    (report_dir / "report.md").write_text("# Done", encoding="utf-8")

    store.delete_job(job.id)

    assert store.list_jobs() == []
    assert not report_dir.exists()
