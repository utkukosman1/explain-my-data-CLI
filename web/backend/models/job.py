from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class JobStatus(str, Enum):
    pending = "pending"
    running = "running"
    done = "done"
    failed = "failed"


@dataclass
class Job:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: JobStatus = JobStatus.pending
    progress: int = 0
    step: str = ""
    result: dict[str, Any] | None = None
    markdown: str | None = None
    error: str | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
