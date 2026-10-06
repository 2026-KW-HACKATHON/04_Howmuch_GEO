# 일반분양가 예측 (ROADMAP 5단계)
#   1순위: 인근 분양 사례(data/sale_cases.csv)를 시점 보정해 중앙값을 쓴다
#   2순위: 사례가 없으면 국토부 실거래가로 주변 신축 시세를 구하고 계수를 곱한다
#
# 시세에 계수를 곱하는 방식은 비교 단지에 크게 휘둘린다.
# 실제로 서울원아이파크(2024-11 분양)는 분양가가 당시 인근 신축 시세의 1.38배였다.
# 대단지·역세권 신규 분양과 기존 신축 아파트의 시세 격차 때문이다.
# 그래서 분양 사례가 있으면 그것을 우선한다.
#
# 실거래가는 전용면적 기준, 분양가는 공급면적 기준이라 환산이 필요하다.
import csv
import os
import statistics
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

#백엔드는 패키지 경로로, AI/predict 를 sys.path 에 넣고 단독 실행하는 경우도 있어 둘 다 받는다
try:
    from AI.predict import trend
except ImportError:
    import trend

API_URL = "https://apis.data.go.kr/1613000/RTMSDataSvcAptTradeDev/getRTMSDataSvcAptTradeDev"

DATA_DIR = Path(__file__).parent / "data"
CASES_CSV = DATA_DIR / "sale_cases.csv"      # 인근 분양 사례
INDEX_CSV = DATA_DIR / "sale_index.csv"      # 아파트 실거래가지수 (2020년 평균 = 100)
TRADES_CACHE = DATA_DIR / "trades_cache.json"  # 실거래 조회 결과 캐시
    
#전용면적 ÷ 공급면적. 아파트마다 다르지만 통상 0.72~0.78
DEFAULT_EXCLUSIVE_RATIO = 0.74

#시세 대비 분양가 비율 (사례가 하나도 없을 때만 쓰는 폴백)
#  2026-10-01 실측 : 분양 사례 9건의 "분양가 ÷ 당시 지역 신축 시세" 배수
#    중앙값 0.91 / 평균 1.01 / 범위 0.76~1.31
#    9건 중 6건이 1 미만이다 — 선분양 리스크 때문에 분양가가 시세보다 싸다.
#    서울원아이파크(1.26~1.31)는 광운대역세권 프리미엄으로 예외다.
#  이상치(서울원 3건)에 끌리지 않게 중앙값을 쓴다.
#  ※ 옛 값 1.2 는 "서울원 1.38배" 라는 폐기된 측정치에 기댄 것이었다
#    (기준이 달랐던 값. 같은 기준으로 재측정하면 1.26~1.31). 32% 과대였다
#  ※ 월계1동은 광운대역세권 영향권이라 실제로는 중앙값보다 높을 수 있다.
#    그 보정은 지역 사례(sale_cases.csv)가 할 일이고, 이 상수는 사례가 없을 때의 폴백이다
DEFAULT_OFFER_TO_MARKET = 0.91

#신축으로 볼 준공 연도 기준 (분양가와 비교할 대상)
DEFAULT_MIN_BUILD_YEAR = 2018

#슬라이더 범위 폭
SLIDER_MARGIN = 0.15

#시점 보정 상한 : 월 ±0.7% (연 ±8.7%)
#  실거래 추세를 그대로 쓰면 월 1.4%(연 18%)가 나오는데, 복리로 늘리면 값이 폭주한다.
#  그렇다고 너무 낮게 자르면 정상 추세까지 깎인다 — 월 0.5%(연 6.2%) 였을 때는
#  측정된 장기 추세(국토부 실거래 노원구 10년 창 연 8.03% = 월 0.645%)조차 매번 상한에 걸렸다.
#  그래서 장기 추세보다는 여유를 두고, 단기 급등은 막는 선으로 월 0.7% 를 쓴다
MAX_MONTHLY_RATE = 0.007

#이 개월 수를 넘겨 외삽하면 경고한다
LONG_HORIZON_MONTHS = 24

