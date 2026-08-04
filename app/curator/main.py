from __future__ import annotations

import os
import asyncio
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .config import DEFAULT_CONFIG_PATH, load_config, save_config
from .models import ImportJob
from .parser import parse_track_list
from .reports import write_reports
from .services import build_client, process_job
from .storage import Store

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("CURATOR_DATA_DIR", "data"))
TERMINAL_JOB_STATUSES = {"completed", "cancelled", "error"}

app = FastAPI(title="Soulseek Curator")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")
store = Store(DATA_DIR)


@app.on_event("startup")
async def resume_interrupted_jobs():
    config = load_config()
    for item in store.list_jobs():
        if item["status"] in TERMINAL_JOB_STATUSES:
            continue
        try:
            job = store.get_job(item["id"])
        except KeyError:
            continue
        if job.status == "cancel_requested":
            job.status = "cancelled"
            job.active_search_id = ""
            job.active_query = ""
            store.save_job(job)
            write_reports(job, store.reports_dir)
            continue
        asyncio.create_task(process_job(job, config, store, queue=job.mode == "queue"))


@app.middleware("http")
async def no_cache_dynamic_pages(request: Request, call_next):
    response = await call_next(request)
    if request.url.path == "/" or request.url.path.startswith("/jobs"):
        response.headers["Cache-Control"] = "no-store, max-age=0"
    return response


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    config = load_config()
    client = build_client(config)
    ok, status = await client.health()
    jobs = store.list_jobs()
    active_jobs = [job for job in jobs if job["status"] not in TERMINAL_JOB_STATUSES]
    finished_jobs = [job for job in jobs if job["status"] in TERMINAL_JOB_STATUSES]
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "request": request,
            "jobs": jobs,
            "active_jobs": active_jobs,
            "finished_jobs": finished_jobs,
            "config": config,
            "slskd_ok": ok,
            "slskd_status": status,
        },
    )


@app.get("/settings", response_class=HTMLResponse)
async def settings(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="settings.html",
        context={"config": load_config()},
    )


@app.post("/settings")
async def update_settings(
    slskd_url: str = Form(...),
    download_root: str = Form(...),
    automatic_queue_enabled: str | None = Form(None),
    search_timeout: int = Form(...),
    response_limit: int = Form(...),
    file_limit: int = Form(...),
    minimum_upload_speed: int = Form(...),
    maximum_queue_length: int = Form(...),
    confidence_threshold: int = Form(...),
    ambiguous_threshold: int = Form(...),
    fallback_order: str = Form(...),
    reject_terms: str = Form(...),
    category_folders: str = Form(""),
):
    config = load_config()
    config.slskd_url = slskd_url.strip()
    config.download_root = download_root.strip()
    config.automatic_queue_enabled = automatic_queue_enabled == "on"
    config.search_timeout = search_timeout
    config.response_limit = response_limit
    config.file_limit = file_limit
    config.minimum_upload_speed = minimum_upload_speed
    config.maximum_queue_length = maximum_queue_length
    config.confidence_threshold = confidence_threshold
    config.ambiguous_threshold = ambiguous_threshold
    config.fallback_order = [item.strip() for item in fallback_order.split(",") if item.strip()]
    config.reject_terms = [item.strip() for item in reject_terms.splitlines() if item.strip()]
    config.category_folders = parse_category_folders(category_folders)
    save_config(config, DEFAULT_CONFIG_PATH)
    return RedirectResponse("/settings", status_code=303)


@app.get("/imports/new", response_class=HTMLResponse)
async def new_import(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="import.html",
        context={"config": load_config()},
    )


@app.post("/imports")
async def create_import(
    background_tasks: BackgroundTasks,
    upload: UploadFile = File(...),
    mode: str = Form("dry-run"),
    quality: str = Form("flac"),
    fallback_order: str = Form("flac,wav,mp3_320,mp3_v0,mp3_any"),
    target_root: str = Form(""),
):
    content = await upload.read()
    tracks = parse_track_list(upload.filename or "import.txt", content)
    if not tracks:
        raise HTTPException(status_code=400, detail="No tracks found in upload")
    config = load_config()
    queue = mode == "queue"
    if queue and not config.automatic_queue_enabled:
        raise HTTPException(status_code=403, detail="Automatic queueing is disabled in settings")
    job = ImportJob.create(
        name=upload.filename or "import",
        tracks=tracks,
        mode=mode,
        quality=quality,
        fallback_order=[item.strip() for item in fallback_order.split(",") if item.strip()],
        target_root=target_root.strip(),
    )
    store.save_job(job)
    background_tasks.add_task(process_job, job, config, store, queue=queue)
    return RedirectResponse(f"/jobs/{job.id}", status_code=303)


@app.get("/jobs/{job_id}", response_class=HTMLResponse)
async def show_job(request: Request, job_id: str):
    try:
        job = store.get_job(job_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Job not found") from None
    return templates.TemplateResponse(request=request, name="job.html", context={"job": job})


@app.post("/jobs/{job_id}/cancel")
async def cancel_job(job_id: str):
    try:
        job = store.get_job(job_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Job not found") from None
    if job.status in TERMINAL_JOB_STATUSES:
        return RedirectResponse(f"/jobs/{job.id}", status_code=303)

    job.status = "cancel_requested"
    store.save_job(job)
    if job.active_search_id:
        client = build_client(load_config())
        try:
            await client.stop_search(job.active_search_id)
        except Exception:
            pass
    job = store.get_job(job_id)
    job.status = "cancelled"
    job.active_search_id = ""
    job.active_query = ""
    store.save_job(job)
    write_reports(job, store.reports_dir)
    return RedirectResponse(f"/jobs/{job.id}", status_code=303)


@app.post("/jobs/{job_id}/delete")
async def delete_job(job_id: str):
    try:
        job = store.get_job(job_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Job not found") from None
    if job.status not in TERMINAL_JOB_STATUSES:
        raise HTTPException(status_code=409, detail="Only completed, cancelled, or failed jobs can be deleted")
    store.delete_job(job_id)
    return RedirectResponse("/", status_code=303)


@app.post("/jobs/{job_id}/reports")
async def regenerate_reports(job_id: str):
    try:
        job = store.get_job(job_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Job not found") from None
    write_reports(job, store.reports_dir)
    return RedirectResponse(f"/jobs/{job.id}", status_code=303)


@app.get("/jobs/{job_id}/reports/{name}")
async def download_report(job_id: str, name: str):
    allowed = {
        "found.csv",
        "not-found.csv",
        "fallback-used.csv",
        "ambiguous.csv",
        "report.md",
    }
    if name not in allowed:
        raise HTTPException(status_code=404, detail="Report not found")
    path = store.reports_dir / job_id / name
    if not path.exists():
        raise HTTPException(status_code=404, detail="Report not generated yet")
    return FileResponse(path, filename=name)


def parse_category_folders(text: str) -> dict[str, str]:
    result = {}
    for line in text.splitlines():
        if not line.strip() or "=" not in line:
            continue
        category, folder = line.split("=", 1)
        result[category.strip()] = folder.strip()
    return result


def run() -> None:
    import uvicorn

    uvicorn.run(
        "curator.main:app",
        host=os.getenv("CURATOR_HOST", "0.0.0.0"),
        port=int(os.getenv("CURATOR_PORT", "8088")),
        reload=False,
    )


if __name__ == "__main__":
    run()
