from pydantic import BaseModel, Field
from typing import List, Optional

#필지 정보 스키마
#  지적도(WFS) 응답에 개별공시지가(jiga)와 폴리곤이 들어 있어서, 프론트가 그대로 넘겨준다
#  토지특성·개별공시지가 데이터 API 권한이 없어도 이 값으로 계산할 수 있다
class ParcelHintDTO(BaseModel):
    pnu: str
    area_m2: Optional[float] = Field(None, description="필지 면적(㎡). 폴리곤에서 계산한 값")
    land_price_per_m2: Optional[float] = Field(None, description="개별공시지가(원/㎡)")


#Zone 요청 스키마
class ZoneRequest(BaseModel):
    pnus: List[str]
    parcels: Optional[List[ParcelHintDTO]] = Field(None, description="선택 필지의 면적·공시지가. 없으면 V-World 데이터 API로 조회한다")
    target_ym: Optional[str] = Field(None, description="공사비 예측 기준 시점 'YYYY-MM' (착공 예상 연월). 없으면 현재 연월")
    household_count: Optional[int] = Field(None, description="구역 세대수. 조합원 수 슬라이더 범위를 만드는 데 사용")
    zoning: Optional[str] = Field(
        None,
        description="사용자가 고른 용도지역. 주면 선택 필지 전체에 이 값을 적용해 용적률 범위를 만든다. "
                    "없으면 필지별 조회값을 그대로 쓴다",
    )

#Owner 요청 스키마
class OwnerRequestDTO(BaseModel):
    desired_unit: str = Field(..., description="선택 평형 (예: '84')")
    official_price: Optional[float] = Field(None, description="공시가격(만원). 없으면 선택 구역 공시지가를 조합원 수로 나눈 1인분을 쓴다")

#Contribution 요청 스키마
class ContributionRequest(BaseModel):
    name: Optional[str] = "사용자 지정 구역"
    site_area_m2: float
    member_count: int
    far_base: float = Field(..., description="조례 기준 용적률(%). ZoneSummary.far_min 을 그대로 넘긴다 (슬라이더 아님)")
    household_count: Optional[int] = Field(None, description="구역 세대수. 조합원 수 슬라이더 범위를 다시 계산하는 데 쓴다. 없으면 member_count 를 기준으로 한다")
    land_value_total: Optional[float] = Field(None, description="선택 구역 공시지가 총액(만원). ZoneSummary.land_value_total 을 그대로 넘긴다")
    sliders: dict = Field(..., description="프론트엔드 슬라이더 조정값 딕셔너리")
    owner: OwnerRequestDTO