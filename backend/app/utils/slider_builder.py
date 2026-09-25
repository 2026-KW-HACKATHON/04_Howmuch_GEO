from AI.engine.schema import ZoneSummary
from AI.predict.construction_cost import CostPrediction

from app.config.engine_defaults import MEMBER_COUNT_MAX_RATIO, MEMBER_COUNT_MIN_RATIO


#슬라이드 변수 초기 설정값
#  cost : 공사비 예측 결과 (AI/predict). 평당 공사비 슬라이더의 초기값·범위로 사용
#  household_count : 구역 세대수. 있으면 조합원 수 슬라이더를 만든다
def build_sliders(
    zone: ZoneSummary,
    cost: CostPrediction,
    household_count: int | None = None,
    project_type: str = "재개발",
) -> dict:
    sliders = {
        "floor_area_ratio": {"value": zone.far_min, "min": zone.far_min, "max": zone.far_max},
        "member_price_ratio": {"value": 0.8, "min": 0.7, "max": 0.9},
        "other_cost_ratio": {"value": 0.35, "min": 0.25, "max": 0.45},
        "commercial_ratio": {"value": 0.03, "min": 0.0, "max": 0.2},
        "construction_cost_per_pyeong": {
            "value": cost.cost_per_pyeong,
            "min": cost.slider_min,
            "max": cost.slider_max,
        },
        "general_price_per_m2": {"value": 998.25, "min": 700, "max": 1300},
        "proportional_rate": {"value": 100, "min": 80, "max": 120, "fixed": True},
    }

    #조합원 수 : 소유자 명부는 공개 자료가 아니므로 세대수를 기준으로 범위를 만든다
    if household_count:
        max_ratio = MEMBER_COUNT_MAX_RATIO.get(project_type, 1.25)
        sliders["member_count"] = {
            "value": household_count,
            "min": int(household_count * MEMBER_COUNT_MIN_RATIO),
            "max": int(household_count * max_ratio),
        }

    return sliders
