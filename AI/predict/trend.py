# 시계열 → 연평균 상승률 추정. 공사비·분양가·지가가 "같은 규칙"을 쓰게 한곳에 모은다.
#
# 왜 한곳에 모으나
#   사업기간 슬라이더(기본 13년)로 모든 값을 같은 시점까지 밀어야 비례율이 왜곡되지 않는다.
#   추정 창이 항목마다 다르면 복리 13년에서 분담금 방향이 뒤집힌다. 실제로 그런 일이 있었다.
#     공사비  최근 24개월 창 → 연 10.16% → 13년 3.5배 (쓸 수 없는 값)
#     공사비  10년 장기       → 연  5.09% → 13년 1.91배
#     분양가  10년            → 연  8.03%  /  5년 → 연 -1.37%  (부호가 바뀐다)
#
# 규칙
#   창    10년 고정
#   방법  로그선형회귀 (구간 내 모든 점 사용). CAGR 은 시작·끝 2점만 보므로 쓰지 않는다
#   대상  g_C(공사비) · g_S(분양가) · g_L(지가) 전부 동일

from dataclasses import dataclass, field
from math import exp, log

#추정 창 (년).
#  10년이면 부동산 1~2 사이클이 들어가지만, 자료를 늘려 보니 한쪽 국면에 쏠린다.
#    공사비  10년 5.04% / 20년 3.97%   (10년 창은 2021~22 자재 급등기 비중이 크다)
#    분양가  10년 8.07% / 20년 6.86%   (10년 창은 2016~2026 상승기만 잡는다)
#  20년이면 2008·2021 급등기를 둘 다 포함하고 2006~2015 정체기도 들어가
#  어느 국면에도 쏠리지 않는다. 적합도도 분양가 R² 0.68 → 0.84 로 올라간다.
#  사업기간 13년을 복리로 미는 값이라 안정성이 더 중요하다
WINDOW_YEARS = 20

#회귀에 필요한 최소 점 개수. 이보다 적으면 두 점 CAGR 로 물러나고 경고를 남긴다
MIN_POINTS = 6

#자료가 창의 몇 할을 덮어야 하는가. 공시지가처럼 연 1회 공표되는 자료도 통과해야 하므로
#점 밀도가 아니라 "첫 점~끝 점이 창을 덮는 비율"로 본다
MIN_COVERAGE = 0.8


@dataclass
class RateEstimate:
    annual_rate: float          # 연평균 상승률 (0.0509 = 연 5.09%)
    points: int                 # 회귀에 쓴 점 개수
    r_squared: float            # 적합도. 낮으면 추세가 뚜렷하지 않다는 뜻
    from_ym: str                # 창 시작
    to_ym: str                  # 창 끝
    method: str                 # "logfit" | "cagr"
    warnings: list[str] = field(default_factory=list)


#"YYYY-MM" 또는 "YYYY" → 개월 수
def months(ym: str) -> int:
    parts = str(ym).split("-")
    year = int(parts[0])
    month = int(parts[1]) if len(parts) > 1 else 6   # 연 단위 자료는 연중(6월)으로 본다
    return year * 12 + month


#months() 의 역함수. months() 가 "year*12 + month(1~12)" 라서 1 을 빼고 나눠야 한다
#  (예전 식 total//12 는 12월을 다음 해로 넘겼다 : 2026-12 → "2027-12". 표시 문자열에만 쓰여 계산엔 영향이 없었다)
def _ym(total: int) -> str:
    return f"{(total - 1) // 12}-{(total - 1) % 12 + 1:02d}"


