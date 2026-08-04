from curator.storage import job_from_dict


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
