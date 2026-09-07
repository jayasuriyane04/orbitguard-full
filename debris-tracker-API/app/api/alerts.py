from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.db.models import Alert as AlertRow
from app.schemas.analysis import AlertOut
from app.schemas.enums import AlertStatus
from app.security import limiter, require_api_key
from app.services.alerts import acknowledge_alert

router = APIRouter(tags=["alerts"])


@router.get("/alerts", response_model=list[AlertOut])
@limiter.limit("60/minute")
def list_alerts(
    request: Request, api_key: str = Depends(require_api_key), db: Session = Depends(get_db),
    status: Optional[AlertStatus] = Query(default=None),
    page: int = Query(default=1, ge=1), page_size: int = Query(default=50, ge=1, le=500),
):
    stmt = select(AlertRow)
    if status:
        stmt = stmt.where(AlertRow.status == status)
    stmt = stmt.order_by(AlertRow.created_at.desc())
    rows = list(db.execute(stmt).scalars().all())
    start = (page - 1) * page_size
    return rows[start:start + page_size]


@router.patch("/alerts/{alert_id}/acknowledge", response_model=AlertOut)
@limiter.limit("60/minute")
def patch_acknowledge_alert(request: Request, alert_id: int,
                             api_key: str = Depends(require_api_key), db: Session = Depends(get_db)):
    row = db.get(AlertRow, alert_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"No alert {alert_id}")
    return acknowledge_alert(db, row)
