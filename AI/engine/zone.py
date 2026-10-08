# 지도에서 고른 필지 목록 → 구역 단위 입력값(ZoneSummary)
# 백엔드가 V-World/토지특성 API 로 받은 필지 정보를 ParcelInfo 리스트로 넘겨주면
# 여기서 합산해서 ProjectParams 에 넣을 값과 슬라이더 범위를 만든다.
import math
from dataclasses import dataclass

from AI.engine import policy
from AI.engine.schema import ParcelInfo, ZoneSummary

# 용도지역 → (조례 기준 용적률, 법적상한용적률) %
# 기준: 서울시 도시계획조례 제55조 제1항 / 상한: 국토계획법 시행령 제85조
# 정비사업은 도시정비법 제54조에 따라 심의를 거쳐 법적상한용적률까지 완화 가능
# ※ 완화분의 일정 비율(최대 75%)은 국민주택규모 임대로 공급해야 함 → calc_allocation 에서 반영
FAR_TABLE = {
    #주거지역
    "제1종전용주거지역": (100, 100),
    "제2종전용주거지역": (120, 150),
    "제1종일반주거지역": (150, 200),
    "제2종일반주거지역": (200, 250),
    "제3종일반주거지역": (250, 300),
    "준주거지역":       (400, 500),
    #상업지역 (서울도심은 조례상 더 낮지만 여기서는 일반 기준을 쓴다)
    "중심상업지역":     (1000, 1500),
    "일반상업지역":     (800, 1300),
    "근린상업지역":     (600, 900),
    "유통상업지역":     (600, 1100),
    #공업지역
    "전용공업지역":     (200, 300),
    "일반공업지역":     (200, 350),
    "준공업지역":       (400, 400),
    #녹지지역 : 정비사업 대상이 되는 일은 드물지만, 구역 경계에 섞여 들어오는 경우가 있다
    "보전녹지지역":     (50, 80),
    "생산녹지지역":     (50, 100),
    "자연녹지지역":     (50, 100),
}

# 용도지역 → (기준용적률, 허용용적률, 상한용적률, 법적상한용적률) %  — 용도지역을 바꾸지 않는 경우
#   서울시 「2030 도시·주거환경정비기본계획(주거환경정비사업부문)」 재정비 (2024-08-22 보도자료 참고자료 3,
#   "용적률 체계 명확화·합리화", 재개발·재건축 공통)
#     기준 ──(인센티브량 × 사업성 보정계수)──→ 허용 ──(공공기여)──→ 상한 ──(도시정비법 제54조)──→ 법적상한
#   기준~상한이 "정비계획으로 정하여진 용적률" 이고, 법적상한은 국토계획법 시행령 제85조의 상한이다.
#   제54조 국민주택규모 임대(재개발은 초과용적률의 50~75%)는 **상한을 넘는 법적상한 구간에만** 붙는다.
#     제54조④ : 초과용적률 = 법적상한용적률 − 정비계획으로 정하여진 용적률
#
#   FAR_TABLE 의 2단(조례, 법적상한)과 같지 않다.
#     3종일반 : 조례 250 = 상한 250
#     2종일반 : 조례 200 < 상한 250 (= 법적상한) — 정비계획의 공공기여로 조례를 넘어 상한까지 간다
#     1종일반 : 2024 재정비로 상한·법적상한 150 → 200 (허용 인센티브는 없다 : 기준 = 허용 150)
#
#   ※ 표에 있지만 뺀 것 : 제2종(7층)(170/190/250/250) — 7층 지정 여부를 필지 조회로 알 수 없다,
#     준공업(210/230/250/400)·상업 — 선택지에 없다. 전용주거는 표에 없어 2단(조례·법적상한)으로 축퇴한다
#   값은 data/policy_rules.json (rules.far_tiers) 에 있다 — 규칙이 바뀌면 그 파일을 고친다
#     1종일반 (150, 150, 200, 200) / 2종일반 (190, 210, 250, 250) / 3종일반 (210, 230, 250, 300) / 준주거 (300, 320, 400, 500)
FAR_TIERS = {z: tuple(v) for z, v in policy.RULES["far_tiers"].items()}

# 용도지역을 바꾸는 경우 (원래 → 변경) — 같은 표의 "용도지역 변경이 있는 경우"
#   기준·허용은 원래 용도지역 쪽(1종은 허용 170), 상한·법적상한은 변경 쪽이다
#   (1종 → 2종만 상한 200 으로 2종의 250 보다 낮다)
#   (rules.far_tiers_upzoned : 1종→2종 150/170/200/250, 1종→3종 150/170/250/300, 2종→3종 190/210/250/300, 3종→준주거 210/230/400/500)
FAR_TIERS_UPZONED = {
    (base, sel): tuple(v)
    for base, targets in policy.RULES["far_tiers_upzoned"].items()
    for sel, v in targets.items()
}

#표에 없는 종상향 조합(1종·2종 → 준주거)은 표의 원칙으로 채운다 :
#  원래 용도지역의 (기준, 허용) — 위 표의 종상향 행에서 쓴 값 — + 변경 용도지역의 (상한, 법적상한)
UPZONED_BASE = {z: tuple(v) for z, v in policy.RULES["upzoned_base"].items()}

