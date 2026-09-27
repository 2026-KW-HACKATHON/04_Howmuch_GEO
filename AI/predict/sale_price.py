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

API_URL = "https://apis.data.go.kr/1613000/RTMSDataSvcAptTradeDev/getRTMSDataSvcAptTradeDev"

DATA_DIR = Path(__file__).parent / "data"
CASES_CSV = DATA_DIR / "sale_cases.csv"      # 인근 분양 사례
TRADES_CACHE = DATA_DIR / "trades_cache.json"  # 실거래 조회 결과 캐시
    
#전용면적 ÷ 공급면적. 아파트마다 다르지만 통상 0.72~0.78
DEFAULT_EXCLUSIVE_RATIO = 0.74

#시세 대비 분양가 비율 (사례가 하나도 없을 때만 쓰는 폴백)
#  서울원아이파크 실측은 1.38배였다. 단지 위상에 따라 0.9~1.4 로 널뛰므로 신뢰도가 낮다
DEFAULT_OFFER_TO_MARKET = 1.2

#신축으로 볼 준공 연도 기준 (분양가와 비교할 대상)
DEFAULT_MIN_BUILD_YEAR = 2018

#슬라이더 범위 폭
SLIDER_MARGIN = 0.15

#시점 보정 상한 : 월 ±0.5% (연 ±6.2%)
#  실거래 추세를 그대로 쓰면 월 1.4% 가 나오는데, 이를 몇 년씩 복리로 늘리면 값이 폭주한다
#  분양 사례를 먼 미래로 보정할 때 특히 위험해서 보수적으로 자른다
MAX_MONTHLY_RATE = 0.005

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
def _monthly_rate(trades: list[Trade], exclusive_ratio: float) -> tuple[float, str | None]:
    picked = [t for t in trades if t.deal_type == "중개거래"]
    if len({t.ym for t in picked}) < 4:
        return 0.0, "거래 월이 적어 시점 보정을 생략했습니다."

    xs = [_months(t.ym) for t in picked]
    ys = [t.price_per_exclusive_m2 * exclusive_ratio for t in picked]
    x_mean, y_mean = statistics.fmean(xs), statistics.fmean(ys)
    denom = sum((x - x_mean) ** 2 for x in xs)
    slope = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys)) / denom if denom else 0.0

    rate = slope / y_mean if y_mean else 0.0
    if abs(rate) > MAX_MONTHLY_RATE:
        capped = MAX_MONTHLY_RATE if rate > 0 else -MAX_MONTHLY_RATE
        return capped, f"실거래 추세가 월 {rate * 100:+.2f}% 로 과도해 월 {MAX_MONTHLY_RATE * 100:.1f}% 로 제한했습니다."
    return rate, None


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
