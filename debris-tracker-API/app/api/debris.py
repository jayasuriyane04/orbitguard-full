from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import load_catalog
from app.db.base import get_db
from app.db.models import ConjunctionEvent as ConjunctionEventRow
from app.db.models import RemovalPriority as RemovalPriorityRow
from app.schemas.analysis import RemovalPriorityOut
from app.security import limiter, require_api_key
from app.services.removal_priority import compute_removal_priorities

router = APIRouter(tags=["debris"])


@router.get("/debris/priorities", response_model=list[RemovalPriorityOut])
@limiter.limit("30/minute")
def get_removal_priorities(request: Request, api_key: str = Depends(require_api_key),
                            db: Session = Depends(get_db)):
    catalog = load_catalog(db)
    events = list(db.execute(select(ConjunctionEventRow)).scalars().all())
    results = compute_removal_priorities(catalog, events)

    # cache the latest computation for audit/history
    for r in results:
        row = db.execute(
            select(RemovalPriorityRow).where(RemovalPriorityRow.norad_id == r.norad_id)
        ).scalar_one_or_none()
        if row:
            row.removal_priority_score = r.removal_priority_score
            row.conjunction_count = r.conjunction_count
            row.average_severity_score = r.average_severity_score
            row.explanation = r.explanation
        else:
            db.add(RemovalPriorityRow(
                norad_id=r.norad_id, object_name=r.object_name,
                removal_priority_score=r.removal_priority_score,
                conjunction_count=r.conjunction_count,
                average_severity_score=r.average_severity_score,
                explanation=r.explanation,
            ))
    db.commit()

    return [RemovalPriorityOut(
        norad_id=r.norad_id, object_name=r.object_name,
        removal_priority_score=r.removal_priority_score,
        conjunction_count=r.conjunction_count,
        average_severity_score=r.average_severity_score,
        explanation=r.explanation,
    ) for r in results]
