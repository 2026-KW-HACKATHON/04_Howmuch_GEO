# 정비사업 계약 사례를 건설공사비지수로 목표 시점까지 시점 보정 => 보정한 값들의 중앙값을 예측치로 사용
# 공개된 자료가 적기 때문에 "지수 보정 + 중앙값"이 안정적
# 결과는 ProjectParams.construction_cost_per_pyeong (만원/평, 평당 공사비)의 슬라이더 초기값.

import csv
from dataclasses import dataclass, field
from pathlib import Path
from statistics import median
from . import trend

# Dataset 불러오기
DATA_DIR = Path(__file__).parent / "data"
INDEX_CSV = DATA_DIR / "cost_index.csv"     # 건설공사비지수, 2026.5월 기준 137.67 (KOSIS 공표값)
CASES_CSV = DATA_DIR / "cost_cases.csv"     # 정비사업 계약 사례, {가격, 지역, 평당 가격} 벡터들의 행렬

#슬라이더 범위를 만들 때 쓰는 폭 (예측치 대비 ±)
SLIDER_MARGIN = 0.15


@dataclass
class CostCase:
    ym: str                  # 계약 시점 "YYYY-MM"
    name: str                # 구역/단지 이름
    region: str              # 시군구
    cost_per_pyeong: float   # 계약 당시 평당 공사비(만원)
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
    if region:
        filtered = [c for c in cases if c.region == region]
        if filtered:
            cases = filtered
        else:
            warnings.append(f"{region} 사례가 없어 서울 전체 기준으로 계산했습니다.")
            cases = [c for c in cases if c.region == "서울"] or cases

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
