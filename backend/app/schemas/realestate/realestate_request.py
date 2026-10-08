from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional

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

#평형 구성 입력 스키마 (세부 설정의 "입력 평형 / 비율" 한 줄)
#  비율은 세대수 기준이다 ("59형이 전체 세대의 30%").
#  엔진 내부(UnitMix.share)는 분양 공급면적 중의 몫이라 calc 에서 환산한다
class UnitMixEntryDTO(BaseModel):
    exclusive_area_m2: float = Field(..., gt=0, le=300, description="전용면적(㎡). 평형 이름이 되는 숫자 (59·84·114)")
    household_ratio: float = Field(..., ge=0, le=100, description="세대수 비율. 비로만 쓰므로 백분율(30)·소수(0.3) 모두 받는다")


#필지별 종전자산 원자료 (/zone 의 prior_asset.parcels 를 그대로 돌려보낸다)
#  왜 돌려보내나 : 평가 기준시점(사업시행인가)은 사업기간 슬라이더에 따라 달라지고,
#  그 시점에서는 건물이 더 낡고(잔존율 ↓) 재조달원가는 오른다(공사비 ↑).
#  상쇄 정도가 구조마다 달라 구역 평균 한 배수로 밀 수 없어 필지 단위로 다시 계산한다.
#  이미 조회해 둔 값이라 API 추가 호출은 없다
#공공기여 기부면적 비율 (세부 설정). 합이 100 이 아니어도 비율대로 맞춘다. 현금은 맞춘 뒤 50% 까지 (넘으면 서버가 자른다)
class ContributionMixDTO(BaseModel):
    land: float = Field(100.0, ge=0, le=100, description="토지 기부 비율(%, 기부면적 기준)")
    public_rental: float = Field(0.0, ge=0, le=100, description="공공임대 건축물 기부채납 비율(%, 대지지분 + 설치비 환산)")
    cash: float = Field(0.0, ge=0, le=100, description="현금 비율(%, 부지가액으로 환산). 기부면적의 절반까지 (시행령 제14조②)")


class ParcelValuationDTO(BaseModel):
    pnu: str
    land_area_m2: float = Field(..., gt=0, description="토지면적(㎡)")
    land_price_per_m2: float = Field(..., ge=0, description="개별공시지가(원/㎡)")
    structure: str = Field("", description="건축물대장 strctCdNm")
    building_area_m2: float = Field(0.0, ge=0, description="연면적(㎡). 0 이면 나대지")
    elapsed_years: float = Field(0.0, ge=0, description="조회 시점 기준 경과연수")
    household_count: int = Field(1, ge=1, description="세대·가구 수")
    has_building: bool = Field(False, description="건물 존재 여부")
    land_category: str = Field("", description="지목. 도로·구거는 법정 비율(1/3)로 감액한다")
    cost_index: float = Field(1.0, gt=0, le=2.0, description="재조달원가 상대지수 (구조·용도, 아파트 = 1.0)")
    owner_type: str = Field("", description="토지 소유구분. 국·공유지면 종전자산·조합원 수에서 뺀다")
    housing_kind: str = Field("", description="주택 공시가격 종류 : 공동(공동주택가격) · 단독(개별주택가격) · 빈칸")
    housing_price: float = Field(0.0, ge=0, description="주택 공시가격 합계(만원). 있으면 종전자산 = 공시가격 ÷ 현실화율")
    housing_units: int = Field(0, ge=0, description="공동주택가격 호수")
    housing_area_prices: Optional[List[List[float]]] = Field(None, description="[전용면적, 호당 공시가격(만원), 호수] — 공동주택만")


#Owner 요청 스키마
class OwnerRequestDTO(BaseModel):
    desired_unit: str = Field(..., description="선택 평형 (예: '84')")
    official_price: Optional[float] = Field(None, description="공시가격(만원). 없으면 선택 구역 공시지가를 조합원 수로 나눈 1인분을 쓴다")
    #내 필지를 지정하면 그 필지의 토지분+건물분으로 개인화된다.
    #  지정하지 않으면 구역 종전자산의 1인분(ρ=1) → 구역 평균 조합원의 분담금이 나온다
    pnu: Optional[str] = Field(None, min_length=19, max_length=19, description="내 필지 PNU. 지정하면 그 필지 기준으로 개인화된다")
    exclusive_area_m2: Optional[float] = Field(None, gt=0, le=1000, description="집합건물에서 내 전유면적(㎡). 없으면 세대수로 균등 분할한다")

