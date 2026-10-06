from AI.engine.rental_cost import DEFAULT_FLOOR_BAND, FLOOR_BANDS
from AI.engine.schema import ZoneSummary
from AI.engine.zone import COMMERCIAL_RATIO_MAX, DEFAULT_COMMERCIAL_RATIO_MAX, far_nodes
from AI.predict.construction_cost import CostPrediction
from AI.predict.sale_price import SalePrediction

from app.config.engine_defaults import MEMBER_COUNT_MAX_RATIO, MEMBER_COUNT_MIN_RATIO


#용적률 노드 슬라이더.
#  노드가 4개면 기준/허용/상한/법적상한, 2개면 상한/법적상한이다.
#  기본값은 노드가 3개 이상일 때 두 번째(허용), 아니면 첫 번째다
def _far_slider(zone: ZoneSummary) -> dict:
    nodes = far_nodes(zone.zoning, zone.far_min, zone.far_max)
    default = nodes[1] if len(nodes) >= 3 else nodes[0]
    return {
        "value": default,
        "options": nodes,
        "min": nodes[0],
        "max": nodes[-1],
        #프론트가 노드에 이름을 붙일 수 있게 단계명을 같이 준다
        "tiers": (
            ["기준", "허용", "상한", "법적상한"][: len(nodes)]
            if len(nodes) >= 3
            else ["상한", "법적상한"][: len(nodes)]
        ),
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
        #  4단 수치가 없는 용도지역은 2단(상한=조례, 법적상한)으로 축퇴한다 → far_nodes 참조.
        #  min/max 도 함께 내려보낸다 — 프론트가 노드 슬라이더를 못 그려도 범위 슬라이더로 동작하게
        "floor_area_ratio": _far_slider(zone),
        #조합원 분양가 비율 : 일반분양가 대비 배수. 조합 총회 의결 사항
        #  0.75 ~ 0.95 (통상 0.8~0.9). 0.8 이 기본값
        "member_price_ratio": {"value": 0.8, "min": 0.75, "max": 0.95},
        "other_cost_ratio": {"value": 0.35, "min": 0.25, "max": 0.45},
        #세대당 주차대수 : 지하 연면적을 결정한다
        #  기본 1.2 = 장위 꿈의숲아이파크 실측 (주차 2,061대 ÷ 1,711세대)
        #  최대 2.0 = 하이엔드 재건축 여지
        #  최소 1.0 — 주택건설기준 제27조① 법정값은 전용면적 합계 기준이라
        #    평형 구성에 따라 0.766(59형만) ~ 1.370(114형만) 으로 움직인다.
        #    지금은 평형과 무관한 고정 슬라이더라 1.0 을 바닥으로 둔다 → 면적 기준 전환은 [6] 과제
        "parking_per_household": {"value": 1.2, "min": 1.0, "max": 2.0},
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
        #임대 인수수입 : 임대동 층수 구간을 고르면 표준건축비 표의 행이 정해진다 (노드 슬라이더)
        #  o────o────o────o 형태로 네 구간만 선택할 수 있다. 중간값은 의미가 없다
        #  전용면적 구간은 임대 1세대 면적에서 자동으로 정해지므로 사용자는 층수만 고른다
        "rental_floor_band": {"value": DEFAULT_FLOOR_BAND, "options": FLOOR_BANDS},

        #사업 기간 : 구역지정 → 관리처분인가(분담금 확정)까지 걸리는 햇수 (노드 슬라이더)
        #  서울시 도시정비사업 통계 주택정비형 재개발 164건에서 뽑았다
        #    하위 25% 10.9년 / 중앙값 13.4년 / 상위 75% 15.9년 / 노원구 실적 17~18년
        #  이 값이 공사비·분양가·종전자산을 모두 같은 시점으로 민다.
        #  (종전자산만 t−3.3년 — 평가 기준시점이 사업시행인가일이라 관리처분보다 앞선다)
        "project_period_years": {"value": 13, "options": [11, 13, 16, 18]},
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
        max_ratio = MEMBER_COUNT_MAX_RATIO.get(project_type, 1.25)
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
        high = int(measured_member_count * MEMBER_COUNT_MAX_RATIO.get(project_type, 1.25))
        if existing:
            #세대수 기준 범위와 실측값을 모두 담을 수 있게 넓힌다
            low = min(low, existing["min"])
            high = max(high, existing["max"])
        sliders["member_count"] = {
            "value": measured_member_count,
            "min": max(1, low),
            "max": max(high, measured_member_count),
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