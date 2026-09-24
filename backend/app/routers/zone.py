from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from typing import List, Optional
from AI.engine.zone import build_zone_summary
from AI.engine.schema import ParcelInfo, ZoneSummary
from app.schemas.realestate.zone.zone_request import ZoneSummaryRequest, ParcelInfoDTO

#라우터 등록
router = APIRouter(
    prefix="/api/v1/zones",
    tags=["Zone & Parcel"]
)

#구역 요약 집계 API
@router.post(
    "/summary",
    response_model=ZoneSummary,
    summary="구역 요약 집계"
)
def api_build_zone_summary(payload: ZoneSummaryRequest):
    try:
        parcels = [ParcelInfo(**p.model_dump()) for p in payload.parcels]
        return build_zone_summary(parcels)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))