#기준 → 허용 사이의 인센티브량(%p). 사업성 보정계수가 여기에 곱해진다
#  2·3종일반 모두 20%p 로 같다 (190→210, 210→230)
def far_incentive(zoning: str) -> float:
    tiers = FAR_TIERS.get(normalize_zoning(zoning))
    return (tiers[1] - tiers[0]) if tiers else 0.0


# ──────────────────────────────────────────────────────────────────────────────
# 사업성 보정계수 (서울시 「정비사업 사업성 개선방안 세부기준」, 2024.09 2030 기본계획 개정)
#   재개발 보정계수 = 서울시 평균 공시지가(재개발) ÷ 해당 구역 평균 공시지가     (1.00 ~ 2.00)
#     · 구역 평균 = 구역 내 지목 '대' 필지의 면적가중평균
#     · 재개발은 지가만 본다 (재건축은 단지규모 α · 세대밀도 β 도 본다)
#     · 소수 셋째자리에서 올림 · 주거지역·준공업지역만 적용
#     · 기준시점 = 사업시행인가(최초 정비계획 주민공람) 직전 년도 공시지가
#   사용자가 지도에서 고른 필지가 곧 구역이라 그 필지들만으로 계산된다 — 지역 보정이 따로 필요 없다

#서울시 평균 공시지가(재개발, 원/㎡). 서울시가 매년 공고한다
#  (표준지 중 1·2종일반주거지역 '대' 의 면적가중평균). 2025년 값이 2026년 보정계수 산정 기준이다
#  (rules.seoul_avg_land_price_redev : 2023 5,861,129 / 2024 5,969,319 / 2025 6,302,982 — 매년 공고되면 추가)
SEOUL_AVG_LAND_PRICE_REDEV = {int(y): int(v) for y, v in policy.RULES["seoul_avg_land_price_redev"].items()}

#서울시 공동주택 평균 공시지가(재건축, 원/㎡) — 서울시가 매년 공고한다
#  (rules.seoul_avg_land_price_recon : 2023 7,192,258 세부기준 / 2024 7,274,646 서울특별시공고 제2025-9호 /
#   2025 8,043,979 서울특별시공고 제2026-529호). 2025년에 산정 방식이 바뀌어 +10.6% 뛰었다 → 연 상승률로 쓰지 않는다
SEOUL_AVG_LAND_PRICE_RECON = {int(y): int(v) for y, v in policy.RULES["seoul_avg_land_price_recon"].items()}

#재건축 보정계수 α(대지면적)·β(세대밀도)와 과밀단지 현황용적률 인정 (세부기준 p.3~5, rules.recon_*)
RECON_SITE_FACTOR = policy.RULES["recon_site_factor"]
RECON_DENSITY_FACTOR = policy.RULES["recon_density_factor"]
RECON_OVERDENSE_INCENTIVE = float(policy.RULES["recon_overdense_incentive"])
#허용 300% 이상 과밀단지의 준주거 종상향 체계 (세부기준 p.5~6, rules.recon_overdense_upzone)
RECON_OVERDENSE_UPZONE = policy.RULES["recon_overdense_upzone"]

#보정계수 범위 1.0 ~ 2.0 (rules.correction_min / correction_max — 노원구는 상한 3.0 을 건의했다, pending 참고)
CORRECTION_MIN = float(policy.RULES["correction_min"])
CORRECTION_MAX = float(policy.RULES["correction_max"])


@dataclass
class BusinessCorrection:
    factor: float           # 적용 보정계수 (1.00 ~ 2.00)
    raw: float | None       # 상하한을 씌우기 전 값
    zone_avg_price: float | None    # 구역 '대' 필지 면적가중평균 공시지가 (원/㎡, 기준년도로 환산)
    seoul_avg_price: float  # 서울시 평균 공시지가 (원/㎡)
    basis_year: int         # 기준 년도
    parcel_count: int       # 계산에 쓴 '대' 필지 수
    note: str = ""
    project_type: str = "재개발"
    land_factor: float | None = None    # 공시지가 보정계수 (소수 셋째자리 올림)
    site_factor: float = 0.0            # 재건축 α 대지면적 보정계수
    density_factor: float = 0.0         # 재건축 β 세대밀도 보정계수


#parcels : (지목, 면적㎡, 공시지가 원/㎡) 목록
#parcel_year : 필지 공시지가의 기준 년도 (V-World 최신값이라 보통 올해)
#  서울시 평균은 작년 값까지만 공고되므로, 구역 공시지가를 서울시 평균의 최근 1년 상승률로
#  되돌려 같은 해로 맞춘 뒤 나눈다 (2024 → 2025 서울시 평균 +5.59%)
def business_correction_factor(
    parcels: list[tuple[str, float, float]], parcel_year: int
) -> BusinessCorrection:
    basis_year, seoul, zone_avg_basis, lot_count = _land_price_basis(parcels, parcel_year, SEOUL_AVG_LAND_PRICE_REDEV)
    if zone_avg_basis is None:
        return BusinessCorrection(1.0, None, None, seoul, basis_year, 0,
                                  "구역에 지목 '대' 필지가 없어 보정계수를 1.0 으로 두었습니다.")

    raw = seoul / zone_avg_basis
    clamped = min(max(raw, CORRECTION_MIN), CORRECTION_MAX)
    factor = _ceil2(clamped)     # 소수 셋째자리에서 올림
    factor = min(factor, CORRECTION_MAX)
    return BusinessCorrection(factor, round(raw, 4), round(zone_avg_basis), seoul, basis_year, lot_count,
                              land_factor=_ceil2(raw))


