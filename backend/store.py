from __future__ import annotations

from .models.job import Job, JobStatus

_jobs: dict[str, Job] = {}


def create_job() -> Job:
    job = Job()
    _jobs[job.id] = job
    return job


def get_job(job_id: str) -> Job | None:
    return _jobs.get(job_id)


def update_job(job_id: str, **kwargs: object) -> None:
    job = _jobs.get(job_id)
    if job is None:
        return
    for k, v in kwargs.items():
        setattr(job, k, v)
