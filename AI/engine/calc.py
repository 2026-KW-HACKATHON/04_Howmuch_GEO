from dataclasses import dataclass, replace

from AI.engine.rental_cost import standard_build_cost_per_m2
from AI.engine.schema import(
    PER_PYEONG_TO_PER_M2,
    ProjectParams,
    ProjectResult,
    ProjectType,
    ParcelInfo,
    ZoneSummary,
    OwnerInput,
    UnitType,
    ContributionResult
)

# 개인 종전자산 (만원)
#  현재는 "공시가격 × 보정률" 단일 배수. 3번째 모델에서 아래로 교체한다.
#    종전자산 = 토지분 + 건물분
#      토지분 = 토지면적 × 공시지가/㎡ × λ              (토지특성 API)
#      건물분 = 연면적 × 재조달원가 × 잔존율            (건축물대장 + 법정 잔가율표)
#      집합건물이면 × (내 전유면적 ÷ 건물 전유면적 합계)
#  단일 배수로 두면 개인·구역에 같은 값이 들어가 분담금에서 약분되므로,
#  분리해야 "내 건물이 구역 평균보다 덜 낡았나" 가 분담금에 반영된다.
def estimate_prior_asset(owner: OwnerInput) -> float:
    if owner.appraisal_value is not None:
        return owner.appraisal_value
    if owner.official_price is not None:
        return owner.official_price * owner.appraisal_ratio
    if owner.land_area_m2 is not None and owner.land_price_per_m2 is not None:
        return (owner.land_area_m2 * owner.land_price_per_m2 / 10000) * owner.appraisal_ratio
    raise ValueError("(감정평가액), (공시가격), (토지면적, 공시지가) 중 하나는 입력해야 합니다.")

# 면적
@dataclass 
class Areas:
    ground_m2 : float           # 지상 연면적
    housing_total_m2 : float    # 주택 연면적
    supply_total_m2 : float     # 주택 공급면적 합계
    commercial_m2 : float       # 상가 면적

def calc_area(params: ProjectParams) -> Areas:
    ground_m2 = (params.site_area_m2 * params.floor_area_ratio) / 100                     # 지상 연면적
    #주택 연면적 : 커뮤니티는 차감하지 않는다.
    #  2026-10-02 신축 4개 단지 실측 결과 주민공동시설이 지상에 0~0.56㎡/세대뿐이고 전부 지하였다.
    #  주택건설기준 제55조의2 의 세대당 2.5㎡ 는 지하에서 충족되므로 지상 연면적에서 뺄 이유가 없다.
    housing_total_m2 = ground_m2 * (1 - params.commercial_ratio)                           # 주택 연면적
    supply_total_m2 = housing_total_m2 * params.housing_supply_efficiency                  # 공급 면적 합계
    commercial_m2 = ground_m2 * params.commercial_ratio                                   # 상가 면적

    return Areas(ground_m2, housing_total_m2, supply_total_m2, commercial_m2)

# 총 사업비
@dataclass
class Costs:
    construction_cost_m2 : float    # m2당 공사비 단가
    underground_m2 : float          # 지하 연면적
    gross_m2 : float                # 총 연면적 (지상 + 지하)
    construction_cost : float       # 총 공사비
    all_cost : float                # 총 사업비


#지하 1대당 주차면적(㎡). 장위 꿈의숲아이파크 총괄표제부 실측 72,169㎡ ÷ 2,061대 = 35.0
PARKING_AREA_PER_CAR_M2 = 35.0

#주차장을 뺀 지하 면적을 세대수로 나눈 값(㎡). 기계실·창고·커뮤니티가 들어간다.
#  같은 단지 실측 (지하 91,217 − 주차 72,169) ÷ 1,711세대 = 11.1
#  커뮤니티를 지상에서 차감하지 않는 이유가 여기 있다 — 전부 지하에 있다
UNDERGROUND_ETC_PER_HOUSEHOLD_M2 = 11.1


