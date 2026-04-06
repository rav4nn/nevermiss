from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.deps import CurrentUser
from app.schemas.scan import ScanJobResponse, ScanStartRequest, ScanStartResponse
from app.services.scan_queue import enqueue_scan, get_latest_scan

router = APIRouter(prefix="/api/scan", tags=["scan"])


@router.post("/start", response_model=ScanStartResponse, status_code=status.HTTP_202_ACCEPTED)
async def start_scan(
    payload: ScanStartRequest,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ScanStartResponse:
    job = await enqueue_scan(db, current_user, payload)
    return ScanStartResponse(job_id=job.id, status=job.status)


@router.get("/status", response_model=ScanJobResponse)
async def get_scan_status(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ScanJobResponse:
    job = await get_latest_scan(db, current_user)
    return ScanJobResponse.model_validate(job)
