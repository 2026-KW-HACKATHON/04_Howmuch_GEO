# 예측 모듈 묶음
#   공사비와 분양가는 반드시 같은 시점(target_ym)으로 예측해야 한다.
#   시점이 어긋나면 비례율이 크게 왜곡된다.
#   (성북맨션 검증: 같은 시점 141.9% vs 분양가만 미래·공사비는 현재 214.1%)
import os
from dataclasses import dataclass
from datetime import date

from AI.predict.construction_cost import CostPrediction, predict_cost_per_pyeong
from AI.predict.sale_price import SalePrediction, Trade, fetch_trades, predict_sale_price_per_m2

#분양가 추세를 뽑을 때 몇 개월치 실거래를 볼지
TRADE_MONTHS = 12


@dataclass
class Predictions:
    target_ym: str           # 두 예측의 공통 기준 시점
    cost: CostPrediction     # 평당 공사비 (만원/평)
    sale: SalePrediction     # 일반분양가 (만원/㎡, 공급면적 기준)

    @property
    def warnings(self) -> list[str]:
        return (
            [f"[공사비] {w}" for w in self.cost.warnings]
            + [f"[분양가] {w}" for w in self.sale.warnings]
        )


#현재 연월 "YYYY-MM"
def current_ym() -> str:
    today = date.today()
    return f"{today.year}-{today.month:02d}"


#target_ym 직전 TRADE_MONTHS 개월의 연월 목록
def _recent_yms(target_ym: str, months: int = TRADE_MONTHS) -> list[str]:
    year, month = (int(x) for x in target_ym.split("-"))
    end = year * 12 + month
    #미래 시점이면 오늘까지의 거래만 볼 수 있다
    year_now, month_now = (int(x) for x in current_ym().split("-"))
    end = min(end, year_now * 12 + month_now)
    return [f"{(end - i - 1) // 12}-{(end - i - 1) % 12 + 1:02d}" for i in reversed(range(months))]


#공사비와 분양가를 같은 시점으로 한 번에 예측한다
#   target_ym : 착공(또는 분양) 예상 연월. 없으면 현재 연월
#   region    : 시군구 이름 ("노원구"). 공사비 사례·분양 사례 필터에 쓰인다
#   lawd_cd   : 실거래가 조회용 시군구 코드 5자리 ("11350"). 없으면 실거래는 건너뛴다
def predict_all(
    target_ym: str | None = None,
    region: str | None = None,
    lawd_cd: str | None = None,
    trades: list[Trade] | None = None,
) -> Predictions:
    target_ym = target_ym or current_ym()

    #실거래는 분양 사례의 시점 보정률을 구하는 데 쓰인다. 키가 없으면 보정 없이 진행
    if trades is None and lawd_cd and os.getenv("MOLIT_API_KEY"):
        try:
            trades = fetch_trades(lawd_cd, _recent_yms(target_ym))
        except Exception:
            trades = []

    return Predictions(
        target_ym=target_ym,
        cost=predict_cost_per_pyeong(target_ym, region=region),
        sale=predict_sale_price_per_m2(target_ym, trades=trades or [], region=region),
    )
