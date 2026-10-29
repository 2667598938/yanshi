"""Completed learning sessions; ongoing timers live in owner-scoped leases."""

import math
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Literal
from ..time import utcnow

MIN_START_MS = 1767225600000  # 2026-01-01 UTC, explicitly chosen product boundary.
MAX_SEC = 10800
CN = timezone(timedelta(hours=8))


class CompletedSession(BaseModel):
    model_config = ConfigDict(extra="allow")
    startedAt: int
    endedAt: int
    pauseAccum: int = Field(default=0, ge=0)
    maxPauseMs: int = Field(default=0, ge=0)
    mode: Literal["timer", "stopwatch"]
    status: Literal["done", "quit"]
    plannedMin: int = Field(default=0, ge=0, le=180, strict=True)

    @field_validator("startedAt", "endedAt", "pauseAccum", "maxPauseMs", mode="before")
    @classmethod
    def numeric(cls, value):
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
        ):
            raise ValueError("finite numeric value required")
        return int(value)


def normalize_session(record):
    value = CompletedSession.model_validate(record)
    if value.startedAt < MIN_START_MS or value.endedAt < value.startedAt:
        raise ValueError("invalid session interval")
    now = int(utcnow().replace(tzinfo=timezone.utc).timestamp() * 1000)
    if (
        value.endedAt > now + 300000
        or value.pauseAccum > value.endedAt - value.startedAt
    ):
        raise ValueError("invalid future interval or pause")
    if value.mode == "timer" and value.plannedMin < 1:
        raise ValueError("countdown requires a plan")
    raw = (value.endedAt - value.startedAt - value.pauseAccum) // 1000
    status = value.status
    reason = record.get("end_reason", "")
    if value.maxPauseMs >= 1800000 or reason == "pause_timeout":
        status, reason = "quit", "pause_timeout"
    elif reason in {"timeout", "abandoned"}:
        status = "quit"
    elif value.mode == "stopwatch" and raw >= MAX_SEC:
        status, reason = "quit", "timeout"
    if value.mode == "timer" and status == "done":
        raw = min(raw, value.plannedMin * 60)
    if raw > MAX_SEC:
        status, reason = "quit", "timeout"
    seconds = min(raw, MAX_SEC)
    effective_end = value.endedAt
    wall_seconds = (value.endedAt - value.startedAt - value.pauseAccum) // 1000
    if seconds < wall_seconds and (status == "done" or reason == "timeout"):
        effective_end = value.startedAt + value.pauseAccum + seconds * 1000
    clean = dict(record)
    for key in ("conflict_flag", "conflict_duration_sec", "validation_issue"):
        clean.pop(key, None)
    clean.update(
        startedAt=value.startedAt,
        endedAt=effective_end,
        pauseAccum=value.pauseAccum,
        maxPauseMs=value.maxPauseMs,
        plannedMin=value.plannedMin,
        mode=value.mode,
        status=status,
        actualSec=seconds,
        date=datetime.fromtimestamp(value.startedAt / 1000, CN).date().isoformat(),
        end_reason="completed"
        if status == "done"
        else (
            reason
            if reason in {"timeout", "pause_timeout", "abandoned"}
            else "abandoned"
        ),
    )
    return clean
