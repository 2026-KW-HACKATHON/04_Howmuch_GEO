from dataclasses import dataclass, field
from enum import Enum

PER_PYEONG_TO_PER_M2 = 1 / 3.3058

class ProjectType(str, Enum):
    REDEVELOPMENT = "재개발"
    RECONSTRUCTION = "재건축"

# 분양 면적  
@dataclass
class UnitType:
    name : str                  # 면적 이름
    exclusive_area_m2 : float   # 전용면적(평형 구분용)
    supply_area_m2 : float      # 분양가 산정 기준 공급면적
    count : int                 # 분양 세대수 (일반 + 조합)

# 공급 면적
@dataclass
class UnitMix:
    name : str                  # 구성 (84, 59) (L1)
    exclusive_area_m2 : float   # 전용 면적 (L1)
    supply_area_m2 : float      # 공급 면적 (L1)
    share : float               # 분양 면적 비율 (L1/L2)

# 정비구역 단위 파라미터
@dataclass(kw_only=True)
class ProjectParams:
    name : str                  # 이름 (장위 1구역 등) (L1)
    project_type : ProjectType  # 재개발 / 재건축 선택 (L1)

    # 규모
    site_area_m2 : float        # 정비구역 면적 (L1)
    floor_area_ratio: float     # 용적률(%) (L2)
    underground_ratio: float    # 지하 연면적 / 지상 연면적 (L1)

    # 분양
    member_count: int                   # 조합원 수 (L1)
    general_price_per_m2 : float        # 제곱 당 일반 분양가(만원) (L2/L3)
    member_price_ratio : float          # 조합원 분양가(일반분양가 대비 비율) (L2)
    rental_price_per_unit : float = 0.0 # 임대 세대 당 인수가(만원) (L1)

    # 비용
    construction_cost_per_pyeong : float    # 평당 공사비(만원) (L2/L3)
    other_cost_ratio : float                # 기타사업비 / 공사비 (L2)

    # 종전 자산 총액 : 기본은 입력, 모르면 (조합원 평균 * 조합원 수)
    total_prior_asset : float | None = None  # 종전자산 총액(만원) (L1)
    avg_prior_asset : float | None = None    # 조합원 평균 종전자산(만원) (L1/L3)

    # 비례율 고정값
    proportional_rate: float | None = None   # 비례율 고정값(%). None이면 사업 수지로 계산 (L2)

    # 임대 (용적률과 연동. 도시정비법 제54조 + 서울시 조례 기준)
    far_base : float                 # 조례 기준 용적률(%). 완화분을 재는 기준점, ZoneSummary.far_min (L1)
    base_rental_ratio : float        # 기준 구간 임대 의무비율 (연면적 기준, 서울 주거지역 0.10) (L1)
    uplift_rental_share : float      # 상향 완화 구간 중 임대로 공급하는 비율 (법정 상한 0.75) (L1)
    rental_supply_area_m2 : float    # 임대 1세대 공급 면적 (L1)

    # 상가 및 커뮤니티
    commercial_ratio : float            # 지상 연면적 중 상가 비율 (L2)
    community_ratio : float             # 커뮤니티(부대시설) 비율 (L1)
    housing_supply_efficiency : float   # 주택 연면적 → 공급면적 합계 전환율 (L1 가정)
    commercial_price_ratio : float      # 상가 분양가 = 일반분양가 × 평균 상가 분양가 (L1 가정)

    #UnitMix template
    unit_mix_list : list[UnitMix]   # 공급 면적 구성 백터 리스트 (L1/L2)

    #생성 시점 검증 : 계산이 불가능한 조합이면 바로 에러
    def __post_init__(self):
        #평형 구성 : 비어 있으면 배분 자체가 불가능
        if not self.unit_mix_list:
            raise ValueError("unit_mix_list 가 비어 있습니다.")

        #share 합계는 1.0 (부동소수 오차 허용)
        share_sum = sum(u.share for u in self.unit_mix_list)
        if abs(share_sum - 1.0) > 1e-6:
            raise ValueError(f"unit_mix_list 의 share 합계가 1.0 이 아닙니다: {share_sum}")

        #비율 범위
        if not 0 <= self.base_rental_ratio <= 1:
            raise ValueError(f"base_rental_ratio 는 0~1 이어야 합니다: {self.base_rental_ratio}")
        if not 0 <= self.uplift_rental_share <= 0.75:
            raise ValueError(
                f"uplift_rental_share 는 0~0.75 이어야 합니다(법정 상한 75%): {self.uplift_rental_share}"
            )
        if self.far_base <= 0:
            raise ValueError(f"far_base 는 0보다 커야 합니다: {self.far_base}")
        if not 0 < self.housing_supply_efficiency <= 1:
            raise ValueError(
                f"housing_supply_efficiency 는 0~1 이어야 합니다: {self.housing_supply_efficiency}"
            )

        #상가 + 커뮤니티가 1 이상이면 주택 연면적이 0 이하가 됨
        non_housing = self.commercial_ratio + self.community_ratio
        if not 0 <= non_housing < 1:
            raise ValueError(
                f"commercial_ratio + community_ratio 는 0 이상 1 미만이어야 합니다: {non_housing}"
            )

        #종전자산 총액 : 총액과 평균 중 하나는 있어야 비례율 계산 가능
        if self.total_prior_asset is None and self.avg_prior_asset is None:
            raise ValueError("total_prior_asset 또는 avg_prior_asset 중 하나는 필요합니다.")