def calc_construction_cost(params: ProjectParams, areas: Areas, alloc: "Allocation") -> Costs:
    #지하 연면적 : 지상 대비 비율(기존 0.6)이 아니라 세대수 × 주차대수로 쌓는다.
    #  주차대수가 지하 규모를 결정하므로 사용자가 조절할 수 있는 값이 되어야 한다
    household_count = sum(u.count for u in alloc.unit_types) + alloc.rental_count
    underground_m2 = household_count * (
        params.parking_per_household * PARKING_AREA_PER_CAR_M2
        + UNDERGROUND_ETC_PER_HOUSEHOLD_M2
    )
    gross_m2 = areas.ground_m2 + underground_m2

    construction_cost_m2 = params.construction_cost_per_pyeong * PER_PYEONG_TO_PER_M2   # m2당 공사비 단가
    construction_cost = gross_m2 * construction_cost_m2                                 # 총 공사비

    #기타사업비 : 설계·감리비, 금융비용(이주비 이자), 조합운영비, 보상비, 각종 부담금·세금, 예비비.
    #  실제 재개발 사례의 총사업비 구성은 공사비 76.9% / 보상비 7.1% / 관리비 9.1% / 기타 6.9% 였다.
    #  공사비 기준으로 환산하면 23.1 ÷ 76.9 = 0.30. 통상 공사비 비중 70~80% 에 대응하는 범위가
    #  0.25(공사비 80%) ~ 0.45(공사비 69%) 라서 슬라이더를 그 폭으로 잡았고,
    #  기본값 0.35 는 공사비 비중 74% 에 해당한다 (사례 76.9% 와 통상 하단 70% 의 사이)
    all_cost = construction_cost * (1 + params.other_cost_ratio)                        # 총 사업비

    return Costs(construction_cost_m2, underground_m2, gross_m2, construction_cost, all_cost)

# 세대수 배분 (추가 예정)
@dataclass
class Allocation:
    unit_types : list[UnitType]   # 평형별 세대수
    rental_count : int            # 임대 세대수
    sale_supply_m2 : float        # 분양 공급면적 합계

def calc_allocation(params: ProjectParams, areas: Areas) -> Allocation:
    supply_total_m2 = areas.supply_total_m2     # 주택 공급면적 합계

    # 용적률 샹항에 따른 임대율 (도시정비법 제54조)
    # 기준 구간(조례 기준 최대 용적률) -> 임대 의무비율 base_rental_ratio
    # 완화 구간(상향 구간) -> 증가분의 uplift_rental_share 를 임대로 공급
    base_share = min(params.far_base / params.floor_area_ratio, 1.0)  # 전체 중 기준 구간의 몫
    base_supply_m2 = supply_total_m2 * base_share                     # 기준 구간 공급면적
    uplift_supply_m2 = supply_total_m2 - base_supply_m2               # 완화 구간 공급면적

    rent_target_m2 = (
        base_supply_m2 * params.base_rental_ratio
        + uplift_supply_m2 * params.uplift_rental_share
    )                                                                  # 임대로 공급해야 할 면적

    rental_count = int(rent_target_m2 / params.rental_supply_area_m2)  # 임대 세대수 (내림)
    rent_total_m2 = rental_count * params.rental_supply_area_m2        # 내림한 세대수로 면적 재계산
    sale_supply_m2 = supply_total_m2 - rent_total_m2                   # 분양 공급면적

    # 평형별 세대수
    unit_types = []
    for mix in params.unit_mix_list:
        count = int(sale_supply_m2 * mix.share / mix.supply_area_m2)
        unit_types.append(UnitType(mix.name, mix.exclusive_area_m2, mix.supply_area_m2, count))

    return Allocation(
        unit_types,
        rental_count,
        sale_supply_m2
    )

# 종후 자산(총 수입)
@dataclass
class Revenues:
    member_share : float        # 분양 세대 중 조합원 비율
    blended_price_m2 : float    # 조합원/일반 가중 평균 분양가(만원/㎡)
    housing_revenue : float     # 주택 분양수입
    rental_revenue : float      # 임대 인수가 수입
    commercial_revenue : float  # 상가 분양수입
    total_post_asset : float    # 종후자산 총액

