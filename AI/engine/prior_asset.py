# 종전자산(종전의 토지·건축물) 평가액 추정
#
# 도시정비법 제74조 제1항 제5호가 말하는 "종전의 토지 또는 건축물의 명세 및
# 사업시행계획인가의 고시가 있은 날을 기준으로 한 가격" 이다.
# 실무 감정평가는 토지와 건물을 따로 평가해 합친다.
#
#   토지 : 공시지가기준법 (감정평가에 관한 규칙 제14조)
#          공시지가 × 시점수정 × 지역요인 × 개별요인 × 그 밖의 요인 보정
#   건물 : 원가법 (제15조)
#          재조달원가 − 감가수정 = 재조달원가 × 잔가율
#
# 우리는 토지 쪽 네 보정항을 하나(land_multiplier)로 묶고, 건물은 원가법을 그대로 쓴다.
#
# 왜 건물을 따로 떼는가
#   공시지가는 토지만이라, 배수 하나로 종전자산을 만들면 모든 조합원의 건물 가치가
#   구역 평균과 같다고 가정하는 셈이 된다. 그러면 개인과 구역에 같은 배수가 들어가
#   분담금에서 약분되어 버린다(수치로 확인했다).
#   건물을 분리해야 "내 집이 구역 평균보다 덜 낡았나" 가 분담금에 반영된다.

from dataclasses import dataclass, field

#구조별 내용연수·잔가율 — 행정안전부 「건축물 시가표준액 조정기준」
#  고시 원문 : "내용연수가 경과된 건축물은 최종연도의 잔가율을 적용한다"
#              → 잔존율 하한의 법적 근거다. 0 으로 떨어지지 않는다
#  (구조명, 내용연수, 최종연도 잔가율, 매년 상각률)
#  매년 상각률 × 내용연수 = 1 − 잔가율 로 표와 정확히 맞는다
STRUCTURE_TABLE = [
    (("철골철근콘크리트", "철골철근", "통나무"),                      50, 0.20, 0.016),
    (("철근콘크리트", "라멘", "석구조", "석조", "프리캐스트", "목구조"), 40, 0.20, 0.020),
    (("철골", "스틸하우스", "연와", "보강콘크리트", "보강블록",
      "황토", "시멘트벽돌", "벽돌", "목조", "ALC", "와이어패널"),      30, 0.10, 0.030),
    (("시멘트블록", "블록", "경량철골", "조립식패널", "FRP"),          20, 0.10, 0.045),
    (("석회", "흙벽돌", "돌담", "토담", "철파이프", "컨테이너"),        10, 0.10, 0.090),
]

#구조를 알 수 없을 때 쓰는 값. 재개발 구역 노후 주택에서 가장 흔한 구간을 택한다
DEFAULT_STRUCTURE = ("벽돌구조", 30, 0.10, 0.030)


@dataclass
class BuildingSpec:
    structure: str          # 건축물대장 strctCdNm (예: "철근콘크리트구조")
    floor_area_m2: float    # 연면적(㎡). 집합건물이면 내 전유+공용 몫
    elapsed_years: float    # 경과연수 = 평가시점 − 사용승인일
    cost_index: float = 1.0 # 재조달원가 상대지수 (아파트 = 1.0) → building_cost_index


