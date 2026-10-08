from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


#Parcel & Zone 정보 관련 스키마
class ParcelInfoModel(BaseModel):
    pnu: str = Field(..., description="필지 고유번호 (19자리)")
    area_m2: float = Field(..., description="면적 (㎡)")
    land_price_per_m2: float = Field(..., description="공시지가 (원/㎡)")
    zoning: str = Field(..., description="용도지역")
    land_category: str = Field(..., description="지목")

#ZoneSummary 스키마
class ZoneSummaryModel(BaseModel):
    pnus: List[str] = Field(default_factory=list, description="대상 PNU 목록")
    total_area_m2: float = Field(..., description="총 토지면적 (㎡)")
    total_land_price: float = Field(..., description="총 토지 공시지가")
    far_min: float = Field(..., description="최저 용적률 (%)")
    far_max: float = Field(..., description="최고 용적률 (%)")
    region: str = Field(..., description="지역 구분")
    warnings: List[str] = Field(default_factory=list, description="경고 메시지 목록")
    # zone 객체 내에 additional fields가 있다면 Dict[str, Any] 또는 구체적 필드로 확장 가능
    extra: Optional[Dict[str, Any]] = None


#예측 정보 스키마
class CostPredictionModel(BaseModel):
    cost_per_pyeong: float = Field(..., description="평당 예측 공사비 (원)")
    unit: str = Field(default="원/평", description="단위")
    # predict_cost_per_pyeong 결과 dataclass의 추가 필드들을 여기에 정의
    details: Optional[Dict[str, Any]] = None

#예측 정보 스키마
class SalePredictionModel(BaseModel):
    sale_price_per_m2: float = Field(..., description="㎡당 예측 분양가 (원)")
    # predict_sale_price_per_m2 결과 dataclass의 추가 필드들을 여기에 정의
    details: Optional[Dict[str, Any]] = None


#슬라이더 스키마
class SliderConfigModel(BaseModel):
    min: float = Field(..., description="슬라이더 최소값")
    max: float = Field(..., description="슬라이더 최대값")
    default: float = Field(..., description="슬라이더 기본값")
    step: Optional[float] = Field(1.0, description="증감 단위")

#슬라이더 모델 스키마
class SlidersModel(BaseModel):
    far: Optional[SliderConfigModel] = Field(None, description="용적률 슬라이더 설정")
    household_count: Optional[SliderConfigModel] = Field(None, description="세대수 슬라이더 설정")
    # build_sliders()가 반환하는 슬라이더 구조에 맞게 자유롭게 dictionary 형태도 가능
    extra_sliders: Optional[Dict[str, Any]] = None


#사업 유형 미리 판정 응답 (필지를 고르는 즉시 배지를 띄운다 — 크레딧 없음)
class ProjectTypeResponse(BaseModel):
    project_type: str = Field(..., description="재개발 · 재건축 (/zone 과 같은 규칙 — AI/engine/project_type.py)")
    project_type_reason: str = Field(..., description="판정 근거 문장 (배지 툴팁)")


#Zone API 응답 스키마
class ZoneResponse(BaseModel):
    zone: Dict[str, Any] = Field(..., description="구역 요약 정보 (asdict(zone))")
    far_base: float = Field(..., description="정비계획 상한용적률 (%). 제54조 초과용적률의 기준점 (4단 상한, 보정계수 반영)")
    target_ym: str = Field(..., description="예측 대상 년월 (YYYY-MM)")
    zoning_options: List[str] = Field(..., description="선택 가능한 용도지역 목록")
    selected_zoning: Optional[str] = Field(None, description="사용자가 선택한 용도지역")
    sliders: Dict[str, Any] = Field(..., description="슬라이더 설정 객체")
    project_type: str = Field("재개발", description="사업 유형 판정 : 아파트 단지(들)만 고르면 재건축, 아파트 외 사유 필지가 섞이면 재개발")
    project_type_reason: str = Field("", description="판정 근거 (선택한 필지 칸 옆 표시용)")
    reconstruction: Optional[Dict[str, Any]] = Field(
        None,
        description="재건축 단지 정보 (세대수·단지 대지면적·현황용적률·공동주택가격 합계·전용면적별 호당 공시가격). "
                    "/contribution 에 그대로 돌려보낸다. 재개발이면 null",
    )
    cost_prediction: Dict[str, Any] = Field(..., description="공사비 예측 데이터")
    prior_asset: Optional[Dict[str, Any]] = Field(
        None,
        description="구역 종전자산(토지분+건물분)과 실측 조합원 수. 건축물대장 전수 집계 결과",
    )
    sale_prediction: Dict[str, Any] = Field(..., description="분양가 예측 데이터")
    business_correction: Optional[Dict[str, Any]] = Field(
        None,
        description="사업성 보정계수 (서울시 평균 공시지가 ÷ 구역 '대' 필지 평균, 1.00~2.00). 허용·상한 용적률을 올린다",
    )
    upzoning: Optional[Dict[str, Any]] = Field(
        None,
        description="종상향 판정. 기준 용도지역(필지 원래 용도지역의 면적가중 평균 단계)보다 높게 고르면 "
                    "최소 공공기여율이 붙는다 (노드별 실제 비율은 sliders.floor_area_ratio.contributions)",
    )
    credits_remaining: int = Field(..., description="남은 일일 크레딧")
    credit_token: str = Field(..., description="성공한 분담금 계산에서 크레딧을 차감하기 위한 토큰")

