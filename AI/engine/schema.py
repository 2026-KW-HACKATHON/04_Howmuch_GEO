from dataclasses import dataclass, field

from AI.engine.rental_cost import DEFAULT_FLOOR_BAND
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
    #주차 여유율 = 실제 주차대수 ÷ 법정 주차대수 (L2). 법정 대수는 평형 구성에서 계산한다 → calc.legal_parking_count
    #  세대당 대수를 고정하면 작은 평형 구역에서 지하가 부풀어 분담금이 과대해진다 (법정 0.75~1.37대/세대)
    parking_margin: float

    # 분양
    member_count: int                   # 조합원 수 (L1)
    general_price_per_m2 : float        # 제곱 당 일반 분양가(만원) (L2/L3)
    member_price_ratio : float          # 조합원 분양가(일반분양가 대비 비율) (L2)
    #조합원분양가 시점 계수 = (관리처분 시점 일반분양가) ÷ (분양 공고 시점 일반분양가).
    #  조합원분양가는 관리처분계획에서 명목으로 확정되고, 일반분양은 그보다 늦은 착공 무렵에 한다.
    #  엔진은 조합원분양가를 "일반분양가 × 비율" 로 계산하므로, 일반분양가를 분양 공고 시점으로
    #  밀면 조합원분양가까지 따라 오른다. 이 계수로 관리처분 시점 값에 묶어 둔다 (1.0 = 같은 시점)
    member_price_time_factor : float = 1.0
    #임대 인수수입 (건물) : 세대당 정액이 아니라 "임대 공급면적 × 단가 + 임대 몫 지하층면적 × 지하층 단가" 다
    #  · 의무 임대    : 기본형건축비(지상층 + 지하층)의 80% (도시정비법 시행령 제68조②1, 2025-03-18 시행 · 서울시 조례 제41조①)
    #  · 제54조 완화분 : 공공건설임대주택 표준건축비, 지하층은 그 63% (도시정비법 제55조② · 서울시 매입기준)
    #  층수 구간만 사용자가 고르고(노드 슬라이더), 전용면적 구간은 아래 값에서 자동으로 정해진다
    rental_floor_band : str = DEFAULT_FLOOR_BAND      # 임대동 층수 구간 (L2, 노드 슬라이더)
    rental_exclusive_area_m2 : float = 39.0           # 임대 1세대 주거전용면적. 표의 전용면적 구간을 고르는 데 쓴다 (L1)
    #의무 임대 건물 인수가격 시점 보정 배수 = 건설공사비지수(일반분양 공고 시점) ÷ 건설공사비지수(기본형건축비 고시 월).
    #  제68조는 "일반분양 공고일 직전에 고시된" 기본형건축비를 쓴다. 기본형건축비는 자재비·노무비 변동을 반영해
    #  매년 3·9월(+비정기) 다시 고시되는 값이라 공사비지수로 민다 (L3)
    rental_cost_multiplier : float = 1.0
    #제54조 완화분 건물 인수가격 시점 보정 배수 (표준건축비 고시 월 → 인수 시점).
    #  표준건축비는 정책가격이라 공사비지수가 아니라 고시 개정 실측 인상률(연 1.42%)로 민다 (L3)
    uplift_rental_cost_multiplier : float = 1.0
    #의무 임대 부속토지 감정가(만원/㎡). 의무 임대의 부속토지는 감정가로 인수한다
    #  (기준시점 = 사업시행계획인가 고시일 → 종전자산 토지분과 같은 시점·방법이라 라우터가 거기서 구한다, L3).
    #  제54조 완화분 임대의 부속토지는 기부채납(무상)이라 이 값을 곱하지 않는다.
    #  기본값 0 = 부속토지 수입을 넣지 않는다 (라우터를 거치지 않는 호출용)
    rental_land_price_per_m2 : float = 0.0
    #공공기여 방식 (AI/engine/public_contribution.py). 기본값 0 = 토지로만 낼 때 (L3, 라우터가 계산)
    #  현금 기부채납액(만원) : "토지 + 현금" 이면 기부면적의 절반을 현금으로 낸다 → 사업비에 더한다
    contribution_cash : float = 0.0
    #  기부채납 공공임대 세대수 : "공공임대 건축물" 이면 공공임대를 지어 기부채납한다 → 인수대금 없음.
    #  의무 임대·제54조 완화분과 별개로 주택 공급면적에서 떼어 둔다
    donated_rental_count : int = 0

    # 비용
    construction_cost_per_pyeong : float    # 평당 공사비(만원) (L2/L3)
    other_cost_ratio : float                # 기타사업비 / 공사비 (L2)

    # 종전 자산 총액 : 기본은 입력, 모르면 (조합원 평균 * 조합원 수)
    total_prior_asset : float | None = None  # 종전자산 총액(만원). 선택 필지 공시지가 합계에서 환산 (L1→L3)

    # 비례율 고정값

    # 임대 (용적률과 연동. 도시정비법 제54조 + 서울시 조례 기준)
    #정비계획 상한용적률(%). 도시정비법 제54조④ 초과용적률(= 법적상한 − 정비계획 용적률)을 재는 기준점.
    #  4단 체계의 상한(사업성 보정계수 반영), 4단이 없는 용도지역은 조례용적률 (zone.far_plan().ceiling) (L1)
    far_base : float
    base_rental_ratio : float        # 기준 구간 임대 의무비율 (연면적 기준, 서울 주거지역 0.10) (L1)
    uplift_rental_share : float      # 상향 완화 구간 중 임대로 공급하는 비율 (법정 상한 0.75) (L1)
    rental_supply_area_m2 : float    # 임대 1세대 공급 면적 (L1)

    # 상가 및 커뮤니티
    commercial_ratio : float            # 지상 연면적 중 상가 비율 (L2)
    #공급면적 전환율 = 1.0.
    #  공급면적(전용+주거공용)과 건축물대장 주택 연면적이 같은 범위를 재기 때문이다.
    #  2026-10-02 신축 5개 단지 전유공용면적으로 실측해 100.0~100.6% 를 확인했다.
    #  (전용률 0.71 과 혼동하지 말 것 — 그건 전용/공급 비율이고 여기는 연면적/공급 비율이다)
    housing_supply_efficiency : float   # 주택 연면적 → 공급면적 합계 전환율 (L1, 실측 1.0)
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
        if self.rental_land_price_per_m2 < 0:
            raise ValueError(
                f"rental_land_price_per_m2 는 0 이상이어야 합니다: {self.rental_land_price_per_m2}"
            )
        if self.contribution_cash < 0 or self.donated_rental_count < 0:
            raise ValueError(
                f"공공기여 현금·기부 세대수는 0 이상이어야 합니다: {self.contribution_cash}, {self.donated_rental_count}"
            )

        #상가 + 커뮤니티가 1 이상이면 주택 연면적이 0 이하가 됨
        non_housing = self.commercial_ratio
        if not 0 <= non_housing < 1:
            raise ValueError(
                f"commercial_ratio 는 0 이상 1 미만이어야 합니다: {non_housing}"
            )

        #종전자산 총액 : 총액과 평균 중 하나는 있어야 비례율 계산 가능
        if self.total_prior_asset is None or self.total_prior_asset <= 0:
            raise ValueError(
                "total_prior_asset(종전자산 총액)이 필요합니다. 선택 구역의 공시지가 총액에서 환산하세요."
            )

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
    #대표 용도지역 (면적이 가장 넓은 것). 용적률 범위와 상가 비율 상한을 정하는 데 쓴다 (L1)
    zoning : str | None = None


