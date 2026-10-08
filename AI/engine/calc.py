from dataclasses import dataclass, replace

from AI.engine.prior_asset import BuildingSpec, building_value
from AI.engine.rental_cost import (
    UPLIFT_BASIS,
    UPLIFT_RATIO,
    takeover_basement_price_per_m2,
    takeover_price_per_m2,
    uplift_takeover_basement_price_per_m2,
    uplift_takeover_price_per_m2,
)
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
                cost_index=owner.building_cost_index,
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


#법정 주차대수 — 「주택건설기준 등에 관한 규정」 제27조 제1항 (특별시)
#  ① 주택 전용면적 합계 기준 : 85㎡ 이하 1대/75㎡, 85㎡ 초과 1대/65㎡
#  ② 세대당 1대 이상 (세대당 전용면적 60㎡ 이하면 0.7대)
#  두 조건을 모두 채워야 하므로 합계끼리 비교한다 (세대마다 큰 값을 골라 더하면 과대해진다).
#  임대 세대도 같은 단지의 주택이라 포함한다 — 여유율도 임대 포함 단지 전체로 쟀다
def legal_parking_count(unit_types: list[UnitType], rental_count: int, rental_exclusive_m2: float) -> float:
    homes = [(u.exclusive_area_m2, u.count) for u in unit_types] + [(rental_exclusive_m2, rental_count)]
    area_based = sum((area / 75 if area <= 85 else area / 65) * count for area, count in homes)
    minimum = sum((0.7 if area <= 60 else 1.0) * count for area, count in homes)
    return max(area_based, minimum)


