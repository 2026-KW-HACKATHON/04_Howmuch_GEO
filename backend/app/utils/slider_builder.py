from AI.engine.schema import ZoneSummary

#슬라이드 변수 초기 설정값
def build_sliders(zone: ZoneSummary) -> dict:
    return {
        "floor_area_ratio": {"value": zone.far_min, "min": zone.far_min, "max": zone.far_max},
        "member_price_ratio": {"value": 0.8, "min": 0.7, "max": 0.9},
        "other_cost_ratio": {"value": 0.35, "min": 0.25, "max": 0.45},
        "commercial_ratio": {"value": 0.03, "min": 0.0, "max": 0.2},
        "construction_cost_per_pyeong": {"value": 850, "min": 700, "max": 1000},
        "general_price_per_m2": {"value": 998.25, "min": 700, "max": 1300},
        "proportional_rate": {"value": 100, "min": 80, "max": 120, "fixed": True}
    }