#같은 시군구 사례가 이 건수 미만이면 인접 지역 사례까지 합쳐 쓴다
#  한 단지만 반복해서 들어가면 그 단지 특성에 끌려가기 때문
MIN_REGION_CASES = 5


@dataclass
class Trade:
    ym: str                  # 거래 시점 "YYYY-MM"
    apt_name: str            # 단지명
    umd_nm: str              # 법정동
    build_year: int          # 준공 연도
    exclusive_area_m2: float # 전용면적
    amount_manwon: float     # 거래금액(만원)
    deal_type: str           # 중개거래 / 직거래

    #전용 ㎡당 가격(만원)
    @property
    def price_per_exclusive_m2(self) -> float:
        return self.amount_manwon / self.exclusive_area_m2


@dataclass
class SalePrediction:
    price_per_m2: float      # 예측 분양가 (공급면적 ㎡당, 만원)
    target_ym: str           # 분양 시점
    basis: str               # "분양사례" 또는 "실거래시세"
    market_price_per_m2: float  # 보정 후 시세 (공급면적 ㎡당). 사례 기반이면 0
    case_count: int          # 사용한 분양 사례 수
    trade_count: int         # 사용한 거래 건수
    apt_names: list[str]     # 사용한 단지
    slider_min: float
    slider_max: float
    warnings: list[str] = field(default_factory=list)


@dataclass
class SaleCase:
    ym: str              # 분양 시점
    name: str            # 단지명
    region: str          # 시군구
    price_per_m2: float  # 공급면적 ㎡당 분양가(만원)
    note: str = ""


#주석(#)과 빈 줄을 걸러내며 CSV 읽기
def load_cases(path: Path = CASES_CSV) -> list[SaleCase]:
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        lines = [ln for ln in f if ln.strip() and not ln.lstrip().startswith("#")]
    return [
        SaleCase(
            ym=row["ym"], name=row["name"], region=row["region"],
            price_per_m2=float(row["price_per_m2"]), note=row.get("note", ""),
        )
        for row in csv.DictReader(lines)
    ]


def _months(ym: str) -> int:
    year, month = ym.split("-")
    return int(year) * 12 + int(month)


#국토부 실거래가 API 호출. lawd_cd 는 시군구 코드 5자리 (노원구 11350)
def fetch_trades(lawd_cd: str, ym_list: list[str], service_key: str | None = None) -> list[Trade]:
    service_key = service_key or os.getenv("MOLIT_API_KEY")
    if not service_key:
        raise ValueError("MOLIT_API_KEY 가 없습니다. .env 를 확인하세요.")

    trades: list[Trade] = []

    for ym in ym_list:
        query = urllib.parse.urlencode({
            "serviceKey": service_key,
            "LAWD_CD": lawd_cd,
            "DEAL_YMD": ym.replace("-", ""),
            "numOfRows": "1000",
            "pageNo": "1",
        })
        with urllib.request.urlopen(f"{API_URL}?{query}", timeout=30) as response:
            root = ET.fromstring(response.read().decode())

        for item in root.iter("item"):
            row = {child.tag: (child.text or "").strip() for child in item}

            #해제된 거래는 제외 (cdealType 에 '해제' 가 들어온다)
            if row.get("cdealType"):
                continue

            try:
                trades.append(Trade(
                    ym=f"{row['dealYear']}-{int(row['dealMonth']):02d}",
                    apt_name=row.get("aptNm", ""),
                    umd_nm=row.get("umdNm", ""),
                    build_year=int(row.get("buildYear") or 0),
                    exclusive_area_m2=float(row["excluUseAr"]),
                    amount_manwon=float(row["dealAmount"].replace(",", "")),
                    deal_type=row.get("dealingGbn", ""),
                ))
            except (KeyError, ValueError):
                continue

    return trades