#소수 셋째자리에서 올림 (세부기준 : 공시지가·대지면적·세대밀도 보정계수 각각 올림 후 합산)
def _ceil2(value: float) -> float:
    return math.ceil(round(value * 100, 6)) / 100


#서울시 평균(기준 년도)과 구역 '대' 필지 면적가중평균을 같은 해로 맞춘다
#  서울시 평균은 작년 값까지만 공고되므로, 구역 공시지가를 땅값 상승률(연율)로 되돌린다.
#  상승률은 재개발 계열(1·2종 대지 표준지)에서 구한다 — 재건축 계열은 2025년에 산정 방식이 바뀌어 땅값 변동이 아니다
def _land_price_basis(parcels, parcel_year: int, series: dict[int, int]):
    basis_year = max(y for y in series if y < parcel_year) if any(y < parcel_year for y in series) else max(series)
    seoul = float(series[basis_year])
    lots = [(area, price) for category, area, price in parcels if category == "대" and area > 0 and price > 0]
    if not lots:
        return basis_year, seoul, None, 0
    zone_avg = sum(a * p for a, p in lots) / sum(a for a, _ in lots)
    trend = SEOUL_AVG_LAND_PRICE_REDEV
    years = sorted(trend)
    growth = (
        (trend[years[-1]] / trend[years[-2]]) ** (1 / (years[-1] - years[-2]))
        if len(years) >= 2 else 1.0
    )
    gap = max(parcel_year - basis_year, 0)
    return basis_year, seoul, zone_avg / (growth ** gap), len(lots)


#재건축 사업성 보정계수 = 공시지가 보정계수 + α(대지면적) + β(세대밀도)   (1.00 ~ 2.00, 세부기준 p.3)
#  공시지가 보정계수 = 서울시 공동주택 평균 공시지가 ÷ 대상단지 평균 공시지가
#  α : 대지 2만㎡ 미만 단지 — 1만㎡ 이하 0.20, 1만~2만㎡ 직선보간, 2만㎡ 0.10
#  β : 가용 용적률 전체를 조합원 분양해도 세대당 평균 전용 85㎡ 공급이 안 되는 단지
#      — 세대당 공급 80㎡ 미만 0.20, 80~110㎡ 직선보간, 110㎡ 0.10
#      "가용 용적률" = (허용(보정 전) + 법적상한) ÷ 2 — 법적상한까지 남은 몫의 절반은 공공주택으로 내므로 (서울 정비조례 제30조① · 도정법 제54조④).
#      세부기준 원문에 정의는 없고 역산으로 확인했다 (2026-10-08) : 서울시 노원 57개 단지 β 시뮬레이션표는 3종 265 = (230 + 300) ÷ 2 일 때만
#      54개 단지가 모두 맞고 2종 (210 + 250) ÷ 2 = 230 도 맞는다. 노원구보 제2258호(2025.7.10) 상계주공5 "31,294.6㎡ × 284.57% / 840명"
#      의 284.57 = (상한 269.41 + 법적상한 299.73) ÷ 2. 보정 전 허용을 쓰면 보정계수가 다시 용적률을 바꾸는 순환도 없다
#      (예전에는 기본계획 상한(보정 전)으로 읽었다 — 3종 250)
#  셋 다 소수 셋째자리에서 올린 뒤 더한다
def reconstruction_correction_factor(
    parcels: list[tuple[str, float, float]],
    parcel_year: int,
    site_area_m2: float,
    households: int,
    available_far: float | None,
) -> BusinessCorrection:
    basis_year, seoul, zone_avg_basis, lot_count = _land_price_basis(parcels, parcel_year, SEOUL_AVG_LAND_PRICE_RECON)
    if zone_avg_basis is None:
        return BusinessCorrection(1.0, None, None, seoul, basis_year, 0,
                                  "단지에 지목 '대' 필지가 없어 보정계수를 1.0 으로 두었습니다.", project_type="재건축")

    raw_land = seoul / zone_avg_basis
    land = _ceil2(raw_land)

    a = RECON_SITE_FACTOR
    if site_area_m2 <= 0 or site_area_m2 >= a["min_at_m2"]:
        alpha = 0.0
    elif site_area_m2 <= a["full_at_or_below_m2"]:
        alpha = a["max"]
    else:
        t = (site_area_m2 - a["full_at_or_below_m2"]) / (a["min_at_m2"] - a["full_at_or_below_m2"])
        alpha = a["max"] + (a["min"] - a["max"]) * t

    b = RECON_DENSITY_FACTOR
    beta = 0.0
    if households > 0 and available_far and site_area_m2 > 0:
        supply_per_household = available_far / 100 * site_area_m2 / households
        if supply_per_household < b["full_below_supply_m2"]:
            beta = b["max"]
        elif supply_per_household < b["min_at_supply_m2"]:
            t = (supply_per_household - b["full_below_supply_m2"]) / (b["min_at_supply_m2"] - b["full_below_supply_m2"])
            beta = b["max"] + (b["min"] - b["max"]) * t

    alpha, beta = _ceil2(alpha) if alpha else 0.0, _ceil2(beta) if beta else 0.0
    raw = land + alpha + beta
    factor = min(max(raw, CORRECTION_MIN), CORRECTION_MAX)
    return BusinessCorrection(factor, round(raw, 4), round(zone_avg_basis), seoul, basis_year, lot_count,
                              project_type="재건축", land_factor=land, site_factor=alpha, density_factor=beta)