#조합원 개인 입력값
@dataclass(kw_only=True)
class OwnerInput:
    desired_unit: str   # UnitType 이름 (84A 등) (L2)
 
    # 종전자산 추정 우선순위: 감정평가액 > 공시가격 > 토지면적×공시지가
    #   입력은 모두 L1(API·법정 고정값)이고, 그것으로 계산한 종전자산 평가액이 L3(추정) 이다.
    appraisal_value: float | None = None    # 감정평가액(만원). 통지서를 받은 조합원이 직접 입력 (L1)
    official_price: float | None = None     # 주택/공동주택 공시가격(만원) (L1)
    land_area_m2: float | None = None       # 토지 지분면적 (L1)
    land_price_per_m2: float | None = None  # 개별공시지가(원/㎡) (L1)

    # 건물 정보 (건축물대장). 있으면 종전자산을 토지분 + 건물분으로 나눠 계산한다.
    #   없으면 건물분 0 = 나대지로 보고 토지분만 쓴다 (기존 동작과 같다)
    building_structure: str | None = None    # strctCdNm (예: "철근콘크리트구조") (L1)
    building_area_m2: float | None = None    # 연면적(㎡). 집합건물이면 share 로 나눈다 (L1)
    building_elapsed_years: float | None = None  # 경과연수 = 평가시점 − 사용승인일 (L1)
    exclusive_share: float = 1.0             # 집합건물에서 내 몫 (전유면적 ÷ 건물 전유합계) (L1)
    replacement_cost_per_m2: float | None = None  # ㎡당 재조달원가(만원). 공사비 예측값 (L3)
    building_cost_index: float = 1.0         # 재조달원가 상대지수 (구조·용도, 아파트 = 1.0) — 구역 집계와 같은 값 (L1)

    # 공시가격 → 종전자산 환산 배수.
    #   단일 배수는 개인·구역에 같은 값이 들어가 분담금에서 약분된다(수치 검증됨).
    #   3번째 모델에서 토지분 + 건물분 분리로 교체 예정 → 그때 이 필드는 토지분 배수(λ)만 맡는다
    #     토지분 = 토지면적 × 공시지가 × λ,  λ = (1/현실화율 0.648) × 감정평가수준 k
    #     건물분 = 연면적 × 재조달원가 × 잔존율(법정 잔가율표)
    appraisal_ratio: float                  # (L1 입력 → L3 결과)


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