#시계열에서 연평균 상승률을 뽑는다
#  series : {"YYYY-MM": 값} 또는 {"YYYY": 값}. 값은 0보다 커야 한다(로그를 쓴다)
#  window_years : 창 길이. 기본 10년
#  anchor_ym : 창의 끝. None 이면 자료의 마지막 시점
def estimate_annual_rate(
    series: dict[str, float],
    window_years: int = WINDOW_YEARS,
    anchor_ym: str | None = None,
) -> RateEstimate:
    points = sorted((months(k), float(v)) for k, v in series.items() if float(v) > 0)
    if len(points) < 2:
        raise ValueError(f"상승률을 추정하려면 점이 2개 이상 필요합니다: {len(points)}개")

    warnings: list[str] = []
    end = months(anchor_ym) if anchor_ym else points[-1][0]
    start = end - window_years * 12

    window = [(m, v) for m, v in points if start <= m <= end]

    #창 안에 자료가 모자라면 전체를 쓴다 (창을 좁히면 단기 변동이 장기 추세로 증폭된다)
    if len(window) < MIN_POINTS:
        warnings.append(
            f"{window_years}년 창에 자료가 {len(window)}개뿐이라 전체 구간({_ym(points[0][0])}~"
            f"{_ym(points[-1][0])})으로 추정했습니다."
        )
        window = points

    n = len(window)
    if n < MIN_POINTS:
        #두 점 CAGR 로 물러난다. 시작점 노이즈에 취약하므로 경고를 남긴다
        (m0, v0), (m1, v1) = window[0], window[-1]
        years = max((m1 - m0) / 12, 1 / 12)
        rate = (v1 / v0) ** (1 / years) - 1
        warnings.append(f"점이 {n}개뿐이라 양 끝 2점으로 계산했습니다. 시작점에 민감합니다.")
        return RateEstimate(rate, n, 0.0, _ym(m0), _ym(m1), "cagr", warnings)

    #로그선형회귀 : ln(v) = a + b·m  →  연율 = exp(12b) − 1
    xs = [m for m, _ in window]
    ys = [log(v) for _, v in window]
    mx = sum(xs) / n
    my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    if sxx == 0:
        raise ValueError("시점이 모두 같아 추세를 낼 수 없습니다.")
    b = sxy / sxx
    a = my - b * mx
    rate = exp(12 * b) - 1

    #결정계수
    ss_tot = sum((y - my) ** 2 for y in ys)
    ss_res = sum((y - (a + b * x)) ** 2 for x, y in zip(xs, ys))
    r2 = 1 - ss_res / ss_tot if ss_tot else 0.0

    if r2 < 0.5:
        warnings.append(f"적합도 R²={r2:.2f} 로 추세가 뚜렷하지 않습니다. 변동이 큰 구간입니다.")

    #자료가 창의 앞부분을 덮지 못하면 짧은 구간을 긴 추세로 쓰는 셈이 된다.
    #공사비 지수가 실제로 이 상태였다(6.3년 자료로 10년 추세 → 단기 급등이 증폭).
    coverage = (xs[-1] - xs[0]) / (window_years * 12)
    if coverage < MIN_COVERAGE:
        warnings.append(
            f"자료가 {window_years}년 창의 {coverage*100:.0f}%({_ym(xs[0])}~{_ym(xs[-1])})만 "
            f"덮습니다. 구간이 짧아 단기 변동이 장기 추세로 증폭될 수 있습니다."
        )

    return RateEstimate(rate, n, r2, _ym(xs[0]), _ym(xs[-1]), "logfit", warnings)


#값을 from_ym 에서 to_ym 으로 민다. 연율 복리
def escalate(value: float, from_ym: str, to_ym: str, annual_rate: float) -> float:
    years = (months(to_ym) - months(from_ym)) / 12
    return value * (1 + annual_rate) ** years


#지수 표가 있을 때의 시점 보정
#  표 구간 안에서는 실제 지수를 선형보간해서 쓰고(실측이 추정보다 낫다),
#  표 마지막 시점 이후만 연율로 복리 연장한다.
#장기 수렴 구간(년). 이 기간에 걸쳐 측정 연율이 장기 연율로 선형 수렴한다.
#  근거 : 부동산·기업가치 DCF 의 "명시적 예측기간" 관행(통상 5~10년). 그 뒤는 안정 성장률을 쓴다.
#  왜 필요한가 — 측정 창(20년)이 2006~2026 서울 부동산 급등기를 통째로 포함하는데,
#  그 연율(분양가 6.86%)을 13~18년 복리로 외삽하면 노원구 분양가가 평당 1억을 넘는다.
#  장기적으로 주택가격 상승률은 소득·물가 성장률에 수렴한다
CONVERGE_YEARS = 5.0