# ──────────────────────────────────────────────────────────────────────────────
# 종상향 (용도지역 상향)
#   정비계획에서 용도지역을 올리는 것 (1종 → 2종 → 3종 → 준주거). 대가는 공공기여(기부채납).
#   공공기여율은 서울시 「2030 기본계획」 재정비 표 (2024-08-22 보도자료 참고자료 1) — 1단계 15% → 10% 완화 포함
#   이 비율은 "이상" 이다(최소). 그 이상 내면 상한용적률 산식(far_plan)으로 용적률을 더 받는다
#   ※ 높이 제약 지역(고도·경관지구, 문화재·학교 주변, 구릉지)은 실제 추가 확보 용적률에 비례해 낸다 —
#     구역의 높이 제약을 모르므로 지금은 반영하지 않는다

#서울 정비사업의 주거지역 용도지역 사다리 (아래 → 위)
ZONING_LADDER = [
    "제1종전용주거지역",
    "제2종전용주거지역",
    "제1종일반주거지역",
    "제2종일반주거지역",
    "제3종일반주거지역",
    "준주거지역",
]

#종상향 최소 공공기여율 (대지면적 대비, (원래, 변경)) — rules.upzoning_contribution
#  1종→2종 10% · 1종→3종 20% · 1종→준주거 30% · 2종→3종 10% · 2종→준주거 20% · 3종→준주거 10%
#  제2종(7층) 행은 7층 지정을 알 수 없어 뺐다 (2종일반과 같은 값이다)
UPZONING_CONTRIBUTION = {
    (base, sel): float(v)
    for base, targets in policy.RULES["upzoning_contribution"].items()
    for sel, v in targets.items()
}

#전용주거지역에서 올리는 경우는 표에 없다 → 1종일반 행을 하한으로 쓴다 (전용은 1종일반보다 낮다)
UPZONING_FALLBACK_BASE = policy.RULES["upzoning_fallback_base"]


#선택 필지들의 원래 용도지역 중 "가장 평균되는" 용도지역.
#  사다리 단계를 면적으로 가중평균해 가장 가까운 단계로 반올림한다.
#  사다리 밖(녹지·상업·공업)은 빼고 센다. 하나도 없으면 None
def base_zoning(zoning_areas: list[tuple[str, float]]) -> str | None:
    ranked = [
        (ZONING_LADDER.index(normalize_zoning(z)), a)
        for z, a in zoning_areas
        if normalize_zoning(z) in ZONING_LADDER and a and a > 0
    ]
    if not ranked:
        return None
    mean = sum(r * a for r, a in ranked) / sum(a for _, a in ranked)
    return ZONING_LADDER[min(int(math.floor(mean + 0.5)), len(ZONING_LADDER) - 1)]


@dataclass
class Upzoning:
    base_zoning: str | None         # 필지 원래 용도지역의 면적가중 평균 단계
    selected_zoning: str | None     # 사용자가 고른 용도지역
    steps: int                      # 올린 단계 수 (0 이하면 종상향 아님)
    contribution_ratio: float       # 공공기여로 내놓는 대지 비율
    note: str = ""


def upzoning(base: str | None, selected: str | None) -> Upzoning:
    sel = normalize_zoning(selected or "")
    if not base or sel not in ZONING_LADDER:
        return Upzoning(base, selected, 0, 0.0)

    steps = ZONING_LADDER.index(sel) - ZONING_LADDER.index(base)
    if steps <= 0:
        return Upzoning(base, sel, steps, 0.0)

    ratio = UPZONING_CONTRIBUTION.get((base, sel))
    fallback = ratio is None
    if fallback:
        ratio = UPZONING_CONTRIBUTION.get((UPZONING_FALLBACK_BASE, sel), 0.0)

    note = f"{base} → {sel} 종상향 : 공공기여 최소 {ratio:.0%} (서울시 2030 기본계획)."
    if fallback:
        note += f" {base} 에서 올리는 비율은 서울시 표에 없어 1종일반 기준을 하한으로 썼습니다."
    return Upzoning(base, sel, steps, ratio, note)


