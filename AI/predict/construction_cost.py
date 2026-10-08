# 정비사업 계약 사례를 건설공사비지수로 목표 시점까지 시점 보정 => 보정한 값들의 중앙값을 예측치로 사용
# 공개된 자료가 적기 때문에 "지수 보정 + 중앙값"이 안정적
# 결과는 ProjectParams.construction_cost_per_pyeong (만원/평, 평당 공사비)의 슬라이더 초기값.

import csv
from dataclasses import dataclass, field
from pathlib import Path
from statistics import median

#백엔드는 패키지 경로(AI.predict.construction_cost)로 부르고,
#  AI/predict 를 sys.path 에 넣고 단독 실행하는 경우도 있어 두 방식을 모두 받는다
try:
    from AI.predict import trend
except ImportError:      # AI/predict 가 sys.path 에 직접 들어간 경우
    import trend

# Dataset 불러오기
DATA_DIR = Path(__file__).parent / "data"
INDEX_CSV = DATA_DIR / "cost_index.csv"     # 건설공사비지수, 2026.5월 기준 137.67 (KOSIS 공표값)
CASES_CSV = DATA_DIR / "cost_cases.csv"     # 정비사업 계약 사례, {가격, 지역, 평당 가격} 벡터들의 행렬

#슬라이더 범위를 만들 때 쓰는 폭 (예측치 대비 ±)
SLIDER_MARGIN = 0.15

#오래된 계약의 가중치 반감기(년).
#  지수로 시점 보정을 해도 오래된 계약은 지금 수준에 못 미친다.
#  지수가 못 잡는 것들이 시간이 갈수록 쌓이기 때문이다 — 마감 사양 상승, 공법 변화,
#  주차대수·커뮤니티 기준 강화 같은 것들이다.
#  실제로 보정 후에도 2016~2017년 계약은 651~667만원인데 2023·2026년 실계약은 800·828만원이다.
#  그래서 중앙값을 쓰면 오래된 사례가 끌어내린다(7건 중앙값 666 vs 최근 실계약 800~828).
#  5년이면 지수로 설명되지 않는 차이가 절반만큼 쌓인다고 보고 가중치를 깎는다.
#  ※ 표본이 쌓이면 최근 사례만으로 충분해져 이 보정이 필요 없어진다
RECENCY_HALFLIFE_YEARS = 5.0

#지역 사례를 단독으로 쓰기 위한 최소 건수.
#  이보다 적으면 서울 전체로 폴백한다. 표본이 적으면 지역 특성이 아니라
#  그 몇 건의 계약 시점·단지 성격이 값을 좌우하기 때문이다
REGION_MIN_CASES = 10


@dataclass
class CostCase:
    ym: str                  # 도급계약 체결 시점 "YYYY-MM" (착공일이 아니다)
    name: str                # 구역/단지 이름
    region: str              # 시군구
    cost_per_pyeong: float   # 계약 당시 평당 공사비(만원). 총공사비 ÷ 연면적(평)
    project_type: str = ""   # 재개발 / 재건축. 지금은 필터에 쓰지 않고 기록만 한다
    note: str = ""           # 출처 메모


@dataclass
class CostPrediction:
    cost_per_pyeong: float   # 예측 평당 공사비(만원)
    target_ym: str           # 예측 시점
    index_used: float        # 목표 시점 지수
    case_count: int          # 사용한 사례 수
    slider_min: float        # 슬라이더 최솟값
    slider_max: float        # 슬라이더 최댓값
    warnings: list[str] = field(default_factory=list)


#"YYYY-MM" → 개월 수 (지수 보간용)
def _months(ym: str) -> int:
    year, month = ym.split("-")
    return int(year) * 12 + int(month)