#재조달원가 상대지수 — 행안부 「건축물 시가표준액 조정기준」의 구조지수 × 용도지수
#  재조달원가는 아파트 공사비로 잡으므로 아파트(철근콘크리트 100 × 아파트 110)로 나눈 상대값을 곱한다.
#  잔존율(STRUCTURE_TABLE)도 같은 조정기준이라, 원래 산식(신축가격 × 구조 × 용도 × 잔가율)의 구조를 그대로 따른다.
#  ※ 과세용 지수라 정책 성격이 섞여 있다 (근린생활시설 117 > 아파트 110) — 절대 단가가 아니라 상대 비율로만 쓴다
#  ※ 2019년판 표 (2018-12 고시). 해마다 거의 바뀌지 않지만 최신판이 나오면 확인할 것
#구조지수 : 대장 표기를 키워드로 찾는다. 순서가 중요하다 ("철골철근콘크리트" 가 먼저)
#  대장의 "벽돌구조" 는 연와조(100)·시멘트벽돌조(90) 구분이 없어 시멘트벽돌조로,
#  "블록구조" 는 보강블록조(90)·시멘트블록조(60) 구분이 없어 시멘트블록조로,
#  "목구조" 는 노후 주택이라 신공법 목구조(125)가 아니라 목조(78)로 본다
STRUCTURE_COST_INDEX = [
    (("철골철근콘크리트",), 120),
    (("철근콘크리트", "라멘", "프리캐스트", "석구조", "석조", "연와"), 100),
    (("경량철골",), 60),
    (("철골",), 100),
    (("블록",), 60),
    (("벽돌", "조적"), 90),
    (("통나무",), 140),
    (("목",), 78),
]
DEFAULT_STRUCTURE_COST_INDEX = 90     # DEFAULT_STRUCTURE(벽돌구조) 와 같은 가정

#용도지수 : 아파트 110 / 단독·다중·다가구·연립·다세대·도시형생활주택 100 / 근린생활시설 117
#  공동주택은 대장 주용도로 아파트와 연립·다세대를 가를 수 없어 층수로 가른다
#  (건축법 시행령 별표1 : 주택으로 쓰는 층수가 5개 층 이상이면 아파트)
APARTMENT_USE_INDEX = 110
HOUSE_USE_INDEX = 100
NEIGHBORHOOD_USE_INDEX = 117


def building_cost_index(structure: str, main_purpose: str = "", floors: int = 0, etc_purpose: str = "") -> float:
    name = (structure or "").replace(" ", "")
    structure_index = next(
        (index for keywords, index in STRUCTURE_COST_INDEX if any(k in name for k in keywords)),
        DEFAULT_STRUCTURE_COST_INDEX,
    )
    purpose = (main_purpose or "").replace(" ", "")
    if "공동주택" in purpose:
        is_apartment = "아파트" in (etc_purpose or "") or floors >= 5
        use_index = APARTMENT_USE_INDEX if is_apartment else HOUSE_USE_INDEX
    elif "근린생활" in purpose:
        use_index = NEIGHBORHOOD_USE_INDEX
    else:
        use_index = HOUSE_USE_INDEX
    return structure_index * use_index / (100 * APARTMENT_USE_INDEX)


#건축물대장 구조명 → (내용연수, 최종연도 잔가율, 매년 상각률)
#  대장 표기가 표와 1:1 로 맞지 않아 키워드로 찾는다.
#  순서가 중요하다 — "철골철근콘크리트" 가 "철근콘크리트"·"철골" 보다 먼저 걸려야 한다
def structure_spec(structure: str) -> tuple[int, float, float]:
    name = (structure or "").replace(" ", "")
    for keywords, years, floor, annual in STRUCTURE_TABLE:
        if any(k in name for k in keywords):
            return years, floor, annual
    return DEFAULT_STRUCTURE[1], DEFAULT_STRUCTURE[2], DEFAULT_STRUCTURE[3]


#잔존율. 내용연수가 지나도 최종연도 잔가율 아래로는 떨어지지 않는다
def residual_rate(structure: str, elapsed_years: float) -> float:
    _, floor, annual = structure_spec(structure)
    return max(1.0 - annual * max(elapsed_years, 0.0), floor)


