# 재개발·재건축 임대주택 인수가격 — 의무 임대는 기본형건축비의 80%, 제54조 완화분은 표준건축비
#
# 정비사업으로 지은 임대주택은 시·도지사(또는 LH·SH 등)가 인수하고, 그 대금이 조합의 임대 인수수입이 된다.
#   ① 의무 임대주택 (재개발만)   : 기준 구간 공급면적 × base_rental_ratio
#     건물 = 기본형건축비(지상층 + 지하층)의 80% — 도시정비법 시행령 제68조②1 (대통령령 제35083호, 2025-03-18 시행)
#            · 서울시 도시정비조례 제41조①. 단가는 일반분양 공고일 직전에 고시된 기본형건축비다
#     부속토지 = 감정가 (기준시점 = 사업시행계획인가 고시일 → 종전자산 토지분과 같은 시점·방법)
#   ② 제54조 용적률 완화분 공공주택 : 완화 구간 공급면적 × uplift_rental_share
#     건물 = 공공건설임대주택 표준건축비 (지하층은 그 63%) — 도시정비법 제55조② (현행, 2021-04-13 개정 이후 그대로)
#     부속토지 = 기부채납(무상) → 토지 수입 0
#   (예전 메모의 "2024-07-31 시행령 개정으로 둘 다 기본형건축비 80%" 는 틀렸다. 2024-07-31 시행본은 표준건축비 그대로였고,
#    80% 전환은 2025-03-18 시행이며 의무 임대(제68조)만이다. 완화분을 기본형건축비에 잇는 제55조 개정안은
#    2026-09-30 현재 본회의 전이라 policy_rules.json pending 에 둔다)
#
# 기본형건축비 — 분양가상한제 건축비 (「공동주택 분양가격의 산정 등에 관한 규칙」 제7조, 국토교통부 고시)
#   표는 data/policy_rules.json 의 rules.rental_takeover 에 있다. 새 고시가 나오면 그 파일만 고친다
#   (정기 고시 매년 3월·9월 + 비정기. 지금 값은 고시 제2026-488호, 2026-09-15 — 63칸 원문 그대로)
#   표 읽는 법 (고시 표 머리 그대로)
#     · 구간은 "주거전용면적" 으로 고르고, 단가는 "주택공급면적"에 곱한다. 둘을 섞지 말 것
#     · 기본형건축비 = 지상층건축비 + 지하층건축비 (규칙 제7조②). 지하층건축비는 지하층면적에 곱하는 단일 단가다
#       (basement, 주거전용면적과 무관). 제68조는 "기본형건축비의 80%" 라고만 해 지하층도 80% 로 넣는다
#     · 단위는 천원/㎡. engine 은 만원 단위를 쓰므로 조회 함수가 ÷10 해서 돌려준다
#   고시 이후의 시점 보정은 건설공사비지수로 한다 (ProjectParams.rental_cost_multiplier, 라우터가 계산).
#     기본형건축비 자체가 자재비·노무비 변동을 반영해 다시 고시되는 값이기 때문이다.
#     출발점은 오늘이 아니라 고시 월(ANNOUNCED_YM)이다
#
# 표준건축비 — 국토교통부 고시 제2023-64호 (2023-02-01 전부개정, 직전 2016-06-08 전부개정, +9.8%)
#   표는 rules.standard_build_cost. 층수 구간 4개 × 전용 40·50·60㎡ 이하·60㎡ 초과, 단가는 주택공급면적에 곱한다
#   지하층은 지상층 표준건축비의 63% — 서울시 「정비사업 등 용적률 완화에 따라 건설되는 공공임대주택 매입업무 처리 기준」(2023.5)
#     (공공주택 특별법 시행규칙 별표7 의 "표준건축비의 100분의 63 을 더할 수 있다". LH 지침은 지하층을 빼지만 서울 인수자는 서울시·SH)
#   표준건축비는 공사비를 따라 다시 고시되는 값이 아니라 정책가격이다 (2016~2023 동결 뒤 +9.8%).
#     그래서 공사비지수가 아니라 직전 두 전부개정 사이 실측 인상률(STANDARD_ANNUAL_RATE)로 고시 월부터 민다
import re
from datetime import date

from AI.engine import policy

_RULE = policy.RULES["rental_takeover"]

#인수가격 = 기본형건축비 × 이 비율 (0.8)
TAKEOVER_RATIO = float(_RULE["ratio"])

#가산비 (기본형건축비 대비, 0.04) — 시행령 제68조②3 · 서울 조례 제41조② 인정 항목(구조형식·성능등급·보증수수료).
#  서울 정비사업 상한제 9개 단지 공시를 조례 규칙으로 다시 계산한 중앙값 (근거는 policy_rules.json notes)
SURCHARGE_RATIO = float(_RULE.get("surcharge", 0.0))

#지하층건축비 (천원/㎡, 지하층면적 기준 — 주거전용면적과 무관한 단일 단가)
BASEMENT_BUILD_COST_KRW_THOUSAND = float(_RULE["basement"])

