from pydantic import BaseModel, Field
from typing import List, Optional

#Zone 요청 스키마
class ZoneRequest(BaseModel):
    pnus: List[str]
    target_ym: Optional[str] = Field(None, description="공사비 예측 기준 시점 'YYYY-MM' (착공 예상 연월). 없으면 현재 연월")
    household_count: Optional[int] = Field(None, description="구역 세대수. 조합원 수 슬라이더 범위를 만드는 데 사용")

#Owner 요청 스키마
class OwnerRequestDTO(BaseModel):
    desired_unit: str = Field(..., description="선택 평형 (예: '84')")
    official_price: float = Field(..., description="공시가격(만원)")

#Contribution 요청 스키마
class ContributionRequest(BaseModel):
    name: Optional[str] = "사용자 지정 구역"
    site_area_m2: float
    member_count: int
    far_base: float = Field(..., description="조례 기준 용적률(%). ZoneSummary.far_min 을 그대로 넘긴다 (슬라이더 아님)")
    sliders: dict = Field(..., description="프론트엔드 슬라이더 조정값 딕셔너리")
    owner: OwnerRequestDTO