#건물분 (만원). 원가법 : 재조달원가 × 잔존율
#  replacement_cost_per_m2 : ㎡당 재조달원가(만원). 공사비 예측값을 쓴다
#    감정평가 실무기준은 재조달원가를 "기준시점에 재생산하는 데 필요한 적정원가" 로 정의한다.
#    지방세 건물신축가격기준액(2017년 67만원/㎡)은 과세용 보수값이라 쓰지 않는다
#    (둘 중 무엇을 쓰냐에 따라 ρ 가 1.07 ↔ 1.28 로 갈린다)
def building_value(building: BuildingSpec, replacement_cost_per_m2: float) -> float:
    return (
        building.floor_area_m2
        * replacement_cost_per_m2
        * building.cost_index
        * residual_rate(building.structure, building.elapsed_years)
    )


#토지분 (만원)
#  land_multiplier = (1 ÷ 공시지가 현실화율) × 감정평가 수준
#    시점수정·지역요인·개별요인·그 밖의 요인 보정을 하나로 묶은 값이다
def land_value(land_area_m2: float, price_per_m2: float, land_multiplier: float) -> float:
    return land_area_m2 * price_per_m2 / 10_000 * land_multiplier      # 원 → 만원


@dataclass
class PriorAsset:
    land: float          # 토지분(만원)
    building: float      # 건물분(만원)
    total: float         # 종전자산 평가액(만원)
    ratio: float         # 공시지가 대비 배수. 화면 표시용 "감정평가 보정률"
    residual: float      # 적용된 잔존율


#종전자산 평가액
#  share : 집합건물에서 내 몫. 전유면적 ÷ 그 건물 전유면적 합계.
#          단독주택·나대지는 1.0. 한 필지에 여러 조합원이 있으면 이 비율로 나눈다
def estimate(
    land_area_m2: float,
    land_price_per_m2: float,
    land_multiplier: float,
    building: BuildingSpec | None,
    replacement_cost_per_m2: float,
    share: float = 1.0,
) -> PriorAsset:
    land = land_value(land_area_m2, land_price_per_m2, land_multiplier) * share
    if building is None:            # 나대지
        bld, residual = 0.0, 0.0
    else:
        bld = building_value(building, replacement_cost_per_m2) * share
        residual = residual_rate(building.structure, building.elapsed_years)

    total = land + bld
    official = land_area_m2 * land_price_per_m2 / 10_000 * share       # 보정 전 공시지가
    return PriorAsset(land, bld, total, total / official if official else 0.0, residual)


# ──────────────────────────────────────────────────────────────────────────────
# 구역 집계 — 약분을 깨는 자리
#
# 지금까지 구역 종전자산 총액은 "공시지가 총액 × 단일 배수" 였다.
# 개인도 같은 배수를 쓰므로 권리가액에서 배수가 소거되어, 배수를 아무리 정교하게
# 추정해도 분담금이 1원도 안 움직였다 (수치로 확인했다).
#
#   권리가액 = (P_i × r) × [사업이익 ÷ (L × r)]      ← r 소거
#
# 약분을 깨는 유일한 길은 r_개인 ≠ r_구역 이고, 그 실체가 건물분이다.
# 개인은 "내 건물", 구역은 "모든 건물의 합" 이라 둘이 달라진다.
#
#   r_구역 = (Σ토지분 + Σ건물분) ÷ Σ공시지가
#   ρ_i    = r_개인 ÷ r_구역        ← 내 집이 구역 평균보다 덜 낡았으면 1 보다 크다
#
# ρ 를 따로 추정하지 않는다. 개인과 구역을 같은 식으로 계산하면 ρ 는 결과로 나온다.
# 새로 필요한 입력은 건축물대장(연면적·구조·사용승인일)뿐이고 전부 L1 이다.