# ──────────────────────────────────────────────────────────────────────────────
# 용적률 계획 : 4단 + 사업성 보정계수 + 종상향 + 상한용적률 공공기여
#   상한용적률 = 최종허용용적률 + 허용용적률(보정 전) × {1.3 × 가중치 × α토지 + (0.7 또는 1.0) × α건축물 + 0.7 × α현금}
#     곱하는 허용용적률은 기준용적률 완화·현황용적률·사업성 보정계수를 적용하지 않은 값이다
#     (서울시 「정비사업 사업성 개선방안 세부기준」 p.2 원문). 보정계수가 1 이면 예전 식 허용 × (1 + 1.3α) 와 같다.
#     검산 : 미미삼 정비계획(안) (노원구 공고 제2026-567호 p.8) 획지1 250 + 230 × 1.3 × 0.0671 = 270.05%,
#            획지3(준주거) 250 + 230 × 1.3 × 0.4092 = 372.36% — 보정 후 250 을 곱하면 271.8 / 383.0 으로 어긋난다
#     (서울시 2030 기본계획 재정비, 2024-08-22 보도자료 참고자료 1)
#     α = 공공시설 부지로 제공하는 면적 ÷ 제공한 후의 대지면적
#   이 모델은 공공기여를 모두 토지로 낸다고 보고 가중치 1 (구역 안 같은 용도지역 땅) 로 둔다.
#   검산 : 같은 산식 구조인 서울시 지구단위계획 기부채납 산식 개정 보도(이투데이 2023-01-02)의 예시
#     "3종 대지 5만㎡, 기부채납 10%(토지 3,000㎡ + 현금·공공시설 2,000㎡) → 기존 256%, 개정 259%" 를
#     230 × (1 + 1.3 × 3,000/47,000 + 0.7 × 2,000/47,000) = 255.9 / 계수 1.0 이면 258.9 로 재현한다
#     → 곱하는 값은 허용용적률, α 의 분모는 기부 후 대지, 가중치 1 로 읽는 것이 맞다
#   허용 → 상한은 이 공공기여로만 올라가고, 기부한 땅만큼 건축 대지가 준다 (용적률은 줄어든 대지에 곱한다)
#   ※ 2026-09-10 공고된 기본계획 변경안 : 상한을 넘는 기부채납도 법적상한 안에서 용적률로 인정한다.
#     확정 고시 전이라 꺼 두었다 (rules.excess_contribution_to_legal). 고시되면 policy_watch --apply 로 켠다
LAND_CONTRIBUTION_COEF = float(policy.RULES["land_contribution_coef"])
EXCESS_CONTRIBUTION_TO_LEGAL = bool(policy.RULES["excess_contribution_to_legal"])


#허용 → far 까지 올리는 데 필요한 토지 기부 비율 (원래 대지 대비)
#  ceiling 을 넘는 부분은 공공기여로 얻지 않으므로 거기서 멈춘다.
#  지금 규칙은 상한까지 (그 위 법적상한 구간은 제54조 임대). 2026 변경안이 켜지면 far_plan 이 법적상한을 넘겨준다
#  allowed = 최종허용(보정 후, 출발점) / allowed_base = 산식에 곱하는 허용(보정 전). 안 주면 같은 값
def land_contribution_for(far: float, allowed: float, ceiling: float, allowed_base: float | None = None) -> float:
    base = allowed_base or allowed
    target = min(far, ceiling)
    if allowed <= 0 or base <= 0 or target <= allowed:
        return 0.0
    alpha = (target - allowed) / (base * LAND_CONTRIBUTION_COEF)
    return alpha / (1 + alpha)


#토지 기부 비율 contribution(원래 대지 대비)으로 받는 용적률. 상한을 넘지 않는다
def far_for_contribution(contribution: float, allowed: float, ceiling: float, allowed_base: float | None = None) -> float:
    base = allowed_base or allowed
    if contribution <= 0:
        return allowed
    alpha = contribution / (1 - contribution)
    return min(allowed + base * LAND_CONTRIBUTION_COEF * alpha, ceiling)


@dataclass
class FarNode:
    value: float            # 용적률 (%) — 공공기여 후 남은 대지에 곱한다
    label: str              # 단계명 (같은 값이면 "·" 로 합친다)
    contribution: float     # 이 용적률에 필요한 토지 공공기여 (원래 대지 대비)


@dataclass
class FarPlan:
    nodes: list[FarNode]
    allowed: float          # 허용용적률 (보정계수 반영)
    ceiling: float          # 제54조 초과용적률의 기준점 (far_base). 보통 상한, 2026 변경안이 켜지면 법적상한
    legal: float            # 법적상한용적률
    min_contribution: float # 종상향 최소 공공기여율
    note: str = ""
    allowed_base: float = 0.0   # 상한 산식에 곱하는 허용용적률 (보정 전)
    overdense: bool = False     # 재건축 과밀단지 (현황용적률을 허용용적률로 인정)


