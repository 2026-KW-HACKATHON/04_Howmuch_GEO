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


#구역 종전자산 총액 + 조합원 수 실측
#  조합원 수 = Σ(집합건물 세대수) + Σ(단독주택·나대지 필지 수)
#  지금까지 member_count 는 세대수 기준 슬라이더(0.75~1.25배)였다.
#  건축물대장으로 세면 슬라이더 하나가 L2 → L1 으로 내려간다.
#  조합원 수는 사업이익을 나누는 분모라 분담금에 직접 영향이 크다
def aggregate_zone(
    parcels: list[ParcelValuation],
    land_multiplier: float,
    replacement_cost_per_m2: float,
) -> ZonePriorAsset:
    rows: list[ParcelPriorAsset] = []
    warnings: list[str] = []
    land_total = building_total = official_total = 0.0
    member_count = 0
    building_parcel_count = 0
    no_price_count = 0
    discounted_count = 0

    for parcel in parcels:
        building = (
            BuildingSpec(parcel.structure, parcel.building_area_m2, parcel.elapsed_years)
            if parcel.has_building and parcel.building_area_m2 > 0
            else None
        )
        #지목이 도로·구거면 법정 비율로 감액한다 (화체 이론)
        category_rate = LAND_CATEGORY_RATE.get(parcel.land_category, 1.0)
        if category_rate < 1.0:
            discounted_count += 1

        asset = estimate(
            land_area_m2=parcel.land_area_m2,
            land_price_per_m2=parcel.land_price_per_m2,
            land_multiplier=land_multiplier * category_rate,
            building=building,
            replacement_cost_per_m2=replacement_cost_per_m2,
        )

        land_total += asset.land
        building_total += asset.building
        official_total += parcel.land_area_m2 * parcel.land_price_per_m2 / 10_000
        member_count += max(parcel.household_count, 1)
        if building is not None:
            building_parcel_count += 1

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

    total = land_total + building_total

    #건물분을 하나도 못 구하면 예전과 똑같이 약분된다. 조용히 넘기면 안 된다
    if parcels and building_parcel_count == 0:
        warnings.append(
            "건축물대장을 받아오지 못해 건물분이 0 입니다. "
            "분담금이 구역 평균값으로만 나옵니다 (개인별 차이가 반영되지 않습니다)."
        )

    #도로·구거는 법정 비율(1/3)로 감액했다. 그 가정의 한계를 알린다
    if discounted_count:
        warnings.append(
            f"{discounted_count}개 필지가 지목상 도로·구거라 토지분을 1/3 로 감액했습니다 "
            "(토지보상법 시행규칙 제26조, 사실상의 사도 기준). "
            "사도법상 사도면 1/5, 국·공유지 도로면 조합원 자산이 아니라 제외해야 합니다."
        )

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
        parcel_count=len(parcels),
        building_parcel_count=building_parcel_count,
        parcels=rows,
        warnings=warnings,
    )
