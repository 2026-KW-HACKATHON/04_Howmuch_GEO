from AI.engine.rental_cost import DEFAULT_FLOOR_BAND, FLOOR_BANDS
from AI.engine.schema import ZoneSummary
from AI.engine.zone import COMMERCIAL_RATIO_MAX, DEFAULT_COMMERCIAL_RATIO_MAX, FarPlan, far_plan
from AI.predict.construction_cost import CostPrediction
from AI.predict.sale_price import SalePrediction

from app.config.engine_defaults import (
    PARKING_MARGIN_DEFAULT,
    PARKING_MARGIN_MAX,
    PARKING_MARGIN_MIN,
    COMPLETION_GAP_MIN,
    COMPLETION_GAP_YEARS,
    DEFAULT_COMPLETION_YEARS,
    DEFAULT_PROJECT_PERIOD_YEARS,
    MEMBER_COUNT_MAX_RATIO,
    MEMBER_COUNT_MIN_RATIO,
    MEMBER_PRICE_RATIO_MAX,
    MEMBER_PRICE_RATIO_MIN,
    OTHER_COST_RATIO_BY_TYPE,
    OTHER_COST_RATIO_DEFAULT,
    OTHER_COST_RATIO_MAX,
    OTHER_COST_RATIO_MIN,
    PROJECT_PERIOD_TICKS,
    PROJECT_PERIOD_TRACK,
)


#용적률 노드 슬라이더.
#  노드는 4단(기준/허용/상한/법적상한)이고, 사업성 보정계수만큼 허용·상한이 오른다.
#  같은 값은 한 노드로 합친다 (2종일반은 상한 = 법적상한 250 → "상한·법적상한").
#  종상향이면 최소 공공기여로 받는 용적률이 첫 노드("종상향 최소")가 된다 → zone.far_plan
#  기본값은 "허용" 이 들어간 노드, 없으면 첫 노드다
def _far_slider(plan: FarPlan) -> dict:
    nodes = [n.value for n in plan.nodes]
    default = next((n.value for n in plan.nodes if "허용" in n.label), nodes[0])
    return {
        "value": default,
        "options": nodes,
        "min": nodes[0],
        "max": nodes[-1],
        #프론트가 노드에 이름을 붙일 수 있게 단계명을 같이 준다 (options 와 같은 순서)
        "tiers": [n.label for n in plan.nodes],
        #노드마다 필요한 토지 공공기여 (원래 대지 대비). 프론트가 고른 노드의 값을
        #  /contribution 의 public_contribution_ratio 로 보낸다 — 산식은 서버에만 둔다
        "contributions": [round(n.contribution, 4) for n in plan.nodes],
        #종상향 최소 공공기여 (순부담). 토지가 아닌 공공기여 방식에서 하한으로 쓴다 → /contribution 의 min_contribution_ratio
        "min_contribution": round(plan.min_contribution, 4),
    }


#사업 기간 슬라이더 (손잡이 두 개)
#   10 ──o────────o──────── 30
#        ↑        ↑
#     고시일    최종 인가
#  안쪽을 움직이면 바깥이 간격을 유지한 채 따라온다(자동 조정).
#  바깥을 움직이면 간격이 gap 범위 안에서 바뀐다. 근거 수치는 engine_defaults 참조
def _period_slider() -> dict:
    track_min, track_max = PROJECT_PERIOD_TRACK
    return {
        "value": [DEFAULT_PROJECT_PERIOD_YEARS, DEFAULT_COMPLETION_YEARS],
        "min": track_min,
        "max": track_max,
        "step": 1,
        "range": True,
        "ticks": PROJECT_PERIOD_TICKS,
        #두 손잡이는 따로 움직이고, 사이는 최소 간격(서울 아파트 공사기간 중앙값 3.05년 → 3년)만 지킨다
        "gap": {"value": COMPLETION_GAP_YEARS, "min": COMPLETION_GAP_MIN, "max": track_max - track_min},
        "labels": ["분담금 고시일", "최종 인가"],
    }


