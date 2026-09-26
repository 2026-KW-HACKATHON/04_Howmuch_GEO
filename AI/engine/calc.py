from dataclasses import dataclass, replace

from AI.engine.schema import(
    PER_PYEONG_TO_PER_M2,
    ProjectParams,
    ProjectResult,
    ParcelInfo,
    ZoneSummary,
    OwnerInput,
    UnitType,
    ContributionResult
)

# 개인 종전자산 (만원)
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
    gross_m2 : float            # 총 연면적 (지상 + 지하)
    housing_total_m2 : float    # 주택 연면적
    supply_total_m2 : float     # 주택 공급면적 합계
    commercial_m2 : float       # 상가 면적

def calc_area(params: ProjectParams) -> Areas:
    ground_m2 = (params.site_area_m2 * params.floor_area_ratio) / 100                     # 지상 연면적
    gross_m2 = ground_m2 * (1 + params.underground_ratio)                                 # 총 연면적
    housing_total_m2 = ground_m2 * (1 - params.commercial_ratio - params.community_ratio) # 주택 연면적
    supply_total_m2 = housing_total_m2 * params.housing_supply_efficiency                 # 공급 면적 합계
    commercial_m2 = ground_m2 * params.commercial_ratio                                   # 상가 면적

    return Areas(ground_m2, gross_m2, housing_total_m2, supply_total_m2, commercial_m2)

# 총 사업비
@dataclass
class Costs:
    construction_cost_m2 : float    # m2당 공사비 단가
    construction_cost : float       # 총 공사비
    all_cost : float                # 총 사업비

def calc_construction_cost(params: ProjectParams, areas: Areas) -> Costs:
    construction_cost_m2 = params.construction_cost_per_pyeong * PER_PYEONG_TO_PER_M2   # m2당 공사비 단가
    construction_cost = areas.gross_m2 * construction_cost_m2                           # 총 공사비
    all_cost = construction_cost * (1 + params.other_cost_ratio)                        # 총 사업비

    return Costs(construction_cost_m2, construction_cost, all_cost)

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
    rental_revenue = alloc.rental_count * params.rental_price_per_unit
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
    costs = calc_construction_cost(params, areas)
    revenues = calc_post_asset(params, areas, alloc)

    # 종전자산 총액 : 공개된 총액 > 조합원 평균 × 조합원 수
    if params.total_prior_asset is not None:
        total_prior_asset = params.total_prior_asset
    else:
        total_prior_asset = params.avg_prior_asset * params.member_count

    # 비례율 : 고정값이 있으면 그대로, 없으면 사업 수지로 계산
    if params.proportional_rate is not None:
        proportional_rate = params.proportional_rate
        rate_fixed = True
        warnings.append("비례율 고정값 사용 : 사업비·분양가 변화가 반영되지 않습니다.")
    else:
        proportional_rate = (
            (revenues.total_post_asset - costs.all_cost) / total_prior_asset * 100
        )
        rate_fixed = False

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

    if not rate_fixed and not 60 <= proportional_rate <= 140:
        warnings.append(
            f"비례율 {proportional_rate:.1f}%는 통상 범위(80~120%)를 크게 벗어납니다. 가정값을 확인하세요."
        )

    return ProjectResult(
        unit_types=alloc.unit_types,
        rental_count=alloc.rental_count,
        commercial_area_m2=areas.commercial_m2,
        gross_floor_area_m2=areas.gross_m2,
        total_cost=costs.all_cost,
        total_post_asset=revenues.total_post_asset,
        total_prior_asset=total_prior_asset,
        proportional_rate=proportional_rate,
        rate_fixed=rate_fixed,
        warnings=warnings,
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