#용도지역(선택값)과 기준 용도지역(필지 원래 용도지역의 평균 단계)으로 용적률 노드를 만든다
#  ① 4단 : 종상향이면 FAR_TIERS_UPZONED(없으면 UPZONED_BASE 원칙), 아니면 FAR_TIERS
#  ② 보정계수 : 허용 = 기준 + 인센티브량 × k, 상한도 같은 폭 (법적상한 불변)
#     (서울시 「정비사업 사업성 개선방안 세부기준」 예시 : 3종일반 보정계수 2.0 → 210/250/270/300)
#  ③ 공공기여 : 노드마다 산식으로 필요한 토지 기부 비율을 붙인다
#  ④ 종상향 최소 공공기여는 산식상 그만큼 용적률을 받으므로, 그보다 낮은 노드(기준·허용)는 "종상향 최소" 하나로 합친다
#  4단이 없는 용도지역(전용주거 등)은 (조례, 법적상한) 2단 — 인센티브량을 몰라 보정계수·산식을 쓸 수 없다
def far_plan(
    zoning: str | None,
    far_min: float,
    far_max: float,
    correction: float = 1.0,
    base_zoning: str | None = None,
    current_far: float | None = None,
) -> FarPlan:
    sel = normalize_zoning(zoning or "")
    up = upzoning(base_zoning, sel) if base_zoning else Upzoning(None, sel, 0, 0.0)
    min_c = up.contribution_ratio if up.steps > 0 else 0.0
    note = ""

    tiers = None
    if up.steps > 0:
        base = base_zoning if base_zoning in UPZONED_BASE else UPZONING_FALLBACK_BASE
        tiers = FAR_TIERS_UPZONED.get((base, sel))
        if tiers is None and sel in FAR_TIERS:
            tiers = UPZONED_BASE[base] + FAR_TIERS[sel][2:]
            note = (
                f"{base} → {sel} 용적률은 서울시 표에 없는 조합이라 표의 원칙"
                "(기준·허용은 원래 용도지역, 상한·법적상한은 변경 용도지역)으로 계산했습니다."
            )
        if tiers is not None and base != base_zoning:
            note = (note + " " if note else "") + f"{base_zoning} 에서 올리는 용적률은 서울시 표에 없어 1종일반 행으로 계산했습니다."
    if tiers is None:
        tiers = FAR_TIERS.get(sel)

    if tiers is None:
        lo, hi = float(far_min), float(far_max)
        nodes = [FarNode(lo, "상한·법적상한" if lo == hi else "상한", min_c)]
        if hi > lo:
            nodes.append(FarNode(hi, "법적상한", min_c))
        return FarPlan(nodes, lo, lo, hi, min_c, note, allowed_base=lo)

    base_far, allowed, ceiling, legal = (float(v) for v in tiers)
    k = min(max(float(correction), CORRECTION_MIN), CORRECTION_MAX)
    lift = (allowed - base_far) * (k - 1.0)
    allowed_k = min(allowed + lift, legal)

    #재건축 과밀단지 중 허용(현황 + 보정)이 3종 법적상한(300%) 이상이고 준주거로 종상향하면 (세부기준 p.5~6 체계도)
    #  기준 210 · 허용 = 현황 + 20%p × (k − 1) (최대 400) · 상한 최대 400 · 법적상한 = 허용 × 1.25 (최대 500)
    #  종상향 공공기여 = 10% × (법적상한 − 300) ÷ (500 − 300) — "실제 추가된 최대용적률에 비례" (원문 예시 최대 400% → 5%)
    #  실제 정비계획의 상한은 기부채납 양으로 정해진다 (체계도 352%, 이촌 강변·강서 361.7%) — 여기서는 노드로 끝값만 준다
    ou = RECON_OVERDENSE_UPZONE
    base_legal = float(FAR_TIERS[ou["base_zoning"]][3]) if ou["base_zoning"] in FAR_TIERS else None
    if (
        current_far is not None and base_legal is not None and up.steps > 0
        and base_zoning == ou["base_zoning"] and sel == ou["upzoned"]
        and current_far + RECON_OVERDENSE_INCENTIVE * (k - 1.0) >= base_legal
    ):
        upzone_legal = float(ou["legal_max"])
        allowed_k = min(current_far + RECON_OVERDENSE_INCENTIVE * (k - 1.0), float(ou["allowed_max"]))
        legal_k = min(allowed_k * float(ou["legal_ratio"]), upzone_legal)
        ceiling_k = min(float(ou["ceiling_max"]), legal_k)
        standard_ratio = UPZONING_CONTRIBUTION.get((ou["base_zoning"], ou["upzoned"]), min_c)
        min_c = standard_ratio * max(legal_k - base_legal, 0.0) / (upzone_legal - base_legal)
        note = (note + " " if note else "") + (
            f"현황용적률 {current_far:.0f}% 과밀단지를 준주거로 종상향해 현황을 허용용적률로 인정하고, "
            f"법적상한을 허용의 125%({legal_k:.0f}%)로 제한했습니다. 종상향 공공기여 {min_c:.1%} (서울시 세부기준)."
        )
        contribution_cap = legal_k if EXCESS_CONTRIBUTION_TO_LEGAL else ceiling_k
        floor_far = round(far_for_contribution(min_c, allowed_k, contribution_cap, allowed), 1)
        raw = [("종상향 최소", floor_far)] + [(n, v) for n, v in (("상한", ceiling_k), ("법적상한", legal_k)) if v > floor_far]
        merged: dict[float, list[str]] = {}
        for name, value in raw:
            merged.setdefault(round(value, 1), []).append(name)
        nodes = [
            FarNode(value, "·".join(names), max(land_contribution_for(value, allowed_k, contribution_cap, allowed), min_c))
            for value, names in sorted(merged.items())
        ]
        return FarPlan(nodes, allowed_k, contribution_cap, legal_k, min_c, note, allowed_base=allowed, overdense=True)

    #재건축 과밀단지 : 현황용적률이 기본계획 허용용적률(보정 전)을 넘으면 현황을 허용으로 인정하고,
    #  허용 총량 중 20%p 범위까지 보정계수로 올린다 (현황 270%·k 2.0 → 290%, 세부기준 p.4~5).
    #  재건축만 current_far 를 넘긴다. 허용이 300% 를 넘는 단지의 종상향·현황 125% 제한은 반영하지 않았다
    overdense = current_far is not None and current_far > allowed
    if overdense:
        allowed_k = min(max(allowed_k, current_far + RECON_OVERDENSE_INCENTIVE * (k - 1.0)), legal)
        note = (note + " " if note else "") + (
            f"현황용적률 {current_far:.0f}% 가 허용용적률 {allowed:.0f}% 보다 높은 과밀단지라 "
            f"현황용적률을 허용용적률로 인정했습니다 (허용 {allowed_k:.0f}%)."
        )
        if sel == ou["base_zoning"] and current_far + RECON_OVERDENSE_INCENTIVE * (k - 1.0) >= legal:
            note += f" 준주거로 종상향하면 허용을 현황까지, 법적상한을 그 125%까지 받을 수 있습니다 (서울시 세부기준)."
    ceiling_k = min(max(ceiling + lift, allowed_k), legal)

    #공공기여로 올라갈 수 있는 끝. 지금은 상한이고, 2026 변경안이 켜지면 법적상한이다.
    #  켜지면 법적상한까지 정비계획 용적률이 되므로 제54조 초과용적률(법적상한 − 정비계획 용적률)이 0 이 된다
    #  → far_base(제54조 기준점)도 같이 법적상한으로 옮긴다
    contribution_cap = legal if EXCESS_CONTRIBUTION_TO_LEGAL else ceiling_k

    raw = [("기준", base_far), ("허용", allowed_k), ("상한", ceiling_k), ("법적상한", legal)]
    if min_c > 0:
        floor_far = round(far_for_contribution(min_c, allowed_k, contribution_cap, allowed), 1)
        raw = [("종상향 최소", floor_far)] + [(n, v) for n, v in raw if n in ("상한", "법적상한") and v > floor_far]

    merged: dict[float, list[str]] = {}
    for name, value in raw:
        merged.setdefault(round(value, 1), []).append(name)
    nodes = [
        FarNode(value, "·".join(names), max(land_contribution_for(value, allowed_k, contribution_cap, allowed), min_c))
        for value, names in sorted(merged.items())
    ]
    return FarPlan(nodes, allowed_k, contribution_cap, legal, min_c, note, allowed_base=allowed, overdense=overdense)