def calc_construction_cost(params: ProjectParams, areas: Areas, alloc: "Allocation") -> Costs:
    #지하 연면적 = 주차대수 × 1대당 면적 + 세대수 × 기타(기계실·창고·커뮤니티).
    #  주차대수 = 평형 구성에서 계산한 법정 대수 × 여유율 (여유율이 슬라이더다)
    #  임대(의무·완화분)와 공공기여로 기부채납하는 공공임대도 같은 단지의 세대다
    rental_homes = alloc.rental_count + alloc.donated_rental_count
    household_count = sum(u.count for u in alloc.unit_types) + rental_homes
    parking_count = (
        legal_parking_count(alloc.unit_types, rental_homes, params.rental_exclusive_area_m2)
        * params.parking_margin
    )
    underground_m2 = (
        parking_count * PARKING_AREA_PER_CAR_M2
        + household_count * UNDERGROUND_ETC_PER_HOUSEHOLD_M2
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
    #공공기여를 현금으로 낸 몫 (토지 + 현금 방식). 사업시행인가 시점 금액에 고정한다
    all_cost += params.contribution_cash

    return Costs(construction_cost_m2, underground_m2, gross_m2, construction_cost, all_cost)

# 세대수 배분 (추가 예정)
@dataclass
class Allocation:
    unit_types : list[UnitType]   # 평형별 세대수
    rental_count : int            # 임대 세대수 (의무 임대 + 제54조 완화분)
    sale_supply_m2 : float        # 분양 공급면적 합계
    #임대 중 의무 임대 세대수. 나머지(rental_count − 이 값)가 제54조 완화분이다.
    #  건물 단가(의무 = 기본형건축비 80%, 완화분 = 표준건축비)와 부속토지(의무 = 감정가, 완화분 = 기부채납)가 다르다
    base_rental_count : int = 0
    #공공기여로 기부채납하는 공공임대 세대수 (공공임대 건축물 방식). rental_count 에 넣지 않는다 — 인수대금이 없다
    donated_rental_count : int = 0

    #제54조 용적률 완화분 임대 세대수
    @property
    def uplift_rental_count(self) -> int:
        return self.rental_count - self.base_rental_count

def calc_allocation(params: ProjectParams, areas: Areas) -> Allocation:
    supply_total_m2 = areas.supply_total_m2     # 주택 공급면적 합계

    # 용적률 샹항에 따른 임대율 (도시정비법 제54조)
    # 기준 구간(조례 기준 최대 용적률) -> 임대 의무비율 base_rental_ratio
    # 완화 구간(상향 구간) -> 증가분의 uplift_rental_share 를 임대로 공급
    base_share = min(params.far_base / params.floor_area_ratio, 1.0)  # 전체 중 기준 구간의 몫
    base_supply_m2 = supply_total_m2 * base_share                     # 기준 구간 공급면적
    uplift_supply_m2 = supply_total_m2 - base_supply_m2               # 완화 구간 공급면적

    base_rent_m2 = base_supply_m2 * params.base_rental_ratio           # 의무 임대 면적
    uplift_rent_m2 = uplift_supply_m2 * params.uplift_rental_share     # 제54조 완화분 임대 면적
    rent_target_m2 = base_rent_m2 + uplift_rent_m2                     # 임대로 공급해야 할 면적

    rental_count = int(rent_target_m2 / params.rental_supply_area_m2)  # 임대 세대수 (내림)
    #의무 임대만 따로 센다 — 부속토지 인수 조건이 완화분과 달라서다 (calc_post_asset).
    #  내림은 합계에서 한 번 하고, 의무분도 내림한 나머지를 완화분으로 본다 (어긋나도 1세대 이내)
    base_rental_count = min(int(base_rent_m2 / params.rental_supply_area_m2), rental_count)
    rent_total_m2 = rental_count * params.rental_supply_area_m2        # 내림한 세대수로 면적 재계산
    #공공기여 기부채납 공공임대 (공공임대 건축물 방식) : 의무·완화분 임대와 별개로 떼어 둔다
    donated_rental_count = params.donated_rental_count
    donated_m2 = donated_rental_count * params.rental_supply_area_m2
    sale_supply_m2 = max(supply_total_m2 - rent_total_m2 - donated_m2, 0.0)   # 분양 공급면적

    # 평형별 세대수
    unit_types = []
    for mix in params.unit_mix_list:
        count = int(sale_supply_m2 * mix.share / mix.supply_area_m2)
        unit_types.append(UnitType(mix.name, mix.exclusive_area_m2, mix.supply_area_m2, count))

    return Allocation(
        unit_types,
        rental_count,
        sale_supply_m2,
        base_rental_count=base_rental_count,
        donated_rental_count=donated_rental_count,
    )

# 종후 자산(총 수입)
@dataclass
class Revenues:
    member_share : float        # 분양 세대 중 조합원 비율
    blended_price_m2 : float    # 조합원/일반 가중 평균 분양가(만원/㎡)
    housing_revenue : float     # 주택 분양수입
    rental_revenue : float      # 임대 인수수입 합계 (건물 + 의무 임대 부속토지)
    commercial_revenue : float  # 상가 분양수입
    total_post_asset : float    # 종후자산 총액
    rental_building_revenue : float = 0.0   # 임대 건물 인수대금 합계 (의무 + 완화분)
    rental_land_revenue : float = 0.0       # 의무 임대 부속토지 인수대금 (감정가)
    rental_land_area_m2 : float = 0.0       # 의무 임대 부속토지 면적(㎡)
    rental_base_building_revenue : float = 0.0    # 의무 임대 건물 (기본형건축비 지상층 + 지하층의 80%)
    rental_uplift_building_revenue : float = 0.0  # 제54조 완화분 건물 (표준건축비, 지하층 63%)
    rental_underground_m2 : float = 0.0           # 임대 몫 지하층면적(㎡)

def calc_post_asset(params: ProjectParams, areas: Areas, alloc: Allocation, costs: Costs | None = None) -> Revenues:
    sale_count = sum(u.count for u in alloc.unit_types)              # 분양 세대수
    if sale_count <= 0:
        raise ValueError("분양 세대수가 0 입니다.")

    # 조합원이 평형 비율대로 배정된다고 가정 → 조합원분양가와 일반분양가의 가중 평균
    member_share = min(params.member_count / sale_count, 1)
    #조합원 몫은 관리처분 시점 가격(시점 계수), 일반분양 몫은 분양 공고 시점 가격이다
    blended_price_m2 = params.general_price_per_m2 * (
        member_share * params.member_price_ratio * params.member_price_time_factor
        + (1 - member_share)
    )

    # 내림으로 세대수를 정했으므로 면적도 세대수에서 다시 합산.
    #  주택형마다 ㎡당 분양가가 다르다 (size_price_index, 84형 = 1.00) → 공급면적에 지수를 곱해 더한다
    sale_supply_m2 = sum(u.count * u.supply_area_m2 for u in alloc.unit_types)
    priced_supply_m2 = sum(
        u.count * u.supply_area_m2 * size_price_index(u.exclusive_area_m2) for u in alloc.unit_types
    )

    housing_revenue = priced_supply_m2 * blended_price_m2
    #임대 인수수입 ① 건물 : 세대당 정액이 아니라 (임대 공급면적 × 지상층 단가 + 임대 몫 지하층면적 × 지하층 단가).
    #  의무 임대와 제54조 완화분은 단가가 다르다 (rental_cost 참조)
    #    · 의무 임대    : 기본형건축비(지상층 + 지하층)의 80% — 시행령 제68조②1 (2025-03-18 시행)
    #    · 제54조 완화분 : 표준건축비, 지하층은 그 63% — 도시정비법 제55조② · 서울시 매입기준
    #  표는 전용면적으로 행을 고르고 지상층 단가는 공급면적에 곱한다 (고시 표 머리).
    #  지하층면적 = 지하 연면적을 주택 공급면적(분양 + 임대) 비로 나눈 임대 몫
    #    (계약면적의 그 밖의 공용면적처럼 나눈다. 지하주차장 포함 — 기본형건축비·서울시 매입기준 정의 모두)
    rental_supply_m2 = alloc.rental_count * params.rental_supply_area_m2
    base_rental_supply_m2 = alloc.base_rental_count * params.rental_supply_area_m2
    uplift_rental_supply_m2 = rental_supply_m2 - base_rental_supply_m2
    if costs is None:
        costs = calc_construction_cost(params, areas, alloc)
    #  기부채납 공공임대(공공기여)도 지하층·대지를 나눠 갖는다 — 인수대금은 없다
    housing_supply_m2 = sale_supply_m2 + rental_supply_m2 + alloc.donated_rental_count * params.rental_supply_area_m2
    base_rental_underground_m2 = costs.underground_m2 * base_rental_supply_m2 / housing_supply_m2
    uplift_rental_underground_m2 = costs.underground_m2 * uplift_rental_supply_m2 / housing_supply_m2
    #  단가는 고시 월 값이라 시점까지 민다.
    #    의무 임대 : 일반분양 공고 시점까지 건설공사비지수로 (rental_cost_multiplier)
    #    완화분    : 인수 시점까지 표준건축비 개정 실측 인상률로 (uplift_rental_cost_multiplier)
    #  밀지 않으면 분양가·공사비만 커져 임대 비중이 저절로 작아지고 종후자산이 과소평가된다
    band, exclusive = params.rental_floor_band, params.rental_exclusive_area_m2
    rental_base_building_revenue = (
        base_rental_supply_m2 * takeover_price_per_m2(band, exclusive)
        + base_rental_underground_m2 * takeover_basement_price_per_m2()
    ) * params.rental_cost_multiplier
    rental_uplift_building_revenue = (
        uplift_rental_supply_m2 * uplift_takeover_price_per_m2(band, exclusive)
        + uplift_rental_underground_m2 * uplift_takeover_basement_price_per_m2(band, exclusive)
    ) * params.uplift_rental_cost_multiplier
    rental_building_revenue = rental_base_building_revenue + rental_uplift_building_revenue
    #임대 인수수입 ② 부속토지 : 의무 임대만 감정가로 인수한다. 제54조 완화분은 기부채납(무상)이라 0.
    #  감정가 기준시점은 사업시행계획인가 고시일 → 종전자산 토지분과 같은 시점·방법이라
    #  라우터가 그 ㎡당 값을 넘긴다 (rental_land_price_per_m2). 인수 시점까지 밀지 않는다.
    #  부속토지 면적 = 건축 대지 × (의무 임대 공급면적 ÷ 주택 공급면적 합계(분양 + 임대))
    #    · site_area_m2 는 공공기여를 뺀 건축 대지다 (라우터가 넘기는 값)
    #    · 상가 몫은 따로 떼지 않았다 (상가 비율 기본 2%) — 그만큼 의무 임대 몫이 약간 크게 잡힌다
    #  sale_count > 0 을 위에서 확인했으므로 분모는 0 이 아니다
    rental_land_area_m2 = params.site_area_m2 * base_rental_supply_m2 / housing_supply_m2
    rental_land_revenue = rental_land_area_m2 * params.rental_land_price_per_m2
    rental_revenue = rental_building_revenue + rental_land_revenue
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
        rental_building_revenue=rental_building_revenue,
        rental_land_revenue=rental_land_revenue,
        rental_land_area_m2=rental_land_area_m2,
        rental_base_building_revenue=rental_base_building_revenue,
        rental_uplift_building_revenue=rental_uplift_building_revenue,
        rental_underground_m2=base_rental_underground_m2 + uplift_rental_underground_m2,
    )


