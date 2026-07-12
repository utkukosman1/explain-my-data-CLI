from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, UploadFile, File, Form, WebSocket, WebSocketDisconnect
from fastapi.responses import Response
from pydantic import BaseModel

from ..models.job import Job, JobStatus
from ..services.analysis_service import run_analyze, run_compare, run_check
from ..store import create_job, get_job, update_job

router = APIRouter()
_executor = ThreadPoolExecutor(max_workers=4)


# ---------------------------------------------------------------------------
# Pydantic response schemas
# ---------------------------------------------------------------------------

class JobCreatedResponse(BaseModel):
    job_id: str
    status: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    progress: int
    step: str
    result: dict[str, Any] | None = None
    error: str | None = None


# ---------------------------------------------------------------------------
# Analyze
# ---------------------------------------------------------------------------

@router.post("/jobs/analyze", response_model=JobCreatedResponse)
async def create_analyze_job(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    skip_correlation: bool = Form(False),
    skip_outlier: bool = Form(False),
    use_iforest: bool = Form(False),
    target: str = Form(""),
    drop_cols: str = Form(""),
    parse_dates: str = Form(""),
    sample_size: int = Form(0),
    sheet: str = Form(""),
) -> JobCreatedResponse:
    file_bytes = await file.read()
    filename = file.filename or "upload.csv"

    options: dict[str, Any] = {
        "skip_correlation": skip_correlation,
        "skip_outlier": skip_outlier,
        "use_iforest": use_iforest,
        "target": target or None,
        "drop_cols": drop_cols,
        "parse_dates": parse_dates,
        "sample_size": sample_size if sample_size > 0 else None,
        "sheet": sheet or None,
    }

    job = create_job()
    background_tasks.add_task(_run_analyze_task, job.id, file_bytes, filename, options)
    return JobCreatedResponse(job_id=job.id, status=job.status)


def _run_analyze_task(job_id: str, file_bytes: bytes, filename: str, options: dict[str, Any]) -> None:
    def progress_cb(step: str, pct: int) -> None:
        update_job(job_id, status=JobStatus.running, step=step, progress=pct)

    update_job(job_id, status=JobStatus.running, step="Starting", progress=0)
    try:
        result = run_analyze(
            job_id=job_id,
            file_bytes=file_bytes,
            filename=filename,
            options=options,
            progress_cb=progress_cb,
        )
        update_job(job_id, status=JobStatus.done, progress=100, step="Done", result=result)
    except Exception as exc:
        update_job(job_id, status=JobStatus.failed, step="Error", error=str(exc))


# ---------------------------------------------------------------------------
# Compare (drift)
# ---------------------------------------------------------------------------

@router.post("/jobs/compare", response_model=JobCreatedResponse)
async def create_compare_job(
    background_tasks: BackgroundTasks,
    reference: UploadFile = File(...),
    current: UploadFile = File(...),
    threshold: float = Form(0.2),
) -> JobCreatedResponse:
    ref_bytes = await reference.read()
    cur_bytes = await current.read()

    options = {"threshold": threshold}
    job = create_job()
    background_tasks.add_task(
        _run_compare_task,
        job.id,
        ref_bytes, reference.filename or "reference.csv",
        cur_bytes, current.filename or "current.csv",
        options,
    )
    return JobCreatedResponse(job_id=job.id, status=job.status)


def _run_compare_task(
    job_id: str,
    ref_bytes: bytes, ref_name: str,
    cur_bytes: bytes, cur_name: str,
    options: dict[str, Any],
) -> None:
    def progress_cb(step: str, pct: int) -> None:
        update_job(job_id, status=JobStatus.running, step=step, progress=pct)

    update_job(job_id, status=JobStatus.running, step="Starting", progress=0)
    try:
        result = run_compare(
            job_id=job_id,
            ref_bytes=ref_bytes, ref_name=ref_name,
            cur_bytes=cur_bytes, cur_name=cur_name,
            options=options,
            progress_cb=progress_cb,
        )
        update_job(job_id, status=JobStatus.done, progress=100, step="Done", result=result)
    except Exception as exc:
        update_job(job_id, status=JobStatus.failed, step="Error", error=str(exc))


# ---------------------------------------------------------------------------
# Quick check (synchronous, no job)
# ---------------------------------------------------------------------------

@router.post("/check")
async def quality_check(file: UploadFile = File(...)) -> dict[str, Any]:
    file_bytes = await file.read()
    filename = file.filename or "upload.csv"
    return run_check(file_bytes, filename)


# ---------------------------------------------------------------------------
# Job status polling
# ---------------------------------------------------------------------------

@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str) -> JobStatusResponse:
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobStatusResponse(
        job_id=job.id,
        status=job.status,
        progress=job.progress,
        step=job.step,
        result=job.result,
        error=job.error,
    )


# ---------------------------------------------------------------------------
# Markdown report download
# ---------------------------------------------------------------------------

@router.get("/jobs/{job_id}/report")
async def download_report(job_id: str) -> Response:
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != "done" or job.result is None:
        raise HTTPException(status_code=400, detail="Job not complete")

    markdown = job.result.get("_markdown")
    if not markdown:
        raise HTTPException(status_code=404, detail="Report not available")

    filename = job.result.get("overview", {}).get("filename", "report")
    stem = filename.rsplit(".", 1)[0] if "." in filename else filename

    return Response(
        content=markdown,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="{stem}_report.md"'},
    )


# ---------------------------------------------------------------------------
# WebSocket progress stream
# ---------------------------------------------------------------------------

@router.websocket("/ws/{job_id}")
async def websocket_job_progress(websocket: WebSocket, job_id: str) -> None:
    await websocket.accept()
    last_progress = -1
    try:
        while True:
            job = get_job(job_id)
            if job is None:
                await websocket.send_json({"error": "Job not found"})
                break

            if job.progress != last_progress or job.status in (JobStatus.done, JobStatus.failed):
                await websocket.send_json({
                    "status": job.status,
                    "progress": job.progress,
                    "step": job.step,
                    "error": job.error,
                })
                last_progress = job.progress

            if job.status in (JobStatus.done, JobStatus.failed):
                break

            await asyncio.sleep(0.4)
    except WebSocketDisconnect:
        pass