#지목별 토지 감액률 — 「공익사업을 위한 토지 등의 취득 및 보상에 관한 법률」 시행규칙 제26조 제1항
#  도로 부분의 가치는 그 도로를 이용하는 토지로 옮겨간다는 화체(化體) 이론에 따라 감액한다.
#    사도법상 사도      인근 택지가격의 1/5   (사도개설허가를 받은 경우. 재개발 구역에선 드물다)
#    사실상의 사도      인근 택지가격의 1/3   (건축 시 도로로 제공한 땅 — 재개발 구역의 대표 유형)
#    국·공유지 도로     용도폐지 상태 기준    (공도는 공익 설치물이라 감액하지 않는다)
#
#  지목만으로는 이 셋을 구분할 수 없다. V-World 토지특성에 소유구분이 없기 때문이다.
#  재개발 구역 내 사유 도로는 대개 '사실상의 사도' 이므로 1/3 을 기본으로 두고 경고를 띄운다.
#  ※ 임의로 정한 값이 아니라 시행규칙에 명시된 비율이다. 셋 중 어느 것인지만 가정했다.
#  ※ 국·공유지 도로라면 애초에 조합원 자산이 아니므로 종전자산에서 빼야 한다 → 경고로 알린다
LAND_CATEGORY_RATE = {
    "도로": 1.0 / 3.0,
    "구거": 1.0 / 3.0,   # 시행규칙 제26조는 "도로 및 구거부지" 를 함께 규정한다
}

#건물분 비중 경고 기준.
#  월계동 실측(487필지, 건축물대장 전수) 20.1% 가 감정평가 실무 범위(10~20%)의 상단이다.
#  그 두 배를 넘으면 구역 구성이 재개발 대상지가 아니라는 신호로 본다
BUILDING_SHARE_WARN = 0.40

#필지 선택·묶기 기능 때문에 구역 평균을 상수로 박아둘 수 없다.
#  사용자가 필지를 하나 더 클릭하면 구역이 바뀐다 → 필지 단위로 계산해 합산한다.
#  사용자가 고른 필지가 곧 구역이므로 표본 추출이 아니라 전수다
@dataclass
class ParcelValuation:
    pnu: str
    land_area_m2: float
    land_price_per_m2: float        # 개별공시지가(원/㎡)
    structure: str = ""             # 건축물대장 strctCdNm
    building_area_m2: float = 0.0   # 연면적(㎡)
    elapsed_years: float = 0.0      # 경과연수
    household_count: int = 1        # 세대·가구 수 (조합원 수 실측)
    has_building: bool = False       # False 면 나대지
    land_category: str = ""          # 지목. '도로'·'구거' 는 법정 비율로 감액한다
    cost_index: float = 1.0          # 재조달원가 상대지수 (building_cost_index, 아파트 = 1.0)
    owner_type: str = ""             # 토지 소유구분 (V-World 토지소유정보, "" 면 조회 안 함)
    #주택 공시가격 (V-World) — 있으면 이 필지의 종전자산은 공시가격 ÷ 현실화율이다 (토지 + 원가법 대신).
    #  주택은 호 단위로 거래사례 감정평가를 한다 — 원가법이면 신축 빌라가 실거래의 0.69배로 낮게 잡혔다
    housing_kind: str = ""           # "공동"(다세대·연립·아파트 공동주택가격) · "단독"(단독·다가구 개별주택가격) · "" 없음
    housing_price: float = 0.0       # 공시가격 합계 (만원, 그해 1월 1일). 공동은 필지의 모든 호 합계
    housing_units: int = 0           # 공동주택가격 호수


#국·공유지 소유구분 — V-World 토지소유정보 posesnSeCode
#  02 국유지 · 04 시·도유지 · 05 군유지(시·군·구유지). 실측 : 월계동 도로 '04 시 도유지', 공원 '05 군유지'
#  국공유지는 조합원 자산이 아니므로 종전자산과 조합원 수에서 뺀다
#  (정비기반시설이면 무상양도, 그 밖이면 조합이 매입한다 — 어느 쪽이든 종전자산은 아니다)
PUBLIC_OWNER_KEYWORDS = ("국유", "도유", "시유", "군유", "구유")


def is_public_owner(owner_type: str) -> bool:
    name = (owner_type or "").replace(" ", "")
    return any(k in name for k in PUBLIC_OWNER_KEYWORDS)