#제54조 완화분 건물 단가 이름 (경고 문구용). 현행 법 제55조② 는 표준건축비, 개정안이 반영되면 기본형건축비 비율
UPLIFT_TAKEOVER_TEXT = UPLIFT_BASIS if UPLIFT_RATIO == 1 else f"{UPLIFT_BASIS}의 {UPLIFT_RATIO:.0%}"


# 사업 전체 수지 → 비례율
def calc_project(params: ProjectParams, alloc: Allocation) -> ProjectResult:
    warnings = []

    areas = calc_area(params)
    costs = calc_construction_cost(params, areas, alloc)
    revenues = calc_post_asset(params, areas, alloc, costs)

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
        + (alloc.rental_count + alloc.donated_rental_count) * params.rental_supply_area_m2
    )
    if used_supply_m2 > areas.ground_m2:
        warnings.append("공급면적 합계가 지상 연면적을 초과합니다. 세대수/평형을 확인하세요.")

    # 법적상한 구간 안내 (도시정비법 제54조)
    #   제54조④ 초과용적률 = 법적상한용적률 − 정비계획으로 정하여진 용적률.
    #   재개발은 그 초과분의 50~75% 를 국민주택규모 임대로 지어야 한다 (uplift_rental_share).
    #   far_base 는 정비계획 용적률의 최대(4단의 상한, 없으면 조례)이므로,
    #   그보다 높은 용적률을 고른 경우에만 이 임대 의무가 붙는다.
    #   기준 → 허용 → 상한은 인센티브·공공기여 구간이라 여기에 해당하지 않는다.
    #   ※ 예전 문구는 "기준보다 올리면 50% 임대" 였는데 조문을 잘못 읽은 것이었다 (2026-10-07 정정)
    if params.floor_area_ratio > params.far_base:
        excess = params.floor_area_ratio - params.far_base
        rental_share = alloc.rental_count * params.rental_supply_area_m2 / areas.supply_total_m2
        warnings.append(
            f"정비계획 상한({params.far_base:.0f}%)을 넘는 법적상한 구간입니다. "
            f"초과 용적률 {excess:.0f}%p 의 {params.uplift_rental_share:.0%}를 국민주택규모 임대로 "
            f"공급해야 해 임대 비중이 {rental_share:.0%}까지 올라갑니다(도시정비법 제54조). "
            f"이 임대는 건물값({UPLIFT_TAKEOVER_TEXT})만 받고 부속토지는 기부채납해 "
            "늘어난 연면적만큼 수입이 늘지 않습니다."
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
        sale_supply_m2=alloc.sale_supply_m2,
    )