def calc_post_asset(params: ProjectParams, areas: Areas, alloc: Allocation) -> Revenues:
    sale_count = sum(u.count for u in alloc.unit_types)              # 분양 세대수
    if sale_count <= 0:
        raise ValueError("분양 세대수가 0 입니다.")

    # 조합원이 평형 비율대로 배정된다고 가정 → 조합원분양가와 일반분양가의 가중 평균
    member_share = min(params.member_count / sale_count, 1)
    blended_price_m2 = params.general_price_per_m2 * (
        member_share * params.member_price_ratio + (1 - member_share)
    )

    # 내림으로 세대수를 정했으므로 면적도 세대수에서 다시 합산
    sale_supply_m2 = sum(u.count * u.supply_area_m2 for u in alloc.unit_types)

    housing_revenue = sale_supply_m2 * blended_price_m2
    #임대 인수수입 (도시정비법 제55조) : 세대당 정액이 아니라 공급면적 × 표준건축비.
    #  표는 전용면적으로 행을 고르고 단가는 공급면적에 곱한다(국토부고시 제2023-64호 주석).
    rental_supply_m2 = alloc.rental_count * params.rental_supply_area_m2
    rental_revenue = rental_supply_m2 * standard_build_cost_per_m2(
        params.rental_floor_band, params.rental_exclusive_area_m2
    )
    #상가 분양수입 : 주택 분양가 × 배수. 배수 0.7 은 기존 상가 실거래 0.48 에 신축 프리미엄을 얹은 값
    #  서울 10개 구 실거래에서 아파트가 비쌀수록 배수가 낮아진다(마포 0.36 / 노원 0.49) → 비례 가정은
    #  엄밀하지 않다. 상가 ㎡당 분양가 직접 예측으로 전환 예정(상가 수입은 종후자산의 약 5%, 우선순위 낮음)
    commercial_revenue = (
        areas.commercial_m2 * params.general_price_per_m2 * params.commercial_price_ratio
    )
    total_post_asset = housing_revenue + rental_revenue + commercial_revenue

    return Revenues(
        member_share,
        blended_price_m2,
        housing_revenue,
        rental_revenue,
        commercial_revenue,
        total_post_asset,
    )


# 사업 전체 수지 → 비례율
def calc_project(params: ProjectParams, alloc: Allocation) -> ProjectResult:
    warnings = []

    areas = calc_area(params)
    costs = calc_construction_cost(params, areas, alloc)
    revenues = calc_post_asset(params, areas, alloc)

    # 비례율 : 사업 수지로 계산한다. 고정 입력 모드는 두지 않는다.
    #   비례율을 슬라이더로 두면 공사비·분양가·용적률을 움직여도 분담금이 따라오지 않아
    #   슬라이더 네 개가 사실상 죽는다. 그래서 (종후자산 − 총사업비) ÷ 종전자산 으로만 구한다
    total_prior_asset = params.total_prior_asset
    proportional_rate = (
        (revenues.total_post_asset - costs.all_cost) / total_prior_asset * 100
    )

    sale_count = sum(u.count for u in alloc.unit_types)
    if params.member_count > sale_count:
        warnings.append(
            f"조합원 수({params.member_count})가 분양 세대수({sale_count})보다 많습니다."
        )

    used_supply_m2 = (
        sum(u.count * u.supply_area_m2 for u in alloc.unit_types)
        + alloc.rental_count * params.rental_supply_area_m2
    )
    if used_supply_m2 > areas.ground_m2:
        warnings.append("공급면적 합계가 지상 연면적을 초과합니다. 세대수/평형을 확인하세요.")

    # 비례율 경고 : 벗어난 정도에 따라 단계를 나눈다
    #   비례율은 사업 수지로 계산되므로 공사비·분양가·용적률을 조절하면 함께 움직인다
    if proportional_rate <= 0:
        warnings.append(
            f"비례율 {proportional_rate:.1f}% : 총사업비가 종후자산을 초과해 사업이 성립하지 않습니다. "
            "공사비를 낮추거나 용적률·분양가를 높여 보세요."
        )
    elif not 60 <= proportional_rate <= 140:
        warnings.append(
            f"비례율 {proportional_rate:.1f}%는 통상 범위(80~120%)를 크게 벗어납니다. 가정값을 확인하세요."
        )
    elif not 80 <= proportional_rate <= 120:
        warnings.append(f"비례율 {proportional_rate:.1f}%는 통상 범위(80~120%)를 벗어납니다.")

    return ProjectResult(
        unit_types=alloc.unit_types,
        rental_count=alloc.rental_count,
        commercial_area_m2=areas.commercial_m2,
        gross_floor_area_m2=costs.gross_m2,
        total_cost=costs.all_cost,
        total_post_asset=revenues.total_post_asset,
        total_prior_asset=total_prior_asset,
        proportional_rate=proportional_rate,
        warnings=warnings,
    )