#필지의 조합원(분양대상자) 수 — 서울특별시 도시 및 주거환경정비 조례 (2025-03-27 개정, 제9548호)
#  제36조제2항제3호 : 1주택 또는 1필지의 토지를 여러 명이 소유해도 1명의 분양대상자 → 단독·다가구는 대장 가구수와 상관없이 1명
#  부칙 제28조제1항 : 1997-01-15 전에 가구별로 지분 또는 구분소유등기를 마친 다가구는 허가받은 가구수 안에서 가구별 1명
#    토지소유정보의 소유권 변동일자로 1997-01-15 전부터 지분을 가진 소유자가 2명 이상이면 가구별 지분 다가구로 보고 min(가구수, 그 수).
#    (변동일자가 없으면 예전 대용 : 사용승인 1997-01-15 이전 + 공유자 2명 이상)
#    실측 : 월계동 47-2 (1994 사용승인, 공유자 2) 는 두 사람이 2020-07-16 함께 이전받은 한 채 → 1명. 같은 세대(부부) 여부는 API 에 없다
#  공동주택(다세대·연립·아파트)은 호마다 소유자가 따로라 세대수 그대로. 1세대 여러 호(제36조제2항제2호)는 못 가려낸다
#  예전에는 다가구 가구수(fmlyCnt, 월계동 최대 16)를 그대로 조합원으로 세 조합원 수가 과대했다 (2026-10-08 정정)
MULTI_HOUSEHOLD_SPLIT_BEFORE = "19970115"


def ordinance_member_count(
    main_purpose: str, approval_ymd: str, household_count: int, owner_count: int, owners_before_1997: int | None = None,
) -> int:
    households = max(int(household_count or 1), 1)
    if "단독주택" not in (main_purpose or ""):
        return households
    if owners_before_1997 is not None:
        return min(households, int(owners_before_1997)) if int(owners_before_1997) >= 2 else 1
    approved = (approval_ymd or "").strip()
    if approved and approved < MULTI_HOUSEHOLD_SPLIT_BEFORE and int(owner_count or 0) >= 2:
        return min(households, int(owner_count))
    return 1


@dataclass
class ParcelPriorAsset:
    pnu: str
    land: float
    building: float
    total: float
    residual: float
    household_count: int


@dataclass
class ZonePriorAsset:
    land_total: float        # 토지분 합계(만원)
    building_total: float    # 건물분 합계(만원)
    total: float             # 종전자산 총액(만원) = 비례율의 분모
    official_total: float    # 보정 전 공시지가 총액(만원)
    ratio: float             # r_구역. 공시지가 대비 배수
    member_count: int        # 실측 조합원 수
    parcel_count: int
    building_parcel_count: int
    parcels: list[ParcelPriorAsset] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    #종전자산에 넣은 필지(국공유지 제외)의 토지면적 합계(㎡)
    land_area_m2: float = 0.0
    #주택 공시가격으로 잡은 필지의 합계(만원)와 필지 수. total = land_total + building_total + housing_total
    housing_total: float = 0.0
    housing_parcel_count: int = 0
    #지목 '대' 필지의 토지 감정가(공시지가 × λ) 합계와 면적 — ㎡당 평균이 의무 임대 부속토지 인수가격이다 (라우터).
    #  주택 공시가격으로 잡은 필지도 토지분은 여기에 넣는다. 도로·구거(1/3 감액)는 빼서 순수 택지 단가가 되게 한다
    dae_land_total: float = 0.0
    dae_land_area_m2: float = 0.0