#미래로 외삽할 때의 누적 배수.
#  long_run_rate 가 없으면 측정 연율로 그냥 복리 (기존 동작).
#  있으면 CONVERGE_YEARS 에 걸쳐 측정 연율 → 장기 연율로 선형 수렴시킨다.
#    g(t) = g_단기 + (g_장기 − g_단기) × min(t / CONVERGE_YEARS, 1)
#  월 단위 중점으로 누적해 구간 경계에서 튀지 않게 한다
def extrapolate(months_ahead: float, annual_rate: float, long_run_rate: float | None = None) -> float:
    if months_ahead <= 0:
        return (1 + annual_rate) ** (months_ahead / 12)
    if long_run_rate is None or abs(long_run_rate - annual_rate) < 1e-12:
        return (1 + annual_rate) ** (months_ahead / 12)

    factor = 1.0
    whole = int(months_ahead)
    for m in range(whole):
        t = (m + 0.5) / 12
        g = annual_rate + (long_run_rate - annual_rate) * min(t / CONVERGE_YEARS, 1.0)
        factor *= (1 + g) ** (1 / 12)

    #남은 소수 개월
    rest = months_ahead - whole
    if rest > 0:
        t = (whole + rest / 2) / 12
        g = annual_rate + (long_run_rate - annual_rate) * min(t / CONVERGE_YEARS, 1.0)
        factor *= (1 + g) ** (rest / 12)

    return factor


def index_at(
    ym: str,
    index: dict[str, float],
    annual_rate: float | None = None,
    long_run_rate: float | None = None,
) -> float:
    key = str(ym)
    if key in index:
        return index[key]

    points = sorted((months(k), float(v)) for k, v in index.items())
    target = months(key)

    rate = annual_rate if annual_rate is not None else estimate_annual_rate(index).annual_rate

    #표보다 이전 : 연율로 거꾸로 되돌린다.
    #  첫 값을 그대로 돌려주면 2010년 계약을 표 시작연도(2020년) 물가로 치게 된다.
    #  그러면 2010·2016·2017년 사례가 전부 같은 배수로 보정되어 과거 사례가 과소평가된다.
    #  역산도 정확하진 않지만(실제보다 낮게 나온다) 첫 값 고정보다는 낫다.
    #  ※ 지수표를 과거까지 채우면 이 분기를 타지 않는다 — 그게 정답이다
    if target <= points[0][0]:
        m_first, v_first = points[0]
        return v_first / (1 + rate) ** ((m_first - target) / 12)

    for (m0, v0), (m1, v1) in zip(points, points[1:]):
        if m0 <= target <= m1:
            return v0 + (v1 - v0) * (target - m0) / (m1 - m0)

    #표 밖(이후) : 공통 규칙으로 뽑은 연율로 연장한다.
    #  long_run_rate 를 주면 장기 연율로 수렴시킨다 (extrapolate 참조)
    m_last, v_last = points[-1]
    return v_last * extrapolate(target - m_last, rate, long_run_rate)



#[start_ym, end_ym) 구간에 균등하게 지출될 때, base_ym 대비 평균 배수.
#  공사비 기성은 착공~준공에 걸쳐 나눠 지급되고, 도급계약의 물가변동 조정은 지급 시점 물가를 따른다.
#  그래서 "계약 시점 단가 × 이 배수" 가 실제로 지출되는 공사비가 된다 (확정 이후 증액).
#  excess_rate : 지수 위에 얹는 연 초과 상승률 — 계약단가가 투입원가보다 빨리 오르는 몫
#  월 단위 중점으로 평균해 구간 경계에서 튀지 않게 한다
def average_index_ratio(
    start_ym: str,
    end_ym: str,
    base_ym: str,
    index: dict[str, float],
    annual_rate: float | None = None,
    long_run_rate: float | None = None,
    excess_rate: float = 0.0,
) -> float:
    rate = annual_rate if annual_rate is not None else estimate_annual_rate(index).annual_rate
    base = index_at(base_ym, index, rate, long_run_rate)
    m_base = months(base_ym)
    m0, m1 = months(start_ym), months(end_ym)
    if m1 <= m0:
        m1 = m0 + 1

    total = 0.0
    for m in range(m0, m1):
        t = (m + 0.5 - m_base) / 12
        total += index_at(_ym(m), index, rate, long_run_rate) / base * (1 + excess_rate) ** t
    return total / (m1 - m0)