# 조합원 수 슬라이더 범위
#  기본값 = 세대수(전원 참여, 가장 보수적)
#  하한   = 세대수 × 0.75 (조합설립 동의율 법정 최소 75%)
#  상한   = 재건축 세대수 × 1.0 / 재개발 세대수 × 1.25
#           (재개발은 나대지·도로지분·무허가건축물 소유자도 조합원이 된다)
#  단, 분양 세대수를 넘으면 조합원에게 줄 집이 모자라 사업이 성립하지 않으므로 거기서 자른다.
#  분양 세대수는 용적률에 따라 바뀌므로 이 함수는 계산할 때마다 다시 불러야 한다.
MEMBER_COUNT_MIN_RATIO = 0.75
MEMBER_COUNT_MAX_RATIO = {ProjectType.RECONSTRUCTION: 1.0, ProjectType.REDEVELOPMENT: 1.25}


@dataclass
class MemberCountRange:
    value : int    # 기본값
    min : int      # 하한
    max : int      # 상한 (분양 세대수로 잘린 값)
    capped : bool  # 분양 세대수에 걸려 잘렸는지


def member_count_range(
    params: ProjectParams, alloc: Allocation, household_count: int
) -> MemberCountRange:
    sale_count = sum(u.count for u in alloc.unit_types)
    ratio = MEMBER_COUNT_MAX_RATIO.get(params.project_type, 1.25)

    raw_max = int(household_count * ratio)
    max_count = min(raw_max, sale_count)          # 분양 세대수를 넘을 수 없다
    min_count = min(int(household_count * MEMBER_COUNT_MIN_RATIO), max_count)

    return MemberCountRange(
        value=min(household_count, max_count),
        min=min_count,
        max=max_count,
        capped=raw_max > sale_count,
    )

# 희망 평형의 조합원분양가 (만원)
def member_price(params: ProjectParams, unit_types: list[UnitType], unit_name: str) -> float:
    for unit in unit_types:
        if unit.name == unit_name:
            return unit.supply_area_m2 * params.general_price_per_m2 * params.member_price_ratio
    raise ValueError(f"존재하지 않는 평형입니다: {unit_name}")



# 희망 평형 선택 버튼 목록 (프론트에 내려줄 값)
@dataclass
class UnitOption:
    name : str              # 평형 이름 ("84"). 그대로 OwnerInput.desired_unit 으로 돌아온다
    supply_area_m2 : float  # 공급면적 (버튼에 표시)
    count : int             # 배분된 세대수 (버튼에 표시)
    member_price : float    # 조합원분양가(만원). 누르기 전에 미리 보여줄 수 있다


def unit_options(params: ProjectParams, alloc: Allocation) -> list[UnitOption]:
    options = []
    for unit in alloc.unit_types:
        price = member_price(params, alloc.unit_types, unit.name)
        options.append(UnitOption(unit.name, unit.supply_area_m2, unit.count, price))

    return options

# 조합원 개인 분담금
def calc_contribution(params: ProjectParams, alloc: Allocation, owner: OwnerInput) -> ContributionResult:
    project = calc_project(params, alloc)
    prior_asset = estimate_prior_asset(owner)
    right_value = prior_asset * project.proportional_rate / 100
    price = member_price(params, alloc.unit_types, owner.desired_unit)

    return ContributionResult(
        prior_asset=prior_asset,
        proportional_rate=project.proportional_rate,
        right_value=right_value,
        member_price=price,
        contribution=price - right_value,
        project=project,
    )