#고시 정보. 화면·응답에 근거로 같이 내보낸다
NOTICE = str(_RULE["notice"])
ANNOUNCED = str(_RULE["announced"])

#시점 보정의 출발점 "YYYY-MM" (고시 월)
ANNOUNCED_YM = ANNOUNCED[:7]

#주거전용면적 구간 상한(㎡). None 은 마지막 "초과" 구간 (125㎡ 초과)
EXCLUSIVE_UPPERS_M2 = [None if u is None else float(u) for u in _RULE["exclusive_upper_m2"]]

#층수 구간 → 전용면적 구간별 지상층건축비(천원/㎡)
BASE_BUILD_COST_KRW_THOUSAND = {
    band: [float(v) for v in row] for band, row in _RULE["table"].items()
}

#노드 슬라이더에 쓰는 순서 (고시 표 순서). o──o──o──o──o──o──o──o──o
#  고시 원문은 "6∼10층 이하" 처럼 적는다. 슬라이더 칸이 좁아 "이하" 를 뺀 이름을 쓴다
FLOOR_BANDS = list(BASE_BUILD_COST_KRW_THOUSAND)

#기본값 : 16~25층.
#  국토부가 고시 때마다 대표값으로 발표하는 칸이 "16~25층·전용 60~85㎡" 다.
#  예전 표준건축비의 기본값(11~20층, "재개발 임대동은 중층으로 짓는 경우가 많다")과도 겹친다
DEFAULT_FLOOR_BAND = "16~25층"

#예전 표준건축비 구간 이름 → 새 구간.
#  프론트·백엔드 배포가 어긋나 옛 이름이 들어와도 계산이 멈추지 않게 한다.
#  두 옛 구간(11~20층 = 옛 기본값, 21층 이상) 모두 16~25층과 겹치므로 기본 구간으로 본다
LEGACY_FLOOR_BANDS = {"11~20층": DEFAULT_FLOOR_BAND, "21층 이상": DEFAULT_FLOOR_BAND}


#규칙 파일이 표 모양과 어긋나면 계산 도중이 아니라 import 할 때 바로 알린다
def _check_table() -> None:
    width = len(EXCLUSIVE_UPPERS_M2)
    for band, row in BASE_BUILD_COST_KRW_THOUSAND.items():
        if len(row) != width:
            raise ValueError(
                f"policy_rules.json rental_takeover.table[{band}] 칸 수({len(row)})가 "
                f"전용면적 구간 수({width})와 다릅니다"
            )
    if DEFAULT_FLOOR_BAND not in BASE_BUILD_COST_KRW_THOUSAND:
        raise ValueError(f"기본 층수 구간 {DEFAULT_FLOOR_BAND} 이 rental_takeover.table 에 없습니다")


_check_table()


#기본형건축비 (만원/㎡, 고시 시점)
#  floor_band          : FLOOR_BANDS 중 하나 (사용자가 노드 슬라이더로 고른다)
#  exclusive_area_m2   : 임대 1세대 주거전용면적. 전용면적 구간을 고르는 데만 쓴다
def base_build_cost_per_m2(floor_band: str, exclusive_area_m2: float) -> float:
    row = BASE_BUILD_COST_KRW_THOUSAND.get(LEGACY_FLOOR_BANDS.get(floor_band, floor_band))
    if row is None:
        raise ValueError(
            f"층수 구간이 올바르지 않습니다: {floor_band} (가능한 값: {', '.join(FLOOR_BANDS)})"
        )

    for upper, cost in zip(EXCLUSIVE_UPPERS_M2, row):
        if upper is None or exclusive_area_m2 <= upper:
            return cost / 10        # 천원/㎡ → 만원/㎡
    return row[-1] / 10


#의무 임대 건물(지상층) 인수가격 (만원/㎡ 주택공급면적, 고시 시점) = 지상층건축비 × (80% + 가산비 4%).
#  일반분양 공고 시점으로는 rental_cost_multiplier 로 민다. 제54조 완화분은 uplift_takeover_price_per_m2
def takeover_price_per_m2(floor_band: str, exclusive_area_m2: float) -> float:
    return base_build_cost_per_m2(floor_band, exclusive_area_m2) * (TAKEOVER_RATIO + SURCHARGE_RATIO)


#의무 임대 지하층 인수가격 (만원/㎡ 지하층면적, 고시 시점) = 지하층건축비 × (80% + 가산비 4%)
def takeover_basement_price_per_m2() -> float:
    return BASEMENT_BUILD_COST_KRW_THOUSAND / 10 * (TAKEOVER_RATIO + SURCHARGE_RATIO)


#── 제54조 용적률 완화분 ─────────────────────────────────────────────
_STD = policy.RULES["standard_build_cost"]

#완화분 단가 기준 : "표준건축비"(현행 법 제55조②) / "기본형건축비"(개정안 — pending 이 반영되면 바뀐다)
UPLIFT_BASIS = str(policy.RULES["uplift_takeover_basis"])
UPLIFT_RATIO = float(policy.RULES["uplift_takeover_ratio"])
if UPLIFT_BASIS not in ("표준건축비", "기본형건축비"):
    raise ValueError(f"policy_rules.json uplift_takeover_basis 가 올바르지 않습니다: {UPLIFT_BASIS}")

