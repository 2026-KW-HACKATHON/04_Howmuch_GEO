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

from dataclasses import dataclass

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