#슬라이드 변수 초기 설정값
#  cost : 공사비 예측 결과 (AI/predict). 평당 공사비 슬라이더의 초기값·범위로 사용
#  household_count : 구역 세대수. 있으면 조합원 수 슬라이더를 만든다
#  sale : 분양가 예측 결과 (AI/predict). 일반분양가 슬라이더의 초기값·범위로 사용
def build_sliders(
    zone: ZoneSummary,
    cost: CostPrediction,
    household_count: int | None = None,
    project_type: str = "재개발",
    sale: SalePrediction | None = None,
    measured_member_count: int | None = None,
    far: FarPlan | None = None,
) -> dict:
    #용도지역별 상가 비율 상한. 구역 대표 용도지역을 모르면 2·3종 일반주거 기준을 쓴다
    commercial_max = COMMERCIAL_RATIO_MAX.get(zone.zoning or "", DEFAULT_COMMERCIAL_RATIO_MAX)

    sliders = {
        #용적률 : 서울시 2030 정비기본계획의 4단 체계를 노드 슬라이더로 둔다
        #    기준 ─── 허용 ─── 상한 ─── 법적상한
        #  중간값은 의미가 없다 — 정비계획이 네 단계 중 하나를 부여한다.
        #  기본값은 **허용용적률**(인센티브 적용 후, 공공기여 전)로 둔다.
        #    기준은 인센티브를 하나도 못 받은 경우, 법적상한은 심의 통과를 전제하므로
        #    둘 다 한쪽 끝이고, 허용이 통상 달성하는 중립적 출발점이다.
        #  4단 수치가 없는 용도지역은 2단(상한=조례, 법적상한)으로 축퇴한다 → zone.far_plan 참조.
        #  사업성 보정계수가 허용·상한을 올리고(3종 2.0 → 210/250/270/300), 노드마다 공공기여 비율이 붙는다.
        #  far 를 안 주면 보정계수·종상향 없이 만든다
        #  min/max 도 함께 내려보낸다 — 프론트가 노드 슬라이더를 못 그려도 범위 슬라이더로 동작하게
        "floor_area_ratio": _far_slider(far or far_plan(zone.zoning, zone.far_min, zone.far_max)),
        #조합원 분양가 비율 : 일반분양가 대비 배수. 조합이 관리처분계획에서 정한다
        #  기본은 자동(auto) — /contribution 이 관리처분 비례율 100% 가 되도록 역산하고, 그 값을 응답
        #  timeline.member_price_ratio 로 돌려준다. 그래서 여기서는 값을 정하지 않는다 (null).
        #  사용자가 손잡이를 움직이면 auto 가 풀리고 그 값을 보낸다 → 범위·근거는 engine_defaults
        "member_price_ratio": {"value": None, "min": MEMBER_PRICE_RATIO_MIN, "max": MEMBER_PRICE_RATIO_MAX, "auto": True},
        #기타사업비 비율 = (총사업비 − 공사비) ÷ 공사비. 서울 정비계획·관리처분 15건 중앙값 36.7% (사분위 32.6~44.5%) — engine_defaults
        #기타사업비 : 관리처분 단계 유형별 중앙값 (재개발 0.707 · 재건축 0.474) — engine_defaults 근거
        "other_cost_ratio": {
            "value": OTHER_COST_RATIO_BY_TYPE.get(project_type, OTHER_COST_RATIO_DEFAULT),
            "min": OTHER_COST_RATIO_MIN,
            "max": OTHER_COST_RATIO_MAX,
        },
        #주차 여유율 : 실제 ÷ 법정 주차대수. 법정 대수는 평형 구성에서 계산한다 (주택건설기준 제27조①)
        #  기본·최대는 강북권 신축 대단지 건축물대장 실측, 최소 1.0 은 법정 대수 그 자체 → engine_defaults
        "parking_margin": {"value": PARKING_MARGIN_DEFAULT, "min": PARKING_MARGIN_MIN, "max": PARKING_MARGIN_MAX},
        #상가 비율 : 지상 연면적 중 근린생활시설 몫
        #  기본 0.02 — 재개발 대단지 실측 1.8~2.4% 이고, 준공 4개 단지로 면적 체인을 검증했을 때
        #  0.02 에서 세대수 평균오차가 -0.5% 로 가장 작았다 (0 이면 +1.4%, 0.05 면 -3.6%)
        #  상한은 용도지역별로 다르다 (전용 0.03 / 1종 0.05 / 2·3종 0.10 / 준주거 0.30)
        "commercial_ratio": {
            "value": min(0.02, commercial_max),
            "min": 0.0,
            "max": commercial_max,
        },
        "construction_cost_per_pyeong": {
            "value": cost.cost_per_pyeong,
            "min": cost.slider_min,
            "max": cost.slider_max,
        },
        "general_price_per_m2": (
            {"value": sale.price_per_m2, "min": sale.slider_min, "max": sale.slider_max}
            if sale
            else {"value": 998.25, "min": 700, "max": 1300}
        ),
        #임대 인수수입 : 임대동 층수 구간을 고르면 기본형건축비 표의 행이 정해진다 (노드 슬라이더)
        #  고시 표의 아홉 구간(5층 이하 ~ 46~49층)만 선택할 수 있다. 중간값은 의미가 없다
        #  (국토교통부 고시 제2026-488호. 구간 목록은 policy_rules.json → rental_cost.FLOOR_BANDS)
        #  전용면적 구간은 임대 1세대 면적에서 자동으로 정해지므로 사용자는 층수만 고른다
        "rental_floor_band": {"value": DEFAULT_FLOOR_BAND, "options": FLOOR_BANDS},

        #사업 기간 : [분담금 고시일, 최종 인가] (오늘부터 몇 년 뒤). 항목마다 시점이 다르다
        #  종전자산 = 고시일 − 3.3 (사업시행인가) / 조합원분양가·공사비 도급 = 고시일
        #  일반분양 = 최종 인가 − 3.6 (착공) / 공사비 기성 = 착공 ~ 최종 인가 / 임대 인수 = 최종 인가
        "project_period_years": _period_slider(),
    }

    #비례율(proportional_rate)은 슬라이더가 아니다.
    #  다른 값을 조절하면 (종후자산 − 총사업비) ÷ 종전자산 으로 다시 계산된다
    #
    #감정평가 보정률(appraisal_ratio)도 슬라이더가 아니다.
    #  개인·구역 종전자산에 같은 배수가 들어가 분담금에서 약분되기 때문이다(수치 검증됨).
    #  바꿔도 화면의 비례율 표시만 움직이므로 조절 수단으로 두면 사용자를 오해시킨다.
    #  ENGINE_DEFAULTS 의 1.527(표준지 공시지가 현실화율 65.5% 의 역수)을 토지분 배수(λ)로만 쓴다.
    #  종전자산 토지분+건물분 분리가 들어가면서 보정률은 입력이 아니라 계산 결과(r_구역)가 되었다

    #조합원 수 : 소유자 명부는 공개 자료가 아니므로 세대수를 기준으로 범위를 만든다
    #  여기서는 분양 세대수를 아직 모르므로 세대수 기준 범위만 준다.
    #  실제 상한은 분양 세대수에 걸려 더 낮아질 수 있어서, /contribution 이
    #  calc.member_count_range 로 다시 계산한 값을 응답에 담는다 (용적률에 따라 바뀜)
    if household_count:
        max_ratio = MEMBER_COUNT_MAX_RATIO.get(project_type, 1.0)
        sliders["member_count"] = {
            "value": household_count,
            "min": int(household_count * MEMBER_COUNT_MIN_RATIO),
            "max": int(household_count * max_ratio),
        }

    #건축물대장으로 실측한 조합원 수가 있으면 그것을 기본값으로 쓴다.
    #  조합원 수 = Σ(집합건물 세대수) + Σ(단독주택·나대지 필지 수) — 전수 집계라 추정이 아니다.
    #  슬라이더 하나가 L2(추정 범위) → L1(실측) 으로 내려간다.
    #  조합원 수는 사업이익을 나누는 분모라 분담금에 직접 영향이 크다.
    #  범위는 남겨둔다 — 무허가건축물·나대지 지분 소유자처럼 대장에 안 잡히는 조합원이 있다
    if measured_member_count:
        existing = sliders.get("member_count")
        low = int(measured_member_count * MEMBER_COUNT_MIN_RATIO)
        high = int(measured_member_count * MEMBER_COUNT_MAX_RATIO.get(project_type, 1.0))
        if existing:
            #세대수 기준 범위와 실측값을 모두 담을 수 있게 넓힌다
            low = min(low, existing["min"])
            high = max(high, existing["max"])
        #기본값 = 최댓값 (전원 참여)
        high = max(high, measured_member_count)
        sliders["member_count"] = {
            "value": high,
            "min": max(1, low),
            "max": high,
            "measured": True,
        }

    #최후 폴백 — 세대수도 실측도 없으면 조합원 수 슬라이더가 아예 안 내려간다.
    #  그러면 프론트가 임시값(2명)을 쓰게 되고, 분모가 2 라 분담금이 터무니없이 나온다.
    #  실제로 그 경로가 열려 있었다 : 프론트가 household_count 를 보내지 않고(useMainPage),
    #  건축물대장이 전부 실패하면 measured 도 없다 (건축HUB 간헐 503).
    #  조합원 수의 확실한 하한은 필지 수다 — 1필지에 최소 1명은 있다.
    #  상한은 필지당 10명 (월계동 실측 485필지 → 2,779명 = 필지당 5.7명의 약 2배 여유)
    if "member_count" not in sliders:
        parcel_count = max(len(zone.pnus or []), 1)
        sliders["member_count"] = {
            "value": parcel_count,
            "min": parcel_count,
            "max": parcel_count * 10,
            "assumed": True,
        }

    return sliders