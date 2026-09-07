from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.schemas.objects import IngestionResult
from app.security import limiter, require_api_key
from app.services.ingestion import ingest_catalog

router = APIRouter(tags=["ingestion"])


@router.post("/ingestion/refresh", response_model=IngestionResult)
@limiter.limit("6/minute")
def refresh_ingestion(request: Request, api_key: str = Depends(require_api_key),
                       db: Session = Depends(get_db)):
    result = ingest_catalog(db)
    return IngestionResult(**result)