#Contribution 요청 스키마
class ContributionRequest(BaseModel):
    name: Optional[str] = "사용자 지정 구역"
    credit_token: str = Field(..., min_length=32, max_length=64, description="구역 분석에서 발급한 크레딧 차감 토큰")
    site_area_m2: float
    member_count: int
    far_base: float = Field(..., description="정비계획 상한용적률(%). /zone 응답의 far_base 를 그대로 넘긴다 (슬라이더 아님)")
    #산식상 최대는 1종 → 준주거 상한 400% 의 약 51% (토지로만 낼 때)
    public_contribution_ratio: float = Field(
        0.0,
        ge=0,
        le=0.6,
        description="토지 공공기여율(원래 대지 대비). /zone 응답 sliders.floor_area_ratio.contributions 중 "
                    "고른 용적률 노드의 값을 넘긴다 (종상향 최소 + 상한용적률 산식). 이만큼 건축 대지가 줄어든다",
    )
    #공공기여 (세부 설정의 「적용」). 노드의 토지 기부 비율에서 필요한 기여량을 되돌려 기부면적 비율대로 채운다
    contribution_mix: Optional[ContributionMixDTO] = Field(
        None, description="토지 · 공공임대 건축물 · 현금 기부면적 비율(%). 없으면 contribution_method 프리셋, 그것도 없으면 토지 100%",
    )
    contribution_method: Optional[str] = Field(
        None,
        description="버튼 프리셋 이름 (contribution_mix 가 없을 때만) : land(토지 100) · land_cash(토지 50 + 현금 50) · land_rental(토지 50 + 공공임대 50)",
    )
    min_contribution_ratio: float = Field(
        0.0,
        ge=0,
        le=0.6,
        description="종상향 최소 공공기여(순부담, 원래 대지 대비). /zone 응답 sliders.floor_area_ratio.min_contribution 을 넘긴다. "
                    "토지가 아닌 방식에서 순부담 하한을 맞추는 데 쓴다",
    )
    household_count: Optional[int] = Field(None, description="구역 세대수. 조합원 수 슬라이더 범위를 다시 계산하는 데 쓴다. 없으면 member_count 를 기준으로 한다")
    land_value_total: Optional[float] = Field(None, description="선택 구역 공시지가 총액(만원). ZoneSummary.land_value_total 을 그대로 넘긴다")
    sliders: dict = Field(..., description="프론트엔드 슬라이더 조정값 딕셔너리")
    unit_mix: Optional[List[UnitMixEntryDTO]] = Field(
        None,
        max_length=4,
        description="사용자가 세부 설정에서 정한 평형 구성(최대 4개). 없으면 기본 UNIT_MIX(59·84·114 실측)를 쓴다",
    )
    parcel_valuations: Optional[List[ParcelValuationDTO]] = Field(
        None,
        description="/zone 의 prior_asset.parcels 를 그대로 돌려보낸다. 주면 종전자산을 "
                    "평가시점 기준으로 필지 단위 재집계한다. 없으면 land_value_total × 보정률 폴백",
    )
    rental_exclusive_area_m2: Optional[float] = Field(
        None,
        gt=0,
        le=200,
        description="임대 1세대 전용면적(㎡). 임대 세대수 비율은 용적률 완화분에서 자동으로 정해지므로 입력받지 않는다",
    )
    owner: OwnerRequestDTO
    #사업 유형 : /zone 의 project_type 을 그대로 (아파트 단지만 고르면 재건축)
    project_type: str = Field("재개발", description="재개발 · 재건축. 재건축이면 의무 임대 0, 종전자산 = 공동주택가격 ÷ 현실화율")
    reconstruction: Optional[Dict[str, Any]] = Field(
        None, description="/zone 의 reconstruction 을 그대로 돌려보낸다 (재건축만 — 세대수·공동주택가격 합계·전용면적별 호당 값)"
    )