#실거래로 월 상승률을 구한다 (사례 시점 보정에도 쓰인다). 구하지 못하면 0
#
#  여기서 쓰는 창은 공사비·사업기간 보정과 다르다. 일부러 다르다.
#    이 함수      최근 실거래(기본 12개월) → 분양 사례를 "지금" 으로 당긴다 (단기, 지역 시세)
#    escalate()  sale_index.csv (20년 창)       → 지금을 "사업기간 뒤" 로 민다 (장기)
#  단기 보정에 10년 평균을 쓰면 최근 시세 변화를 못 잡고,
#  장기 보정에 12개월 추세를 쓰면 복리로 폭주한다 (공사비에서 실제로 겪었다 — 연 10.16%).
#
#  회귀는 trend.py 와 같은 로그선형회귀를 쓴다. 구한 비율을 복리로 적용하므로
#  단순 선형회귀 기울기를 평균으로 나눈 근사값보다 로그회귀가 맞다
def _monthly_rate(trades: list[Trade], exclusive_ratio: float) -> tuple[float, str | None]:
    picked = [t for t in trades if t.deal_type == "중개거래"]
    if len({t.ym for t in picked}) < 4:
        return 0.0, "거래 월이 적어 시점 보정을 생략했습니다."

    #월별 중앙값으로 묶는다. 한 달에 거래가 몰리면 그 달이 추세를 좌우하기 때문
    by_month: dict[str, list[float]] = {}
    for t in picked:
        by_month.setdefault(t.ym, []).append(t.price_per_exclusive_m2 * exclusive_ratio)
    series = {ym: statistics.median(v) for ym, v in by_month.items() if v}

    try:
        #창을 넉넉히 줘서 받은 거래 전체를 쓴다 (호출부가 이미 12개월로 잘라서 넘긴다)
        annual = trend.estimate_annual_rate(series, window_years=50).annual_rate
    except ValueError:
        return 0.0, "거래 월이 적어 시점 보정을 생략했습니다."

    rate = (1 + annual) ** (1 / 12) - 1      # 연율 → 월율
    if abs(rate) > MAX_MONTHLY_RATE:
        capped = MAX_MONTHLY_RATE if rate > 0 else -MAX_MONTHLY_RATE
        return capped, f"실거래 추세가 월 {rate * 100:+.2f}% 로 과도해 월 {MAX_MONTHLY_RATE * 100:.1f}% 로 제한했습니다."
    return rate, None


#실거래가지수 표. 건설공사비지수(cost_index.csv)와 같은 역할이다
def load_index(path: Path = INDEX_CSV) -> dict[str, float]:
    with open(path, encoding="utf-8") as f:
        lines = [ln for ln in f if ln.strip() and not ln.lstrip().startswith("#")]
    return {row["ym"]: float(row["index"]) for row in csv.DictReader(lines)}


#장기 분양가 상승률 (연율).
#  예전에는 측정값을 SALE_PRICE_ANNUAL_RATE 상수로 코드에 박아뒀는데,
#  그러면 지역·시점이 고정되고 갱신하려면 사람이 코드를 고쳐야 했다.
#  지수 파일을 두고 trend.py 가 매번 회귀하게 하면 데이터만 갈아끼우면 된다.
#
#  _monthly_rate 와 역할이 다르다 — 이쪽은 장기(사업기간 보정), 저쪽은 단기(사례 현재화)다
def annual_rate(index: dict[str, float] | None = None) -> float:
    return trend.estimate_annual_rate(index or load_index()).annual_rate


#지수로 값을 시점 이동한다. 사업기간 보정에 쓴다
def escalate(price: float, from_ym: str, to_ym: str, index: dict[str, float] | None = None) -> float:
    index = index or load_index()
    rate = trend.estimate_annual_rate(index).annual_rate
    return price * trend.index_at(to_ym, index, rate) / trend.index_at(from_ym, index, rate)


