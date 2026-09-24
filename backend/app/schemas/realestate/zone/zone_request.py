from pydantic import BaseModel
from typing import List, Optional

#ParcelInfoDTO 스키마
class ParcelInfoDTO(BaseModel):
    pnu: str
    area_m2: float
    land_price_per_m2: float
    zoning: str
    land_category: Optional[str] = None

#ZoneSummaryRequest 스키마
class ZoneSummaryRequest(BaseModel):
    parcels: List[ParcelInfoDTO]