#분양 평형 스키마
class ContributionUnitType(BaseModel):
    name: str = Field(..., description="평형 이름")
    exclusive_area_m2: float = Field(..., description="전용면적 (㎡)")
    supply_area_m2: float = Field(..., description="공급면적 (㎡)")
    count: int = Field(..., description="배분 세대수")


#사업 계산 결과 스키마
class ContributionProject(BaseModel):
    unit_types: List[ContributionUnitType] = Field(..., description="분양 평형별 세대수")
    rental_count: int = Field(..., description="임대 세대수")
    commercial_area_m2: float = Field(..., description="상가 면적 (㎡)")
    gross_floor_area_m2: float = Field(..., description="연면적 (㎡)")
    total_cost: float = Field(..., description="총 사업비")
    total_post_asset: float = Field(..., description="총 종후자산")
    total_prior_asset: float = Field(..., description="총 종전자산")
    proportional_rate: float = Field(..., description="비례율 (%)")
    warnings: List[str] = Field(default_factory=list, description="사업성 계산 경고 메시지")
    sale_supply_m2: float = Field(0.0, description="평형에 나눠 줄 수 있는 분양 공급면적 (㎡) = 주택 공급면적 − 임대 − 기부채납 공공임대")


#조합원 평형 선택 옵션 스키마
class UnitOption(BaseModel):
    name: str = Field(..., description="평형 이름")
    supply_area_m2: float = Field(..., description="공급면적 (㎡)")
    count: int = Field(..., description="배분 세대수")
    member_price: float = Field(..., description="조합원 분양가")

#평형별 분담금 스키마 ("예상 분담금" 패널에 전부 깔아 보여주는 값)
#  사용자가 평형을 고르지 않아도 분양 평형 전부의 분담금이 한 번에 내려온다.
#  임대는 조합원 분양 대상이 아니라 목록에 없다
class UnitContributionModel(BaseModel):
    name: str = Field(..., description="평형 이름 (전용면적 숫자)")
    exclusive_area_m2: float = Field(..., description="전용면적 (㎡)")
    supply_area_m2: float = Field(..., description="공급면적 (㎡)")
    count: int = Field(..., description="배분 세대수")
    member_price: float = Field(..., description="조합원 분양가 (만원)")
    contribution: float = Field(..., description="분담금 (만원). 음수면 환급")
    contribution_ratio: float = Field(..., description="분담금 ÷ 조합원 분양가")


#Member Count 스키마
class MemberCountRange(BaseModel):
    value: int = Field(..., description="현재 설정된 조합원 수")
    min: int = Field(..., description="조합원 수 슬라이더 최소값")
    max: int = Field(..., description="조합원 수 슬라이더 최대값")
    capped: bool = Field(True, description="상한선 적용 여부")

#Contribution API 응답 스키마
class ContributionResponse(BaseModel):
    prior_asset: float = Field(..., description="추정 종전자산 평가액")
    proportional_rate: float = Field(..., description="추정 비례율 (%)")
    right_value: float = Field(..., description="권리가액")
    member_price: float = Field(..., description="선택 평형 조합원 분양가")
    contribution: float = Field(..., description="추정 분담금 (음수면 환급)")
    project: ContributionProject = Field(..., description="사업 전체 계산 결과")
    unit_options: List[UnitOption] = Field(..., description="평형별 조합원 분양가 선택지")
    unit_contributions: List[UnitContributionModel] = Field(
        default_factory=list, description="분양 평형별 분담금. 화면의 예상 분담금 패널에 그대로 깐다"
    )
    prior_asset_detail: Optional[Dict[str, Any]] = Field(
        None,
        description="종전자산 분해(구역 토지분·건물분, r_구역, 실측 조합원 수, ρ). "
                    "ρ 가 1 이 아니면 건물분으로 약분이 깨져 개인화된 상태",
    )
    rental_exclusive_area_m2: float = Field(
        0.0, description="계산에 쓴 임대 1세대 전용면적(㎡). 세부 설정 입력란에 되돌려 보여준다"
    )
    member_count_range: MemberCountRange = Field(..., description="조합원 수 슬라이더 가동 범위")
    timeline: Optional[Dict[str, Any]] = Field(
        None,
        description="사업 일정(고시일·착공·최종 인가)과 시점별 값. 관리처분 확정 분담금 → 준공 정산 분담금의 "
                    "단계별 변화(분양 시점 반영 · 물가변동 · 비물가 초과)와 조합원 분양가(고시일 확정)를 담는다",
    )
    warnings: List[str] = Field(default_factory=list, description="사업성 계산 경고 메시지")
    credits_remaining: int = Field(..., description="남은 일일 크레딧")