#분양가 예측. 분양 사례가 있으면 그것을 쓰고, 없으면 실거래 시세에 계수를 곱한다
def predict_sale_price_per_m2(
    target_ym: str,
    trades: list[Trade] | None = None,
    cases: list[SaleCase] | None = None,
    umd_nm: str | None = None,
    region: str | None = None,
    min_build_year: int = DEFAULT_MIN_BUILD_YEAR,
    exclusive_ratio: float = DEFAULT_EXCLUSIVE_RATIO,
    offer_to_market: float = DEFAULT_OFFER_TO_MARKET,
) -> SalePrediction:
    warnings: list[str] = []
    trades = trades if trades is not None else []
    cases = cases if cases is not None else load_cases()

    #시점 보정에 쓸 월 상승률 (실거래에서 구한다)
    monthly_rate, rate_note = _monthly_rate(trades, exclusive_ratio)
    if rate_note:
        warnings.append(rate_note)

    #1순위 : 분양 사례
    #지역 우선. 다만 사례가 MIN_REGION_CASES 건도 안 되면 인접 지역까지 합쳐 쓴다
    #  (월계동은 장위뉴타운과 붙어 있어 시세 흐름이 비슷하다)
    if region:
        same_region = [c for c in cases if c.region == region]
        if len(same_region) >= MIN_REGION_CASES:
            cases = same_region
        elif cases:
            warnings.append(f"{region} 분양 사례가 {len(same_region)}건뿐이라 인접 지역 사례를 함께 사용했습니다.")

    if cases:
        escalated = [
            c.price_per_m2 * (1 + monthly_rate) ** (_months(target_ym) - _months(c.ym))
            for c in cases
        ]
        predicted = statistics.median(escalated)

        if len(cases) < 3:
            warnings.append(f"분양 사례가 {len(cases)}건뿐이라 신뢰도가 낮습니다.")
        gap = _months(target_ym) - max(_months(c.ym) for c in cases)
        if gap > 0:
            warnings.append(f"분양 사례를 월 {monthly_rate * 100:+.2f}% 로 {target_ym} 까지 보정했습니다.")
            if gap > LONG_HORIZON_MONTHS:
                warnings.append(f"{gap}개월 차이를 보정한 값이라 오차가 큽니다. 슬라이더로 조정하세요.")

        return SalePrediction(
            price_per_m2=round(predicted, 1),
            target_ym=target_ym,
            basis="분양사례",
            market_price_per_m2=0.0,
            case_count=len(cases),
            trade_count=0,
            apt_names=sorted({c.name for c in cases}),
            slider_min=round(predicted * (1 - SLIDER_MARGIN), 1),
            slider_max=round(predicted * (1 + SLIDER_MARGIN), 1),
            warnings=warnings,
        )

    #2순위 : 실거래 시세 × 계수
    warnings.append("분양 사례가 없어 실거래 시세로 추정했습니다. 사례를 모으면 정확해집니다.")

    picked = [t for t in trades if t.deal_type == "중개거래"]
    new_builds = [t for t in picked if t.build_year >= min_build_year]
    if umd_nm:
        same_dong = [t for t in new_builds if t.umd_nm == umd_nm]
        if len(same_dong) >= 5:
            picked = same_dong
        elif new_builds:
            picked = new_builds
            warnings.append(f"{umd_nm} 신축 거래가 부족해 시군구 전체 신축 거래를 사용했습니다.")
        else:
            warnings.append(f"{min_build_year}년 이후 준공 거래가 없어 전체 거래를 사용했습니다.")
    elif new_builds:
        picked = new_builds

    if not picked:
        raise ValueError("분양 사례도 실거래 자료도 없습니다.")

    per_supply = [t.price_per_exclusive_m2 * exclusive_ratio for t in picked]
    xs = [_months(t.ym) for t in picked]
    x_mean, y_mean = statistics.fmean(xs), statistics.fmean(per_supply)
    market = y_mean * (1 + monthly_rate) ** (_months(target_ym) - x_mean)

    predicted = market * offer_to_market
    warnings.append(
        f"시세 대비 분양가 {offer_to_market:.2f}배 가정 (실측 사례는 1.38배였고 단지에 따라 편차가 큽니다)"
    )
    if len(picked) < 10:
        warnings.append(f"거래가 {len(picked)}건뿐이라 신뢰도가 낮습니다.")

    return SalePrediction(
        price_per_m2=round(predicted, 1),
        target_ym=target_ym,
        basis="실거래시세",
        market_price_per_m2=round(market, 1),
        case_count=0,
        trade_count=len(picked),
        apt_names=sorted({t.apt_name for t in picked}),
        slider_min=round(predicted * (1 - SLIDER_MARGIN), 1),
        slider_max=round(predicted * (1 + SLIDER_MARGIN), 1),
        warnings=warnings,
    )