#관리처분 비례율을 목표값으로 맞추는 조합원분양가 비율 (기본 방식)
#  조합은 관리처분계획에서 조합원분양가를 정해 비례율을 맞춘다. 비율을 고정하면(예전 0.8)
#  비례율이 결과로 튀어 250~300% 가 나왔고, 개발이익이 종전자산 비례로만 나뉘었다.
#  비례율 = (종후 − 사업비) ÷ 종전 에서 비율에 따라 움직이는 건 종후의 조합원분양 수입뿐이다
#  (사업비·일반분양·임대·상가는 비율과 무관) → 비례율은 비율의 1차 함수다.
#  두 점(0, 1)의 비례율로 직선을 풀면 정확히 나온다 — 반복 계산이 필요 없다.
#  params 는 관리처분 확정 단계(모든 항목이 고시일 시점)여야 한다. 범위 제한은 부르는 쪽이 한다.
#  조합원 몫이 없어 기울기가 0 이면 풀 수 없다 → None
def solve_member_price_ratio(params: ProjectParams, alloc: Allocation, target_rate: float) -> float | None:
    rate_at_zero = calc_project(replace(params, member_price_ratio=0.0), alloc).proportional_rate
    rate_at_one = calc_project(replace(params, member_price_ratio=1.0), alloc).proportional_rate
    slope = rate_at_one - rate_at_zero
    if slope <= 1e-9:
        return None
    return (target_rate - rate_at_zero) / slope



