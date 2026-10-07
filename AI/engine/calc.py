from dataclasses import dataclass, replace

from AI.engine.prior_asset import BuildingSpec, building_value
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
    UnitMix,
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
    #감정평가 통지서를 받은 조합원은 그 값이 가장 정확하다
    if owner.appraisal_value is not None:
        return owner.appraisal_value

    #토지분 : 공시가격(또는 면적×공시지가) × 보정률
    #  보정률(appraisal_ratio)은 시점수정·지역요인·개별요인·그 밖의 요인 보정을 묶은 값이다
    if owner.official_price is not None:
        land = owner.official_price * owner.appraisal_ratio * owner.exclusive_share
    elif owner.land_area_m2 is not None and owner.land_price_per_m2 is not None:
        land = (
            owner.land_area_m2 * owner.land_price_per_m2 / 10000
            * owner.appraisal_ratio * owner.exclusive_share
        )
    else:
        raise ValueError("(감정평가액), (공시가격), (토지면적, 공시지가) 중 하나는 입력해야 합니다.")

    #건물분 : 원가법 (재조달원가 × 잔존율). 건축물대장 정보가 없으면 0 = 나대지로 본다
    #  건물을 분리하지 않으면 개인·구역에 같은 배수가 들어가 분담금에서 약분된다.
    #  분리하면 "내 건물이 구역 평균보다 덜 낡았나" 가 권리가액에 반영된다
    #  (같은 토지 4.5억이어도 2015년 신축이면 +18.8%, 나대지면 −13.7%)
    if (
        owner.building_area_m2
        and owner.building_elapsed_years is not None
        and owner.replacement_cost_per_m2
    ):
        building = building_value(
            BuildingSpec(
                structure=owner.building_structure or "",
                floor_area_m2=owner.building_area_m2,
                elapsed_years=owner.building_elapsed_years,
            ),
            owner.replacement_cost_per_m2,
        ) * owner.exclusive_share
    else:
        building = 0.0

    return land + building

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
    #  표준건축비는 2023년 고시값이라 관리처분 시점까지 밀어야 한다 (rental_cost_multiplier).
    #  밀지 않으면 분양가·공사비만 커져 임대 비중이 저절로 작아지고 종후자산이 과소평가된다
    rental_revenue = (
        rental_supply_m2
        * standard_build_cost_per_m2(params.rental_floor_band, params.rental_exclusive_area_m2)
        * params.rental_cost_multiplier
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

    #평형별 세대수가 전부 0 이면 구역이 너무 작다. calc_post_asset 이 ValueError 를 내기 전에 알린다
    buildable = [u for u in alloc.unit_types if u.count > 0]
    if len(buildable) < len(alloc.unit_types):
        dropped = [u.name for u in alloc.unit_types if u.count <= 0]
        warnings.append(
            f"구역이 작아 {', '.join(dropped)}형은 0세대입니다. "
            "필지를 더 선택하거나 세부 설정에서 평형을 작게 바꿔 보세요."
        )

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

    # 용적률 상향 안내 : 올렸는데 분담금이 늘어나는 이유를 알려준다
    #   도시정비법 제54조에 따라 완화 용적률의 50% 를 임대로 공급해야 하는데,
    #   임대 인수가는 표준건축비(분양가의 약 11%)뿐이라 완화분의 수입이 크게 깎인다.
    #   게다가 임대 1세대 면적이 작아 세대수가 더 빨리 늘고, 지하(세대수 비례)가 같이 커진다.
    #   → 모델상으로는 용적률을 올릴수록 사업성이 나빠진다. 계산은 일관되지만 직관과 반대라 알린다.
    #   서울시가 2024년 "사업성 보정계수"를 만든 이유가 바로 이 구조다
    #   (임대 부담 없이 허용용적률을 올려준다). 그 제도는 아직 반영하지 않았다 → ROADMAP [6]
    if params.floor_area_ratio > params.far_base:
        uplift_share = 1 - params.far_base / params.floor_area_ratio
        rental_share = alloc.rental_count * params.rental_supply_area_m2 / areas.supply_total_m2
        warnings.append(
            f"용적률을 기준({params.far_base:.0f}%)보다 {uplift_share:.0%} 올리면 "
            f"완화분의 {params.uplift_rental_share:.0%}를 임대로 공급해야 해 "
            f"임대 비중이 {rental_share:.0%}까지 올라갑니다(도시정비법 제54조). "
            "임대는 표준건축비로만 인수되어 분담금이 오히려 늘 수 있습니다. "
            "서울시 사업성 보정계수(임대 부담 없는 허용용적률 상향)는 아직 반영되지 않았습니다."
        )

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

# 전용면적 → 공급면적 (㎡)
#  세부 설정의 "입력 평형" 은 전용면적이다 (59·84·114 라고 부르는 그 숫자).
#  엔진은 공급면적으로 계산하므로 전용률로 되돌려야 한다.
#  전용률은 UNIT_MIX 실측값에서만 가져온다 (재개발 신축 7개 단지 건축물대장 전유공용면적)
#    전용 59 → 공급 83.4㎡ (70.74%) / 84 → 112.6 (74.60%) / 114 → 153.9 (74.07%)
#  코어·복도 면적이 거의 고정이라 소형일수록 전용률이 낮다.
#  측정점 사이는 선형보간하고, 바깥은 가장 가까운 측정점의 전용률을 그대로 쓴다
#  (측정 범위를 벗어난 평형은 추정이다. 사례가 쌓이면 아래 점들을 갱신할 것)
EXCLUSIVE_RATIO_POINTS = [
    (59.0, 59.0 / 83.4),
    (84.0, 84.0 / 112.6),
    (114.0, 114.0 / 153.9),
]

#임대는 전용률이 분양과 다르다. 기본값 실측 한 점(전용 39 / 공급 59)만 있으므로 상수로 둔다
RENTAL_EXCLUSIVE_RATIO = 39.0 / 59.0


def exclusive_ratio(exclusive_m2: float) -> float:
    points = EXCLUSIVE_RATIO_POINTS
    if exclusive_m2 <= points[0][0]:
        return points[0][1]
    if exclusive_m2 >= points[-1][0]:
        return points[-1][1]

    for (lo_area, lo_ratio), (hi_area, hi_ratio) in zip(points, points[1:]):
        if lo_area <= exclusive_m2 <= hi_area:
            t = (exclusive_m2 - lo_area) / (hi_area - lo_area)
            return lo_ratio + (hi_ratio - lo_ratio) * t

    return points[-1][1]


def supply_area_from_exclusive(exclusive_m2: float) -> float:
    if exclusive_m2 <= 0:
        raise ValueError("전용면적은 0보다 커야 합니다")
    return exclusive_m2 / exclusive_ratio(exclusive_m2)


def rental_supply_from_exclusive(exclusive_m2: float) -> float:
    if exclusive_m2 <= 0:
        raise ValueError("임대 전용면적은 0보다 커야 합니다")
    return exclusive_m2 / RENTAL_EXCLUSIVE_RATIO


# 세대수 비율 입력 → UnitMix (면적 몫)
#  사용자는 "59형 30%, 84형 40%, 114형 30%" 처럼 세대수 비율로 적는다.
#  UnitMix.share 는 세대수 비율이 아니라 분양 공급면적 중 그 평형의 몫이므로 환산한다.
#    면적몫_i = (세대비율_i × 공급면적_i) ÷ Σ(세대비율_j × 공급면적_j)
#  이렇게 넣으면 calc_allocation 의
#    count_i = 분양면적 × 면적몫_i ÷ 공급면적_i = 분양면적 × 세대비율_i ÷ Σ(...)
#  가 되어 세대수 비가 입력한 비율과 같아진다 (세대수 내림 오차만 남는다).
MAX_UNIT_TYPES = 4


def unit_mix_from_household_ratio(entries: list[tuple[float, float]]) -> list[UnitMix]:
    if not entries:
        raise ValueError("평형을 최소 1개 입력해야 합니다")
    if len(entries) > MAX_UNIT_TYPES:
        raise ValueError(f"평형은 최대 {MAX_UNIT_TYPES}개까지 입력할 수 있습니다")

    areas = [(float(ex), supply_area_from_exclusive(float(ex))) for ex, _ in entries]
    ratios = [max(float(r), 0.0) for _, r in entries]

    #입력 비율의 합이 1이 아니어도(부분 입력·반올림) 비로만 쓰므로 정규화한다
    weights = [r * supply for r, (_, supply) in zip(ratios, areas)]
    weight_total = sum(weights)
    if weight_total <= 0:
        raise ValueError("평형 비율의 합이 0보다 커야 합니다")

    mixes = []
    for (exclusive, supply), weight in zip(areas, weights):
        if weight <= 0:
            continue
        name = f"{exclusive:g}"
        mixes.append(
            UnitMix(
                name=name,
                exclusive_area_m2=round(exclusive, 2),
                supply_area_m2=round(supply, 2),
                share=weight / weight_total,
            )
        )

    if not mixes:
        raise ValueError("비율이 0보다 큰 평형이 최소 1개 있어야 합니다")

    return mixes


# 평형별 분담금 (화면의 "예상 분담금" 패널에 전부 깔아 보여줄 값)
#  사용자가 평형을 고르게 하지 않고 모든 분양 평형의 분담금을 한 번에 내려준다.
#  비례율·권리가액은 평형과 무관하므로 한 번만 구하고 분양가만 평형별로 바꾼다.
#  임대는 조합원 분양 대상이 아니라 목록에서 제외한다.
@dataclass
class UnitContribution:
    name : str                  # 평형 이름 ("84")
    exclusive_area_m2 : float   # 전용면적
    supply_area_m2 : float      # 공급면적
    count : int                 # 배분된 세대수
    member_price : float        # 조합원분양가(만원)
    contribution : float        # 분담금(만원). 음수면 환급
    contribution_ratio : float  # 분담금 ÷ 조합원분양가. 체감용 지표


def calc_contribution_all(
    params: ProjectParams, alloc: Allocation, owner: OwnerInput
) -> list[UnitContribution]:
    project = calc_project(params, alloc)
    right_value = estimate_prior_asset(owner) * project.proportional_rate / 100

    units = []
    for unit in alloc.unit_types:
        #0세대 평형은 지을 수 없으므로 목록에서 뺀다.
        #  구역이 작으면 세대수 내림(int)으로 큰 평형이 0 이 되는데,
        #  그대로 내보내면 화면에 "114형 0세대 / 분담금 19억" 처럼 의미 없는 줄이 뜬다.
        #  (실측: 198㎡ 단일 필지 → 지상 416㎡ → 114형 공급 153.9㎡ 가 0세대)
        if unit.count <= 0:
            continue

        price = member_price(params, alloc.unit_types, unit.name)
        contribution = price - right_value
        units.append(
            UnitContribution(
                name=unit.name,
                exclusive_area_m2=unit.exclusive_area_m2,
                supply_area_m2=unit.supply_area_m2,
                count=unit.count,
                member_price=price,
                contribution=contribution,
                contribution_ratio=contribution / price if price else 0.0,
            )
        )

    return units


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