# 용적률이 낮아 정비사업 대상이 되기 어려운 용도지역 (선택은 막지 않고 안내만 한다)
LOW_DENSITY_ZONING = ("보전녹지지역", "생산녹지지역", "자연녹지지역")

# 용도지역별 상가(비주거) 비율 상한
#   주거지역에는 비주거 '하한' 조문이 없어서 최소 0 이 성립한다.
#   상한은 용도지역이 높을수록 커진다 — 준주거는 상업 기능을 허용하는 지역이라 폭이 넓다.
#   ※ 상업지역은 서울시 조례 별표3 으로 비주거 30%(일부 20%, 심의 시 10%) '이상' 의무라
#     성격이 반대다. 재개발 대상이 아니므로 표에서 뺀다
#   2026-10-02 확정. 재개발 대단지 실측은 1.8~2.4% 였고 기본값 0.02 는 거기서 왔다
COMMERCIAL_RATIO_MAX = {
    "제1종전용주거지역": 0.03,
    "제2종전용주거지역": 0.03,
    "제1종일반주거지역": 0.05,
    "제2종일반주거지역": 0.10,
    "제3종일반주거지역": 0.10,
    "준주거지역":       0.30,
}

# 용도지역을 모를 때 쓰는 상한. 가장 흔한 2·3종 일반주거 기준
DEFAULT_COMMERCIAL_RATIO_MAX = 0.10


# 사용자가 고를 수 있는 용도지역 (프론트 버튼 목록)
#   재개발은 사실상 주거지역에서만 일어나므로 주거지역만 연다.
#   상업·공업·녹지는 조회값으로 들어올 수는 있어도 선택지로는 주지 않는다
#   (상업지역은 비주거 의무비율 30% 로 성격이 다른 사업이 된다)
SELECTABLE_ZONING = [
    "제1종전용주거지역",
    "제2종전용주거지역",
    "제1종일반주거지역",
    "제2종일반주거지역",
    "제3종일반주거지역",
    "준주거지역",
]

# 종전자산 합산에서 제외할 지목 (국공유지 성격)
EXCLUDED_LAND_CATEGORY = {"도로", "구거", "하천", "공원", "제방"}

# 시군구 코드(PNU 앞 5자리) → 이름
# 우선 노원구와 인접 자치구만. 범위가 넓어지면 행정표준코드 전체를 불러오는 방식으로 바꿀 것
SIGUNGU_NAME = {
    "11350": "노원구",
    "11305": "강북구",
    "11320": "도봉구",
    "11230": "동대문구",
    "11260": "중랑구",
    "11215": "광진구",
    "11110": "종로구",
    "11140": "중구",
    "11380": "은평구",
    "11410": "서대문구",
    "11440": "마포구",
    "11170": "용산구",
    "11200": "성동구",
    "11290": "성북구",
}


# V-World 응답의 용도지역 문자열을 FAR_TABLE 키와 맞춤 (공백/줄바꿈 제거)
def normalize_zoning(zoning: str) -> str:
    return "".join(zoning.split()) if zoning else ""


# PNU 앞 5자리 = 시군구 코드 (예: 1135010300100010000 → "11350")
def sigungu_code(pnu: str) -> str:
    return pnu[:5] if pnu and len(pnu) >= 5 else ""