# 조합원 수 슬라이더 범위
#  기본값 = 상한 = 세대수(전원 참여). 실제 사업은 대부분 참여한다 (2026-10-08 : 기본값을 최댓값으로)
#  하한   = 세대수 × 0.75 (조합설립 동의율 법정 최소 75%)
#  재개발도 상한을 세대수(실측 조합원 수)로 둔다. 예전 1.25 배(나대지·도로지분·무허가 소유자 여유분)는
#  근거 수치가 없었고, 실측값이 이미 나대지 필지를 1명씩 센다
#  단, 분양 세대수를 넘으면 조합원에게 줄 집이 모자라 사업이 성립하지 않으므로 거기서 자른다.
#  분양 세대수는 용적률에 따라 바뀌므로 이 함수는 계산할 때마다 다시 불러야 한다.
MEMBER_COUNT_MIN_RATIO = 0.75
MEMBER_COUNT_MAX_RATIO = {ProjectType.RECONSTRUCTION: 1.0, ProjectType.REDEVELOPMENT: 1.0}


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
    ratio = MEMBER_COUNT_MAX_RATIO.get(params.project_type, 1.0)

    raw_max = int(household_count * ratio)
    max_count = min(raw_max, sale_count)          # 분양 세대수를 넘을 수 없다
    min_count = min(int(household_count * MEMBER_COUNT_MIN_RATIO), max_count)

    return MemberCountRange(
        value=min(household_count, max_count),
        min=min_count,
        max=max_count,
        capped=raw_max > sale_count,
    )

# 주택형별 일반분양가 지수 (공급면적 ㎡당, 84형 = 1.00) — 슬라이더의 ㎡당 일반분양가는 84형 기준이다
#  청약홈 입주자모집공고 2022-01~2026-11 서울 동북권 6구 17단지 : 단지마다 (전용 밴드 안 타입의 세대가중 ㎡당 ÷ 84형 ㎡당) 을 내고
#  단지 간 중앙값을 쓴다 (39형 9단지 · 49형 9 · 59형 17 · 74형 8 · 99형 8 · 114형 5).
#  공급㎡ 기준이라 59형만 비싸다(1.048). 39·49형은 공용면적 비중이 커(공급/전용 1.40, 84형 1.36) 84형보다 낮거나 같다.
#  사이 면적은 직선으로 잇고, 바깥은 끝값 (134형 이상은 동북권 자료 없음 → 114형 값)
SIZE_PRICE_INDEX = [(39.0, 0.935), (49.0, 0.991), (59.0, 1.048), (74.0, 0.987), (84.0, 1.000), (99.0, 1.008), (114.0, 0.976)]


