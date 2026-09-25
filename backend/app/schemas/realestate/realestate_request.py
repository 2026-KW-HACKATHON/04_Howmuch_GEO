from pydantic import BaseModel, Field
from typing import List, Optional

#Zone 요청 스키마
class ZoneRequest(BaseModel):
    pnus: List[str]

#Owner 요청 스키마
class OwnerRequestDTO(BaseModel):
    desired_unit: str = Field(..., description="선택 평형 (예: '84')")
    official_price: float = Field(..., description="공시가격(만원)")

#Contribution 요청 스키마
class ContributionRequest(BaseModel):
    name: Optional[str] = "사용자 지정 구역"
    site_area_m2: float
    member_count: int
    sliders: dict = Field(..., description="프론트엔드 슬라이더 조정값 딕셔너리")
    owner: OwnerRequestDTO