# 구역의 시군구 이름. 선택 면적 중 가장 큰 면적이 속한 시군구를 고르며, 표에 없으면 None
def district(parcels: list[ParcelInfo]) -> str | None:
    area_by_code: dict[str, float] = {}
    for parcel in parcels:
        code = sigungu_code(parcel.pnu)
        if not code:
            continue
        area = parcel.area_m2 if parcel.area_m2 and parcel.area_m2 > 0 else 0.0
        area_by_code[code] = area_by_code.get(code, 0.0) + area

    if not area_by_code:
        return None

    #면적이 가장 큰 시군구를 대표로 사용 (면적을 모두 모르면 코드 순서로 결정됨)
    top_code = max(area_by_code, key=lambda c: area_by_code[c])
    return SIGUNGU_NAME.get(top_code)


# 필지 목록 → 구역 집계
def build_zone_summary(parcels: list[ParcelInfo]) -> ZoneSummary:
    if not parcels:
        raise ValueError("선택된 필지가 없습니다.")

    warnings = []

    site_area_m2 = 0.0      # 구역 면적 합계
    land_value_total = 0.0  # 종전자산 추정 기초 (만원)
    far_min_weighted = 0.0  # 면적 가중 기준 용적률
    far_max_weighted = 0.0  # 면적 가중 상한 용적률
    far_area_m2 = 0.0       # 용적률을 알 수 있는 필지 면적 합계
    area_by_zoning: dict[str, float] = {}   # 용도지역별 면적 (구성 안내용)
    low_density_m2 = 0.0    # 녹지지역 등 저밀도 용도지역 면적
    low_density_count = 0

    for parcel in parcels:
        # 면적이 없는 필지는 합산에서 제외 (토지특성 API 미조회 등)
        if parcel.area_m2 is None or parcel.area_m2 <= 0:
            warnings.append(f"면적이 없는 필지를 제외했습니다: {parcel.pnu}")
            continue

        site_area_m2 += parcel.area_m2

        # 종전자산 기초 : 도로·구거 등 국공유지는 조합원 자산이 아니므로 제외
        if parcel.land_category in EXCLUDED_LAND_CATEGORY:
            pass
        else:
            # 공시지가는 원/㎡ → 만원 환산
            land_value_total += parcel.area_m2 * parcel.land_price_per_m2 / 10_000

        # 용적률 : 용도지역별 값을 면적으로 가중평균
        zoning = normalize_zoning(parcel.zoning)
        area_by_zoning[zoning] = area_by_zoning.get(zoning, 0.0) + parcel.area_m2
        far_range = FAR_TABLE.get(zoning)
        if far_range is None:
            warnings.append(f"용적률 표에 없는 용도지역입니다: {parcel.zoning} ({parcel.pnu})")
            continue

        if zoning in LOW_DENSITY_ZONING:
            low_density_m2 += parcel.area_m2
            low_density_count += 1

        far_min_weighted += parcel.area_m2 * far_range[0]
        far_max_weighted += parcel.area_m2 * far_range[1]
        far_area_m2 += parcel.area_m2

    if site_area_m2 <= 0:
        raise ValueError("면적이 있는 필지가 하나도 없습니다.")

    # 용도지역을 하나도 못 읽으면 오류
    if far_area_m2 <= 0:
        raise ValueError("용도지역을 확인할 수 있는 필지가 없습니다.")

    #부동소수 오차방지 반올림
    far_min = round(far_min_weighted / far_area_m2, 2)
    far_max = round(far_max_weighted / far_area_m2, 2)

    #용도지역이 섞이면 면적 가중평균 사용, 용도지역 비율 표기
    if len(area_by_zoning) > 1:
        parts = []
        for zoning, area in sorted(area_by_zoning.items(), key=lambda kv: -kv[1]):
            share = area / site_area_m2 * 100
            #1% 미만은 0%로 보이지 않게 따로 표기한다
            parts.append(f"{zoning or '미확인'} {share:.0f}%" if share >= 1 else f"{zoning or '미확인'} 1%미만")
        warnings.append(
            f"용도지역 구성: {', '.join(parts)} — 면적 가중평균으로 용적률을 계산했습니다."
        )

    #녹지지역(50%)선택시 용적률을 많이 낮추나 막지 않고 경고만 함
    if low_density_count:
        warnings.append(
            f"이 중 녹지지역 {low_density_count}개 필지는 용적률이 50%라 평균을 끌어내립니다. "
            f"정비사업 대상이 아니라면 선택에서 빼세요."
        )

    #대표 시군구 : 공사비 등 예측 모듈에 넘길 지역
    region = district(parcels)
    codes = {sigungu_code(p.pnu) for p in parcels if sigungu_code(p.pnu)}
    if len(codes) > 1:
        warnings.append(f"여러 시군구에 걸친 구역입니다. 면적이 가장 큰 {region or '지역'} 기준으로 처리했습니다.")
    if region is None:
        warnings.append("PNU 로 시군구를 확인하지 못했습니다. 지역별 예측값 대신 전체 기준이 사용됩니다.")

    #대표 용도지역 : 면적이 가장 넓은 것. 상가 비율 상한을 정하는 데 쓴다
    #  한 구역에 여러 용도지역이 섞이면 가장 넓은 쪽 기준이 된다
    main_zoning = max(area_by_zoning, key=area_by_zoning.get) if area_by_zoning else None

    return ZoneSummary(
        zoning=main_zoning,
        site_area_m2=site_area_m2,
        far_min=far_min,
        far_max=far_max,
        land_value_total=land_value_total,
        pnus=[p.pnu for p in parcels],
        warnings=warnings,
        region=region,
    )