def size_price_index(exclusive_m2: float) -> float:
    points = SIZE_PRICE_INDEX
    if exclusive_m2 <= points[0][0]:
        return points[0][1]
    if exclusive_m2 >= points[-1][0]:
        return points[-1][1]
    for (lo_area, lo_value), (hi_area, hi_value) in zip(points, points[1:]):
        if lo_area <= exclusive_m2 <= hi_area:
            return lo_value + (hi_value - lo_value) * (exclusive_m2 - lo_area) / (hi_area - lo_area)
    return 1.0


# 희망 평형의 조합원분양가 (만원)
def member_price(params: ProjectParams, unit_types: list[UnitType], unit_name: str) -> float:
    for unit in unit_types:
        if unit.name == unit_name:
            #조합원분양가는 관리처분계획에서 확정된다 → 시점 계수로 관리처분 시점 값에 묶는다
            #  주택형별 ㎡당 지수를 곱한다 (조합원분양가 = 그 주택형 일반분양가 × 비율)
            return (
                unit.supply_area_m2
                * params.general_price_per_m2
                * size_price_index(unit.exclusive_area_m2)
                * params.member_price_ratio
                * params.member_price_time_factor
            )
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
#  소형 2점 추가 (2026-10-08) : 강북권 2015년 이후 준공 21개 단지 건축물대장 전유공용면적 호별 실측
#    (주거공용 = 지상·각층 공용 중 주용도 아파트·공동주택, 주차·기계·전기·관리·주민시설 제외. 단지별 중앙값의 중앙)
#    전용 40㎡ 0.661 (13개 단지) — 임대 실측 39/59 = 0.661 과 같다 / 46㎡ 0.671 (14개 단지).
#    예전에는 59㎡ 미만도 70.7% 로 써서 소형 공급면적이 약 6% 작게 잡혔다.
#    같은 실측에서 60㎡ 0.729 · 85㎡ 0.761 은 기존 점(70.7% · 74.6%, 공급 83.4 · 112.6㎡)과 공급면적 기준 1% 안이라 그대로 둔다.
#    대형(122㎡ 0.801 · 149㎡ 0.807)은 단지가 2~3개뿐이고 기존 114㎡ 점과 어긋나 넣지 않았다 (scratchpad/exclusive_ratio_bands.json)
#  측정점 사이는 선형보간하고, 바깥은 가장 가까운 측정점의 전용률을 그대로 쓴다
#  (측정 범위를 벗어난 평형은 추정이다. 사례가 쌓이면 아래 점들을 갱신할 것)
EXCLUSIVE_RATIO_POINTS = [
    (40.0, 0.661),
    (46.0, 0.671),
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


# 임대 전용면적 → 공급면적 (㎡)
#  소형 임대(전용 39㎡ 실측 39/59 = 0.661)와 분양 전용률 곡선(59㎡ 이상) 사이를 직선으로 잇는다.
#  서울시 공공임대 사회혼합 기준으로 임대가 분양과 같은 평형으로 섞이면 공급면적도 분양과 같다
#  (미미삼 정비계획(안) 노원구 공고 제2026-567호 : 공공주택 452 = 59.98㎡ 362 + 84.98㎡ 90,
#   "조합원 주택을 포함한 전체 주택을 대상으로 추첨" → 평균 공급 90.4㎡. 예전 한 점(0.661)이면 98.3㎡ 로 공공주택이 −11.7%)
def rental_supply_from_exclusive(exclusive_m2: float) -> float:
    if exclusive_m2 <= 0:
        raise ValueError("임대 전용면적은 0보다 커야 합니다")
    small_area, small_ratio = 39.0, RENTAL_EXCLUSIVE_RATIO
    sale_area = EXCLUSIVE_RATIO_POINTS[0][0]
    if exclusive_m2 >= sale_area:
        ratio = exclusive_ratio(exclusive_m2)
    elif exclusive_m2 <= small_area:
        ratio = small_ratio
    else:
        t = (exclusive_m2 - small_area) / (sale_area - small_area)
        ratio = small_ratio + (exclusive_ratio(sale_area) - small_ratio) * t
    return exclusive_m2 / ratio


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