# 필지 1개당 입력값
@dataclass
class ParcelInfo:
    pnu : str                           # 필지 고유번호 (L1)
    area_m2 : float                     # 필지 면적 (L1)
    land_price_per_m2 : float           # 필지 당 공시지가 (L1)
    zoning : str                        # 필지 용도 (1종, 2종 등) (L1)
    land_category : str | None = None   # 지목 (필지 용도, 대, 도로, 전, 답 등) (L1)

# zone.py 정보 입력값
@dataclass
class ZoneSummary:
    site_area_m2 : float        # 총 필지 면적
    far_min : float             # 고시 기준 용적률 (최소 용적률)
    far_max : float             # 슬라이더 용적률 최댓값
    land_value_total : float    # 면적 * 공시지가 의 총 값 (만원)

    pnus : list[str]            # 선택된 필지 목록
    warnings : list[str] = field(default_factory=list) # 특정 조건 시 warning 문구 띄움
    region : str | None = None  # 공사비 예측을 위한 해당 지역 이름, 예측 모듈에 넘길 지역 (L1)


#조합원 개인 입력값
@dataclass(kw_only=True)
class OwnerInput:
    desired_unit: str   # UnitType 이름 (84A 등) (L2)
 
    # 종전자산 추정 우선순위: 감정평가액 > 공시가격 > 토지면적×공시지가
    appraisal_value: float | None = None    # 감정평가액(만원) (L2/L3)
    official_price: float | None = None     # 주택/공동주택 공시가격(만원) (L1)
    land_area_m2: float | None = None       # 토지 지분면적 (L1)
    land_price_per_m2: float | None = None  # 개별공시지가(원/㎡) (L1)

    appraisal_ratio: float                  # 감정평가액 / 공시가격 보정률 (L1)


#사업 단위 계산 결과
@dataclass
class ProjectResult:
    unit_types : list[UnitType] # 배분된 평형별 세대수
    rental_count : int          # 배분된 임대 세대수
    commercial_area_m2: float   # 상가 면적

    gross_floor_area_m2 : float # 지상+지하 연면적
    total_cost : float          # 총사업비
    total_post_asset : float    # 종후자산 총액(총수입)
    total_prior_asset : float   # 종전자산 총액  
    proportional_rate : float   # 비례율(%)
    rate_fixed : bool           # True면 입력한 고정값, False면 계산값

    warnings : list[str] = field(default_factory=list) # 특정 조건 시 warning 문구 띄움
    
# 조합원 개인 계산 결과
@dataclass
class ContributionResult:
    prior_asset : float          # 종전자산평가액(추정)
    proportional_rate : float    # 비례율(%)
    right_value : float          # 권리가액 = 종전자산 × 비례율
    member_price : float         # 희망 평형 조합원분양가
    contribution : float         # 분담금 (음수면 환급)
    project : ProjectResult