#구역 종전자산 총액 + 조합원 수 실측
#  조합원 수 = Σ(집합건물 세대수) + Σ(단독주택·나대지 필지 수)
#  지금까지 member_count 는 세대수 기준 슬라이더(0.75~1.25배)였다.
#  건축물대장으로 세면 슬라이더 하나가 L2 → L1 으로 내려간다.
#  조합원 수는 사업이익을 나누는 분모라 분담금에 직접 영향이 크다
#housing_rates : 주택 공시가격 현실화율 {"공동": 0.69, "단독": 0.536} — 주면 공시가격이 있는 필지를 공시가격 ÷ 현실화율로 잡는다
#housing_multiplier : 공시가격 기준 시점(그해 1월) → 평가 시점 배수 (라우터가 땅값 상승률로 준다)
def aggregate_zone(
    parcels: list[ParcelValuation],
    land_multiplier: float,
    replacement_cost_per_m2: float,
    housing_rates: dict[str, float] | None = None,
    housing_multiplier: float = 1.0,
) -> ZonePriorAsset:
    rows: list[ParcelPriorAsset] = []
    warnings: list[str] = []
    land_total = building_total = official_total = 0.0
    land_area = 0.0
    member_count = 0
    building_parcel_count = 0
    no_price_count = 0
    discounted_count = 0
    unknown_road_count = 0
    public_count = 0
    public_area = 0.0
    housing_total = 0.0
    housing_parcel_count = 0
    dae_land_total = dae_land_area = 0.0

    for parcel in parcels:
        #국공유지 : 조합원 자산이 아니다 → 종전자산·공시지가 총액·조합원 수에서 모두 뺀다
        #  (대지면적에는 남는다 — 새 단지의 대지로 들어간다)
        #  집합건물은 소유자가 호마다 달라 소유정보 표본만으로 필지 전체를 판단할 수 없다 → 단독 소유 필지만 뺀다
        #  (소유정보 자체도 앞 20행 표본이 모두 국공유일 때만 국공유로 내려온다 — zone._request_possession)
        if is_public_owner(parcel.owner_type) and parcel.household_count <= 1:
            public_count += 1
            public_area += parcel.land_area_m2
            continue

        building = (
            BuildingSpec(parcel.structure, parcel.building_area_m2, parcel.elapsed_years, parcel.cost_index)
            if parcel.has_building and parcel.building_area_m2 > 0
            else None
        )
        #지목이 도로·구거면 법정 비율로 감액한다 (화체 이론)
        category_rate = LAND_CATEGORY_RATE.get(parcel.land_category, 1.0)
        if category_rate < 1.0:
            discounted_count += 1
            if not parcel.owner_type:
                unknown_road_count += 1

        asset = estimate(
            land_area_m2=parcel.land_area_m2,
            land_price_per_m2=parcel.land_price_per_m2,
            land_multiplier=land_multiplier * category_rate,
            building=building,
            replacement_cost_per_m2=replacement_cost_per_m2,
        )

        #의무 임대 부속토지 단가의 바탕 : 지목 '대' 필지의 토지 감정가 (감액 없는 순수 택지)
        if parcel.land_category == "대":
            dae_land_total += asset.land
            dae_land_area += parcel.land_area_m2

        #주택 공시가격이 있으면 그 값 ÷ 현실화율 (토지 + 건물이 들어 있는 호·주택 단위 가격)
        rate = (housing_rates or {}).get(parcel.housing_kind)
        if rate and parcel.housing_price > 0:
            value = parcel.housing_price / rate * housing_multiplier
            asset = PriorAsset(0.0, 0.0, value, value / (parcel.land_area_m2 * parcel.land_price_per_m2 / 10_000)
                               if parcel.land_area_m2 * parcel.land_price_per_m2 else 0.0, asset.residual)
            housing_total += value
            housing_parcel_count += 1
        else:
            land_total += asset.land
            building_total += asset.building
            if building is not None:
                building_parcel_count += 1

        official_total += parcel.land_area_m2 * parcel.land_price_per_m2 / 10_000
        land_area += parcel.land_area_m2
        member_count += max(parcel.household_count, 1)

        #공시지가 조회 실패 시 0 이 들어온다. 그 필지는 토지분이 0 이 되어
        #건물분만 남고, r_구역 을 조용히 끌어올린다 (약분 구조도 왜곡된다)
        if parcel.land_price_per_m2 <= 0:
            no_price_count += 1

        rows.append(
            ParcelPriorAsset(
                pnu=parcel.pnu,
                land=asset.land,
                building=asset.building,
                total=asset.total,
                residual=asset.residual,
                household_count=max(parcel.household_count, 1),
            )
        )

    total = land_total + building_total + housing_total

    #건물분을 하나도 못 구하면 예전과 똑같이 약분된다. 조용히 넘기면 안 된다 (주택 공시가격으로 잡은 필지는 개별값이라 괜찮다)
    if parcels and building_parcel_count == 0 and housing_parcel_count == 0:
        warnings.append(
            "건축물대장을 받아오지 못해 건물분이 0 입니다. "
            "분담금이 구역 평균값으로만 나옵니다 (개인별 차이가 반영되지 않습니다)."
        )

    #국공유지는 뺐다 (토지소유정보로 확인)
    if public_count:
        warnings.append(
            f"{public_count}개 필지({public_area:,.0f}㎡)가 국·공유지라 종전자산과 조합원 수에서 뺐습니다 "
            "(조합원 자산이 아니다. 정비기반시설이면 무상양도, 그 밖이면 조합이 매입한다)."
        )

    #사유 도로·구거는 법정 비율(1/3)로 감액했다. 그 가정의 한계를 알린다
    if discounted_count:
        message = (
            f"{discounted_count}개 필지가 지목상 도로·구거(사유지)라 토지분을 1/3 로 감액했습니다 "
            "(토지보상법 시행규칙 제26조, 사실상의 사도 기준). 사도법상 사도면 1/5 입니다."
        )
        if unknown_road_count:
            message += f" 그중 {unknown_road_count}개는 소유구분을 확인하지 못했습니다 — 국·공유지면 빼야 합니다."
        warnings.append(message)

    #공시지가를 못 받은 필지. 토지분이 0 이라 종전자산이 과소평가된다
    if no_price_count:
        warnings.append(
            f"{no_price_count}개 필지의 공시지가를 불러오지 못해 토지분을 0 으로 두었습니다. "
            "종전자산이 실제보다 낮게 잡혀 분담금이 과대평가됩니다."
        )

    #건물분 비중 상한 점검.
    #  감정평가 실무에서 노후주택 밀집지의 건물분은 토지의 10~20% 수준이다
    #  (월계동 실측 487필지 = 20.1%). 이를 크게 넘으면 구역에 대단지 아파트 필지가
    #  섞인 것이다 — 300㎡ 대지에 연면적 65,836㎡ 가 올라가면 r_구역이 30 배로 튄다.
    #  재개발 대상지(단독주택 밀집지)가 아니라는 신호이므로 계산을 막지 않고 알린다
    if total and building_total / total > BUILDING_SHARE_WARN:
        warnings.append(
            f"건물분이 종전자산의 {building_total / total:.0%} 입니다 "
            f"(노후주택 밀집지는 보통 10~20%). 아파트 단지 필지가 섞여 있지 않은지 확인해 주세요 — "
            "섞이면 종전자산이 과대평가되어 분담금이 실제보다 낮게 나옵니다."
        )

    return ZonePriorAsset(
        land_total=land_total,
        building_total=building_total,
        total=total,
        official_total=official_total,
        ratio=total / official_total if official_total else 0.0,
        member_count=max(member_count, 1),
        parcel_count=len(parcels) - public_count,
        building_parcel_count=building_parcel_count,
        parcels=rows,
        warnings=warnings,
        land_area_m2=land_area,
        housing_total=housing_total,
        housing_parcel_count=housing_parcel_count,
        dae_land_total=dae_land_total,
        dae_land_area_m2=dae_land_area,
    )
