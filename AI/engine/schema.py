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

# 정비구역 단위 파라미터
@dataclass(kw_only=True)
class ProjectParams:
    name : str                  # 이름 (장위 1구역 등) (L1)
    project_type : ProjectType  # 재개발 / 재건축 선택 (L1)

    # 규모
    site_area_m2 : float        # 정비구역 면적 
    floor_area_ratio: float     # 용적률(%) 
    underground_ratio: float    # 지하 연면적 / 지상 연면적

    # 분양
    unit_types: list[UnitType]
    member_count: int                   # 조합원 수
    general_price_per_m2 : float        # 제곱 당 일반 분양가(만원)
    member_price_ratio : float          # 조합원 분양가(일반분양가 대비 비율)
    rental_count : int = 0              # 임대 세대수
    rental_price_per_unit : float = 0.0 # 임대 세대 당 인수가(만원)

    # 비용
    construction_cost_per_pyeong : float 
    other_cost_ratio : float

    # 종전 자산 총액 : 기본은 입력, 모르면 (조합원 평균 * 조합원 수)
    total_prior_asset : float | None = None
    avg_prior_asset : float | None = None

    # 비례율 고정값
    proportional_rate: float | None = None   # 비례율 고정값(%). None이면 사업 수지로 계산
   

#조합원 개인 입력값
@dataclass(kw_only=True)
class OwnerInput:
    desired_unit: str   # UnitType 이름 (84A 등)
 
    # 종전자산 추정 우선순위: 감정평가액 > 공시가격 > 토지면적×공시지가
    appraisal_value: float | None = None    # 감정평가액(만원)
    official_price: float | None = None     # 주택/공동주택 공시가격(만원)
    land_area_m2: float | None = None       # 토지 지분면적
    land_price_per_m2: float | None = None  # 개별공시지가(원/㎡)

    appraisal_ratio: float                  # 감정평가액 / 공시가격 보정률


#사업 단위 계산 결과
@dataclass
class ProjectResult:
    gross_floor_area_m2: float                    # 지상+지하 연면적
    total_cost: float                             # 총사업비
    total_post_asset: float                       # 종후자산 총액(총수입)
    total_prior_asset: float                      # 종전자산 총액  
    proportional_rate: float                      # 비례율(%)
    rate_fixed: bool                              # True면 입력한 고정값, False면 계산값
    warnings: list[str] = field(default_factory=list)   # 특정 조건 시 warning 문구 띄움

    
# 조합원 개인 계산 결과
@dataclass
class ContributionResult:
    prior_asset: float          # 종전자산평가액(추정)
    proportional_rate: float    # 비례율(%)
    right_value: float          # 권리가액 = 종전자산 × 비례율
    member_price: float         # 희망 평형 조합원분양가
    contribution: float         # 분담금 (음수면 환급)
    project: ProjectResult