STANDARD_NOTICE = str(_STD["notice"])
STANDARD_ANNOUNCED = str(_STD["announced"])
STANDARD_ANNOUNCED_YM = STANDARD_ANNOUNCED[:7]
STANDARD_BASEMENT_RATIO = float(_STD["basement_ratio"])
STANDARD_EXCLUSIVE_UPPERS_M2 = [None if u is None else float(u) for u in _STD["exclusive_upper_m2"]]
STANDARD_FLOOR_UPPERS = [None if u is None else int(u) for u in _STD["floor_upper"]]
STANDARD_BUILD_COST_KRW_THOUSAND = {band: [float(v) for v in row] for band, row in _STD["table"].items()}
STANDARD_FLOOR_BANDS = list(STANDARD_BUILD_COST_KRW_THOUSAND)


#표준건축비 연 상승률 = 직전 두 전부개정 사이 실측 (2016-06-08 → 2023-02-01, +9.8% → 연 1.42%)
def _standard_annual_rate() -> float:
    start = date.fromisoformat(str(_STD["previous_announced"]))
    end = date.fromisoformat(STANDARD_ANNOUNCED)
    years = (end - start).days / 365.25
    return (1 + float(_STD["revision_increase"])) ** (1 / years) - 1


STANDARD_ANNUAL_RATE = _standard_annual_rate()


def _check_standard_table() -> None:
    if len(STANDARD_FLOOR_UPPERS) != len(STANDARD_FLOOR_BANDS):
        raise ValueError("policy_rules.json standard_build_cost.floor_upper 와 table 행 수가 다릅니다")
    for band, row in STANDARD_BUILD_COST_KRW_THOUSAND.items():
        if len(row) != len(STANDARD_EXCLUSIVE_UPPERS_M2):
            raise ValueError(f"policy_rules.json standard_build_cost.table[{band}] 칸 수가 전용면적 구간 수와 다릅니다")


_check_standard_table()


#기본형건축비 층수 구간(9개) → 표준건축비 층수 구간(4개).
#  임대동 층수는 기본형건축비 구간으로 고른다. 그 구간의 최고 층으로 표준건축비 구간을 고른다
#  ("16~25층" → 25층 → "21층 이상". 같은 칸의 11~20층 과는 1.7~1.8% 차이)
def standard_floor_band(floor_band: str) -> str:
    band = LEGACY_FLOOR_BANDS.get(floor_band, floor_band)
    if band not in BASE_BUILD_COST_KRW_THOUSAND:
        raise ValueError(f"층수 구간이 올바르지 않습니다: {floor_band} (가능한 값: {', '.join(FLOOR_BANDS)})")
    top = int(re.findall(r"\d+", band)[-1])
    for name, upper in zip(STANDARD_FLOOR_BANDS, STANDARD_FLOOR_UPPERS):
        if upper is None or top <= upper:
            return name
    return STANDARD_FLOOR_BANDS[-1]


#표준건축비 (만원/㎡ 주택공급면적, 고시 시점)
def standard_build_cost_per_m2(floor_band: str, exclusive_area_m2: float) -> float:
    row = STANDARD_BUILD_COST_KRW_THOUSAND[standard_floor_band(floor_band)]
    for upper, cost in zip(STANDARD_EXCLUSIVE_UPPERS_M2, row):
        if upper is None or exclusive_area_m2 <= upper:
            return cost / 10
    return row[-1] / 10


#제54조 완화분 건물 인수가격 (만원/㎡ 주택공급면적, 고시 시점)
def uplift_takeover_price_per_m2(floor_band: str, exclusive_area_m2: float) -> float:
    if UPLIFT_BASIS == "기본형건축비":
        return base_build_cost_per_m2(floor_band, exclusive_area_m2) * UPLIFT_RATIO
    return standard_build_cost_per_m2(floor_band, exclusive_area_m2) * UPLIFT_RATIO


#제54조 완화분 지하층 인수가격 (만원/㎡ 지하층면적, 고시 시점)
#  표준건축비 : 그 세대 지상층 표준건축비의 63% (서울시 매입기준) / 기본형건축비 : 지하층건축비 × 비율
def uplift_takeover_basement_price_per_m2(floor_band: str, exclusive_area_m2: float) -> float:
    if UPLIFT_BASIS == "기본형건축비":
        return BASEMENT_BUILD_COST_KRW_THOUSAND / 10 * UPLIFT_RATIO
    return standard_build_cost_per_m2(floor_band, exclusive_area_m2) * STANDARD_BASEMENT_RATIO * UPLIFT_RATIO


#완화분 단가의 고시 월 (시점 보정 출발점)과 근거 문구
UPLIFT_ANNOUNCED_YM = ANNOUNCED_YM if UPLIFT_BASIS == "기본형건축비" else STANDARD_ANNOUNCED_YM
UPLIFT_NOTICE = NOTICE if UPLIFT_BASIS == "기본형건축비" else STANDARD_NOTICE