#주석(#)과 빈 줄을 걸러내며 CSV 읽기
def _read_csv(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        lines = [ln for ln in f if ln.strip() and not ln.lstrip().startswith("#")]
    return list(csv.DictReader(lines))


def load_index(path: Path = INDEX_CSV) -> dict[str, float]:
    return {row["ym"]: float(row["index"]) for row in _read_csv(path)}


def load_cases(path: Path = CASES_CSV) -> list[CostCase]:
    return [
        CostCase(
            ym=row["ym"],
            name=row["name"],
            region=row["region"],
            cost_per_pyeong=float(row["cost_per_pyeong"]),
            project_type=row.get("project_type", ""),
            note=row.get("note", ""),
        )
        for row in _read_csv(path)
    ]


#해당 시점의 지수. 표 구간 안은 선형 보간, 표 밖은 trend.py 의 공통 규칙(10년 창)으로 연장
#  예전에는 "최근 24개월 상승률"로 연장했는데, 지수표에 점이 몇 개 없으면
#  4개월 변동이 연 10.16% 로 증폭되어 13년 뒤 공사비가 3.5배로 튀었다.
#  공사비·분양가·지가가 같은 규칙을 쓰도록 trend.py 한곳에 모았다
def index_at(ym: str, index: dict[str, float] | None = None) -> float:
    index = index or load_index()
    return trend.index_at(ym, index)


#계약 당시 공사비를 목표 시점 기준으로 보정
def escalate(cost: float, from_ym: str, to_ym: str, index: dict[str, float] | None = None) -> float:
    index = index or load_index()
    rate = trend.estimate_annual_rate(index).annual_rate
    return cost * trend.index_at(to_ym, index, rate) / trend.index_at(from_ym, index, rate)


#목표 시점의 평당 공사비 예측
def predict_cost_per_pyeong(
    target_ym: str,
    cases: list[CostCase] | None = None,
    region: str | None = None,
) -> CostPrediction:
    index = load_index()
    cases = cases if cases is not None else load_cases()
    warnings: list[str] = []

    #지역 우선순위 : 요청 지역 → 서울 전체 기준점
    #지역 필터 : 사례가 REGION_MIN_CASES 건 이상일 때만 그 지역만 쓴다.
    #  몇 건뿐이면 그 지역 특성이 아니라 "어쩌다 걸린 계약"이 값을 정해 버린다.
    #  실제로 노원구 4건은 전부 2010~2022년 계약이라 최근 시세보다 한참 낮게 나왔다
    #  (노원구만 623 vs 서울 전체 738, 최근 실계약 800~828).
    if region:
        filtered = [c for c in cases if c.region == region]
        if len(filtered) >= REGION_MIN_CASES:
            cases = filtered
        elif filtered:
            warnings.append(
                f"{region} 사례가 {len(filtered)}건뿐이라(기준 {REGION_MIN_CASES}건) "
                "서울 전체 사례로 계산했습니다. 지역 시세와 다를 수 있습니다."
            )
        else:
            warnings.append(f"{region} 사례가 없어 서울 전체 기준으로 계산했습니다.")

    if not cases:
        raise ValueError("공사비 사례가 하나도 없습니다. data/cost_cases.csv 를 확인하세요.")

    #상승률을 한 번만 구해 모든 사례에 같은 값을 쓴다 (사례마다 다른 창을 쓰면 안 된다)
    rate_est = trend.estimate_annual_rate(index)
    warnings.extend(f"건설공사비지수 : {w}" for w in rate_est.warnings)

    escalated = [
        c.cost_per_pyeong
        * trend.index_at(target_ym, index, rate_est.annual_rate)
        / trend.index_at(c.ym, index, rate_est.annual_rate)
        for c in cases
    ]

    #최근 계약에 더 무게를 준다 (가중 평균). 가중치는 계약이 오래될수록 반감기로 줄어든다
    latest = max(_months(c.ym) for c in cases)
    weights = [0.5 ** ((latest - _months(c.ym)) / 12 / RECENCY_HALFLIFE_YEARS) for c in cases]
    predicted = sum(v * w for v, w in zip(escalated, weights)) / sum(weights)

    #가중 평균이 사례 범위를 벗어나면 가중치 설정이 잘못된 것이다
    if not min(escalated) <= predicted <= max(escalated):
        warnings.append("가중 평균이 사례 범위를 벗어났습니다. 가중치 설정을 확인하세요.")
        predicted = median(escalated)

    if len(cases) < 5:
        warnings.append(f"사례가 {len(cases)}건뿐이라 신뢰도가 낮습니다. 사례를 더 모으세요.")

    last_ym = max(index, key=_months)
    if _months(target_ym) > _months(last_ym):
        warnings.append(
            f"지수 표의 마지막 시점({last_ym}) 이후라 연 {rate_est.annual_rate * 100:.2f}% 로 "
            "연장 추정했습니다."
        )

    #표보다 이전 계약이 섞여 있으면 역산 구간이라 오차가 커진다
    first_ym = min(index, key=_months)
    older = [c.ym for c in cases if _months(c.ym) < _months(first_ym)]
    if older:
        warnings.append(
            f"{len(older)}건이 지수 표 시작({first_ym})보다 이전 계약이라 상승률로 역산했습니다. "
            "지수 표를 과거까지 채우면 정확해집니다."
        )

    return CostPrediction(
        cost_per_pyeong=round(predicted, 1),
        target_ym=target_ym,
        index_used=round(index_at(target_ym, index), 2),
        case_count=len(cases),
        slider_min=round(predicted * (1 - SLIDER_MARGIN), 1),
        slider_max=round(predicted * (1 + SLIDER_MARGIN), 1),
        warnings=warnings,
    )



#계약단가가 건설공사비지수(투입원가)보다 빠르게 오르는 몫 — 확정 이후 "비물가" 증액
#  = 도급계약 사례의 로그선형 연율 − 같은 기간 지수의 로그선형 연율
#  ※ 기간을 반드시 맞춘다. 사례 연율을 지수의 20년 평균 연율과 비교하면, 사례 기간에만 있는
#    지수 급등(2021~22)이 초과분으로 잘못 잡힌다 (노원 사례 2016~2025 : 사례 6.76% vs 같은 기간 지수
#    5.33% → 초과 1.42%/년. 20년 평균 3.97% 와 비교하면 2.79%/년으로 두 배 부풀려진다 — 2026-10-07 정정)
#  지역 사례가 REGION_MIN_CASES 미만이면 서울 전체 사례로 계산한다 (예측과 같은 규칙)
#  음수면 0 으로 둔다 — 확정 이후 공사비가 계약보다 내려가는 일은 드물다
@dataclass
class ExcessRate:
    rate: float         # 적용 초과 연율 (0 이상)
    case_rate: float    # 사례 계약단가 연율
    index_rate: float   # 같은 기간 지수 연율
    case_count: int
    basis: str          # 지역명 또는 "서울 전체"
    span: str           # 사례 기간 "YYYY-MM~YYYY-MM"


def _loglinear_rate(points: list[tuple[float, float]]) -> float:
    #(연, 값) → 연율. 최소자승 기울기를 연율로 바꾼다
    import math
    n = len(points)
    xs = [x for x, _ in points]
    ys = [math.log(y) for _, y in points]
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx <= 0:
        return 0.0
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    return math.exp(slope) - 1


def contract_excess_rate(
    region: str | None = None,
    cases: list[CostCase] | None = None,
    index: dict[str, float] | None = None,
) -> ExcessRate:
    cases = cases if cases is not None else load_cases()
    index = index if index is not None else load_index()

    basis = "서울 전체"
    if region:
        local = [c for c in cases if c.region == region]
        if len(local) >= REGION_MIN_CASES:
            cases, basis = local, region

    def year(ym: str) -> float:
        y, m = ym.split("-")[:2]
        return int(y) + (int(m) - 1) / 12

    if len(cases) < 3:
        return ExcessRate(0.0, 0.0, 0.0, len(cases), basis, "")

    first = min(c.ym for c in cases)
    last = max(c.ym for c in cases)
    case_rate = _loglinear_rate([(year(c.ym), c.cost_per_pyeong) for c in cases])
    window = [(year(k), v) for k, v in index.items() if first <= k <= last and v > 0]
    index_rate = _loglinear_rate(window) if len(window) >= 3 else case_rate

    return ExcessRate(
        rate=max(case_rate - index_rate, 0.0),
        case_rate=case_rate,
        index_rate=index_rate,
        case_count=len(cases),
        basis=basis,
        span=f"{first}~{last}",
    )
