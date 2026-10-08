from app.config.engine_defaults import (
    COMPLETION_GAP_MIN,
    COMPLETION_GAP_YEARS,
    CONSTRUCTION_YEARS,
    DEFAULT_COMPLETION_YEARS,
    DEFAULT_PROJECT_PERIOD_YEARS,
    ENGINE_DEFAULTS,
    ENGINE_DEFAULTS_FOR_PARAMS,
    LAND_PRICE_ANNUAL_RATE,
    MEMBER_COUNT_UNKNOWN_MIN_RATIO,
    MEMBER_PRICE_RATIO_MAX,
    MEMBER_PRICE_RATIO_MIN,
    MEMBER_PRICE_TARGET_RATE,
    APT_PRICE_REALIZATION_RATE,
    HOUSING_REALIZATION_RATES,
    RECON_BASE_RENTAL_RATIO,
    RECON_UPLIFT_RENTAL_SHARE,
    PRIOR_ASSET_LEAD_YEARS,
    UNIT_MIX,
)
from app.schemas.realestate.realestate_request import ZoneRequest, ContributionRequest
from app.schemas.realestate.realestate_response import ContributionResponse
from app.services.building_ledger_service import fetch_exclusive_total
from app.services.credit_service import consume_credit_token
from app.services.organization_service import get_active_organization
from app.database.database_connection import get_db
from sqlalchemy.orm import Session
from app.services.zone_service import get_cached_exclusive_total, set_cached_exclusive_total
from app.utils.slider_builder import build_sliders
from app.exceptions.exceptions_handler import BadRequestException, ServiceUnavailableException, UnauthorizedException
from AI.engine.calc import (
    MemberCountRange,
    calc_allocation,
    calc_area,
    calc_construction_cost,
    calc_contribution_all,
    calc_post_asset,
    estimate_prior_asset,
    calc_project,
    member_count_range,
    rental_supply_from_exclusive,
    solve_member_price_ratio,
    unit_mix_from_household_ratio,
    unit_options,
)
from AI.engine.prior_asset import BuildingSpec, ParcelValuation, aggregate_zone, estimate
from AI.engine.public_contribution import (
    CASH_MAX_SHARE,
    PRESETS as CONTRIBUTION_PRESETS,
    SITE_VALUE_WEIGHT,
    contribution_need,
    mixed_contribution,
    normalize_mix,
)
from AI.engine.rental_cost import (
    ANNOUNCED as RENTAL_ANNOUNCED,
    ANNOUNCED_YM as RENTAL_ANNOUNCED_YM,
    BASEMENT_BUILD_COST_KRW_THOUSAND,
    NOTICE as RENTAL_NOTICE,
    STANDARD_ANNUAL_RATE,
    SURCHARGE_RATIO as RENTAL_SURCHARGE_RATIO,
    TAKEOVER_RATIO as RENTAL_TAKEOVER_RATIO,
    UPLIFT_ANNOUNCED_YM,
    UPLIFT_BASIS,
    UPLIFT_NOTICE,
    UPLIFT_RATIO,
    base_build_cost_per_m2,
    takeover_price_per_m2,
    uplift_takeover_price_per_m2,
)
from AI.engine.schema import (
    PER_PYEONG_TO_PER_M2, ParcelInfo, ProjectType, UnitMix, OwnerInput, ProjectParams, UnitType,
)
from AI.engine.zone import SIGUNGU_NAME, build_zone_summary, sigungu_code
from AI.predict import trend
from AI.predict.construction_cost import contract_excess_rate, load_index, predict_cost_per_pyeong
from AI.predict.sale_price import escalate as escalate_sale, fetch_trades, predict_sale_price_per_m2
from dataclasses import asdict
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request, status
from typing import List, Optional
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import json
import logging
import math
import os
import requests
import time

#부동산 계산식 API 라우터 설정
router = APIRouter(
    prefix="/api/v1",
    tags=["Contribution Engine"]
)

#백엔드 Logger
logger = logging.getLogger(__name__)

#환경 변수 로드
load_dotenv()
VWORLD_API_KEY = os.getenv("VWORLD_API_KEY")
VWORLD_DOMAIN = os.getenv("VWORLD_DOMAIN")

#V-World 데이터 API 세션
VWORLD_SESSION = requests.Session()
VWORLD_SESSION.mount(
    "https://",
    HTTPAdapter(
        max_retries=Retry(
            total=4,
            backoff_factor=0.3,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=("GET",),
        )
    ),
)

#호출 간격(초). 쉬지 않고 던지면 서버가 연결을 끊어 재시도 대기가 붙고 오히려 느려진다
VWORLD_CALL_GAP = 0.05

#실거래 조회 기간(개월). 분양가 시점 보정에 쓰는 월 상승률을 여기서 구한다
TRADE_MONTHS = 12

#"YYYY-MM" 을 연 단위(소수 허용)로 이동시킨다.
#  사업기간(13년)과 종전자산 평가시점(13 − 3.3 = 9.7년)이 달라서 필요하다.
#  9.7년 = 116개월처럼 개월까지 반영해야 3.3년 차이가 사라지지 않는다
def _shift_ym(ym: str, years: float) -> str:
    months = int(ym[:4]) * 12 + (int(ym[5:7]) - 1) + round(years * 12)
    return f"{months // 12:04d}-{months % 12 + 1:02d}"


#사업 기간 슬라이더 값 → (분담금 고시일, 최종 인가) 년.
#  [고시일, 최종 인가] 가 기본이다. 숫자 하나면 예전 요청(고시일만)으로 보고 기본 간격을 더한다.
#  간격은 슬라이더와 같은 범위로 묶는다 — 프론트를 거치지 않은 요청도 같은 규칙을 따르게
def _parse_period(value) -> tuple[float, float]:
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        mgmt, complete = float(value[0]), float(value[1])
    elif value is not None and not isinstance(value, (list, tuple, dict)):
        mgmt = float(value)
        complete = mgmt + COMPLETION_GAP_YEARS
    else:
        mgmt, complete = float(DEFAULT_PROJECT_PERIOD_YEARS), float(DEFAULT_COMPLETION_YEARS)
    mgmt = max(mgmt, 0.0)
    #최종 인가는 고시일 + 최소 간격(공사기간 중앙값) 이상. 최대 제한은 없다 (슬라이더와 같은 규칙)
    complete = max(complete, mgmt + COMPLETION_GAP_MIN)
    return mgmt, complete


#구역의 시군구 (면적이 가장 큰 쪽). 확정 이후 증액의 지역 사례를 고르는 데 쓴다
def _region(valuations) -> str | None:
    area_by_code: dict[str, float] = {}
    for v in valuations or []:
        code = sigungu_code(v.pnu)
        if code:
            area_by_code[code] = area_by_code.get(code, 0.0) + v.land_area_m2
    if not area_by_code:
        return None
    return SIGUNGU_NAME.get(max(area_by_code, key=area_by_code.get))


#슬라이더 및 추가 변수들로 계산하는 API
@router.post(
    "/contribution",
    response_model = ContributionResponse,
    summary = "조합원 개인 분담금 및 사업성 계산")
async def get_contribution(req: ContributionRequest, request: Request, session: Session = Depends(get_db)):
    user_id = request.session.get("user_id")
    if user_id is None:
        raise UnauthorizedException("로그인이 필요합니다.")

    try:
        sliders = dict(req.sliders)

        #감정평가 보정률은 ProjectParams 의 필드가 아니라 종전자산 환산에만 쓴다.
        #슬라이더에서 뺐으므로 평소에는 ENGINE_DEFAULTS 의 고정값(1.527)이 쓰인다
        appraisal_ratio = sliders.pop("appraisal_ratio", ENGINE_DEFAULTS["appraisal_ratio"])

        #예전 요청의 세대당 주차대수는 여유율로 바꿀 수 없다 (법정 대수가 평형마다 달라서) → 버리고 기본 여유율
        if "parking_per_household" in sliders:
            sliders.pop("parking_per_household")
            sliders.setdefault("parking_margin", ENGINE_DEFAULTS["parking_margin"])

        #조합원분양가 비율 : 값이 없거나 null 이면 자동이다 — 관리처분 확정 단계 비례율이
        #  MEMBER_PRICE_TARGET_RATE(100%)가 되도록 아래 단계 계산 직전에 역산한다.
        #  숫자를 보내면(사용자가 슬라이더를 움직였다) 그 값을 그대로 쓴다
        member_price_auto = sliders.get("member_price_ratio") is None
        if member_price_auto:
            #역산 전 임시값. ProjectParams 를 만들려면 숫자가 필요하다 (결과에는 쓰이지 않는다)
            sliders["member_price_ratio"] = MEMBER_PRICE_RATIO_MAX

        #사업 유형 : /zone 이 판정한 값 (아파트 단지만 고르면 재건축). 재건축 단지 정보가 없으면 종전자산은 필지 기준으로 남는다
        project_type = (
            ProjectType.RECONSTRUCTION if req.project_type == ProjectType.RECONSTRUCTION.value else ProjectType.REDEVELOPMENT
        )
        recon = req.reconstruction if project_type == ProjectType.RECONSTRUCTION else None

        #사업 기간 : [분담금 고시일, 최종 인가] (오늘부터 몇 년 뒤). ProjectParams 의 필드가 아니라
        #  항목마다 다른 시점을 정하는 데 쓴다
        mgmt_years, complete_years = _parse_period(sliders.pop("project_period_years", None))

        #항목별 시점 (오늘부터 년)
        #  종전자산 평가    = 사업시행인가 = 고시일 − 3.3 (도시정비법 : 사업시행계획인가 고시일 기준 평가)
        #  조합원분양가     = 고시일. 관리처분계획에서 명목으로 확정되어 이후 오르지 않는다
        #  공사비 도급단가  = 고시일 무렵 확정. 착공~준공 기성 때 물가변동·증액이 붙는다
        #  일반분양가       = 착공 = 최종 인가 − 공사기간 3.05 (일반분양은 착공 무렵 한다)
        #  의무 임대 건물   = 일반분양 공고 시점 (시행령 제68조②1 · 서울시 조례 제41조① : 일반분양 공고일 직전에 고시된
        #                     기본형건축비의 80%. 고시 월에서 이 시점까지 공사비지수로 민 값)
        #  완화분 임대 건물 = 최종 인가 (준공 때 시·도지사가 인수. 표준건축비를 고시 월에서 이 시점까지 개정 실측 인상률로 민 값)
        #  의무 임대 부속토지 = 사업시행인가 시점 감정가라 종전자산과 같은 시점
        now_ym = datetime.now().strftime("%Y-%m")
        start_years = max(complete_years - CONSTRUCTION_YEARS, mgmt_years)
        mgmt_ym = _shift_ym(now_ym, mgmt_years)
        start_ym = _shift_ym(now_ym, start_years)
        complete_ym = _shift_ym(now_ym, complete_years)

        #슬라이더에 보이는 공사비·분양가는 "오늘 기준" 값이다.
        #  사용자가 아는 금액을 조절하게 두고, 계산만 각 시점으로 민다.
        #  공사비는 건설공사비지수로, 분양가는 실거래가지수로 보정한다 (둘 다 trend.py 회귀)
        base_cost_per_pyeong = sliders.get("construction_cost_per_pyeong", 0.0)
        base_sale_per_m2 = sliders["general_price_per_m2"]
        cost_index = load_index()
        cost_rate = trend.estimate_annual_rate(cost_index).annual_rate
        cost_now = trend.index_at(now_ym, cost_index, cost_rate)

        def cost_at(ym: str) -> float:
            return base_cost_per_pyeong * trend.index_at(ym, cost_index, cost_rate) / cost_now

        #임대 건물 인수가격 시점 보정 배수 : 기본형건축비 고시 월 → 인수 시점 (건설공사비지수 비).
        #  기본형건축비는 자재비·노무비 변동을 반영해 매년 3·9월(+비정기) 다시 고시되는 값이라
        #  공사비지수가 그 사이의 재고시를 대신한다. 출발점은 오늘이 아니라 고시 월이다
        #  (예전에는 2023년 고시 표준건축비를 오늘부터 연 1.34% 로 밀어 출발점이 어긋나 있었다)
        rental_index_announced = trend.index_at(RENTAL_ANNOUNCED_YM, cost_index, cost_rate)

        def rental_multiplier(ym: str) -> float:
            return trend.index_at(ym, cost_index, cost_rate) / rental_index_announced

        #제54조 완화분 건물 인수가격 시점 보정 배수 : 표준건축비 고시 월 → 인수 시점.
        #  표준건축비는 공사비를 따라 다시 고시되는 값이 아니라 정책가격(2016~2023 동결 뒤 +9.8%)이라
        #  직전 두 전부개정 사이 실측 인상률(연 1.42%)로 민다. 제55조 개정으로 기본형건축비에 이어지면 공사비지수로
        uplift_index_announced = trend.index_at(UPLIFT_ANNOUNCED_YM, cost_index, cost_rate)

        def uplift_multiplier(ym: str) -> float:
            if UPLIFT_BASIS == "기본형건축비":
                return trend.index_at(ym, cost_index, cost_rate) / uplift_index_announced
            months = (int(ym[:4]) * 12 + int(ym[5:7])) - (int(UPLIFT_ANNOUNCED_YM[:4]) * 12 + int(UPLIFT_ANNOUNCED_YM[5:7]))
            return (1 + STANDARD_ANNUAL_RATE) ** (months / 12)

        #공사비 도급단가 (고시일)
        cost_contract = cost_at(mgmt_ym)

        #확정 이후 증액 = 기성(착공~준공) 기간 평균 배수. 둘로 나눠 보여준다
        #  ① 물가변동 : 건설공사비지수. 도급계약의 물가변동 조정은 지급 시점 물가를 따른다
        #  ② 비물가 초과 : 계약단가가 지수보다 빨리 오르는 몫 (설계변경·특화·공기연장 등).
        #     도급계약 사례의 연율 − 같은 기간 지수 연율 (서울 13건 +0.76%/년, 2026-10-08)
        #  회귀 기반이라 과거 추세(고급화 등)가 그대로 이어진다고 본다 — 추세가 꺾이면 이 값을 보정한다
        excess = contract_excess_rate(_region(req.parcel_valuations))
        escalation_index = trend.average_index_ratio(start_ym, complete_ym, mgmt_ym, cost_index, cost_rate)
        escalation_total = trend.average_index_ratio(
            start_ym, complete_ym, mgmt_ym, cost_index, cost_rate, excess_rate=excess.rate
        )

        #분양가 : 고시일 값(조합원분양가의 기준)과 착공 값(일반분양)
        sale_mgmt = escalate_sale(base_sale_per_m2, now_ym, mgmt_ym)
        sale_start = escalate_sale(base_sale_per_m2, now_ym, start_ym)

        #종전자산도 미래 시점으로 민다.
        #  단 시점이 다르다 — 종전자산은 "사업시행계획인가 고시일" 기준으로 평가하고(도시정비법),
        #  그 날은 관리처분인가(고시일)보다 중앙값 3.3년 앞선다. 그래서 (고시일 − 3.3)년만 민다.
        #  이걸 빼먹으면 분모(종전자산)만 제자리인 채 분자(종후자산)가 커져 비례율이 폭증한다
        prior_years = max(mgmt_years - PRIOR_ASSET_LEAD_YEARS, 0.0)
        prior_growth = (1 + LAND_PRICE_ANNUAL_RATE) ** prior_years

        if not req.land_value_total and not req.parcel_valuations:
            raise BadRequestException("구역 공시지가 총액이 없습니다. 지도에서 필지를 선택한 뒤 다시 계산해 주세요.")

        #종전자산 = 토지분 + 건물분.
        #  단일 배수(공시지가 × 보정률)로 두면 개인·구역에 같은 값이 들어가 분담금에서
        #  약분된다 — 보정률을 아무리 정교하게 추정해도 분담금이 1원도 움직이지 않았다.
        #  건물분을 분리해야 "내 집이 구역 평균보다 덜 낡았나" 가 권리가액에 반영된다.
        #
        #  평가 기준시점은 사업시행계획인가 고시일 = 관리처분 − 3.3년 이다.
        #  그 시점에서는 건물이 (prior_years) 만큼 더 낡고(잔존율 ↓),
        #  재조달원가는 그만큼 오른다(공사비 ↑).
        #  상쇄 정도가 구조마다 달라(철근콘크리트 −4.6%, 잔가율 하한에 붙은 벽돌 +46%)
        #  구역 평균 한 배수로 밀 수 없어서 필지 단위로 다시 집계한다
        #
        #  ※ 재조달원가는 sliders 의 공사비를 그대로 쓰면 안 된다.
        #    공사비는 고시일(관리처분) 이후 시점으로 밀려 종전자산 평가시점보다 3.3년 이상 뒤다.
        #    공사비 연 3.97% 면 3.3년치가 13.7% 과대이고, 그만큼 건물분이 부풀어
        #    비례율이 과소 → 분담금이 과대해진다. 평가시점(prior_ym) 으로 다시 민다
        prior_ym = _shift_ym(now_ym, prior_years)
        replacement_cost_per_m2 = cost_at(prior_ym) * PER_PYEONG_TO_PER_M2
        zone_prior = None

        if req.parcel_valuations:
            valuations = [
                ParcelValuation(
                    pnu=v.pnu,
                    land_area_m2=v.land_area_m2,
                    #토지는 공시지가 상승률로 민다
                    land_price_per_m2=v.land_price_per_m2 * prior_growth,
                    structure=v.structure,
                    building_area_m2=v.building_area_m2,
                    #평가시점까지 더 낡는다
                    elapsed_years=v.elapsed_years + prior_years,
                    household_count=v.household_count,
                    has_building=v.has_building,
                    land_category=v.land_category,
                    cost_index=v.cost_index,
                    owner_type=v.owner_type,
                    #주택 공시가격 (그해 1월) — aggregate_zone 이 공시가격 ÷ 현실화율 × 땅값 상승률로 민다
                    housing_kind=v.housing_kind,
                    housing_price=v.housing_price,
                    housing_units=v.housing_units,
                )
                for v in req.parcel_valuations
            ]
            #주택 필지는 공시가격 ÷ 현실화율(공동 69% · 단독 53.6%)을 평가시점까지 땅값 상승률로 민다.
            #  재개발 구역 주택은 땅값이 대부분이라 토지와 같은 상승률을 쓴다 (재건축 아파트는 아래에서 아파트 지수로 따로 잡는다)
            zone_prior = aggregate_zone(
                valuations,
                land_multiplier=appraisal_ratio,
                replacement_cost_per_m2=replacement_cost_per_m2,
                housing_rates=HOUSING_REALIZATION_RATES,
                housing_multiplier=prior_growth,
            )
            total_prior_asset = zone_prior.total
        else:
            #필지 원자료가 없으면 예전 방식(토지분만). 건물분이 빠져 다시 약분된다
            total_prior_asset = req.land_value_total * appraisal_ratio * prior_growth

        #재건축 종전자산 = 공동주택가격 합계 ÷ 공동주택 현실화율(69%), 평가시점(사업시행인가)까지 아파트 가격지수로 민다.
        #  아파트는 호 단위로 감정평가한다 — 토지 공시지가 × λ + 원가법 건물로 잡으면 미미삼이 실거래의 0.36배로 나왔다.
        #  공시가격 기준월은 그해 1월 1일이다
        apt_growth = 1.0
        recon_prior = None
        if recon and float(recon.get("official_total") or 0) > 0:
            official_ym = f"{recon.get('official_year') or now_ym[:4]}-01"
            apt_growth = escalate_sale(1.0, official_ym, prior_ym)
            recon_prior = float(recon["official_total"]) / APT_PRICE_REALIZATION_RATE * apt_growth
            #상가 등 비주거 조합원 : 공동주택가격이 없다 → 토지 지분(연면적 비율) × 공시지가 × λ + 건물 원가법 (재개발 근생과 같다)
            #  평가시점(사업시행인가)으로 토지는 공시지가 상승률, 건물은 더 낡고 재조달원가는 그 시점 값
            shop = recon.get("commercial") or {}
            shop_prior = 0.0
            if shop.get("units"):
                shop_prior = estimate(
                    land_area_m2=float(shop.get("land_share_m2") or 0),
                    land_price_per_m2=float(shop.get("land_price_per_m2") or 0) * prior_growth,
                    land_multiplier=appraisal_ratio,
                    building=BuildingSpec(
                        shop.get("structure") or "",
                        float(shop.get("floor_area_m2") or 0),
                        float(shop.get("elapsed_years") or 0) + prior_years,
                        float(shop.get("cost_index") or 1.0),
                    ),
                    replacement_cost_per_m2=replacement_cost_per_m2,
                ).total
                recon_prior += shop_prior
            total_prior_asset = recon_prior

        #의무 임대 부속토지 감정가 (만원/㎡).
        #  감정 기준시점이 사업시행계획인가 고시일이라 종전자산 토지분과 같은 시점·방법이다 → 거기서 ㎡당 평균을 구한다
        #  ① 필지 원자료 있음 : 구역 토지분 ÷ 그 토지면적. 둘 다 국공유지를 뺀 값이다 (aggregate_zone 과 같은 기준).
        #     도로·구거는 1/3 로 감액된 채 평균에 들어가 순수 택지 감정가보다 조금 낮게 나온다
        #  ② 폴백(공시지가 총액만) : 종전자산(토지분만) ÷ 구역 면적. 국공유지를 가려낼 수 없어
        #     분자(공시지가 총액)와 분모(구역 면적)를 같은 범위 — 선택 필지 전체 — 로 맞춘다
        #  ※ 2026-10-08 : 지목 '대' 필지만으로 낸다 — 사유 도로·구거(1/3 감액)가 섞이면 순수 택지 감정가보다 낮아진다.
        #    주택 공시가격으로 종전을 잡은 필지도 토지 감정가(공시지가 × λ)는 여기에 넣는다. '대' 가 없으면 예전 방식
        if zone_prior is not None and zone_prior.dae_land_area_m2 > 0:
            rental_land_price_per_m2 = zone_prior.dae_land_total / zone_prior.dae_land_area_m2
        elif zone_prior is not None:
            rental_land_price_per_m2 = (
                zone_prior.land_total / zone_prior.land_area_m2 if zone_prior.land_area_m2 > 0 else 0.0
            )
        else:
            rental_land_price_per_m2 = total_prior_asset / req.site_area_m2 if req.site_area_m2 > 0 else 0.0

        #평형 구성 : 세부 설정에서 넘어온 값이 있으면 그걸 쓰고, 없으면 실측 기본값(59·84·114)
        #  입력은 세대수 비율이고 UnitMix.share 는 면적 몫이라 환산해서 넣는다
        if req.unit_mix:
            unit_mix_list = unit_mix_from_household_ratio(
                [(m.exclusive_area_m2, m.household_ratio) for m in req.unit_mix]
            )
        else:
            unit_mix_list = [UnitMix(**m) for m in UNIT_MIX]

        #임대 평형 : 전용면적만 입력받고 공급면적은 임대 전용률로 되돌린다.
        #  임대 비율은 입력받지 않는다 — 용적률 완화분에서 법정으로 정해진다 (도시정비법 제54조)
        engine_params = dict(ENGINE_DEFAULTS_FOR_PARAMS)
        #재건축 : 의무 임대가 없고(도시정비법 제10조·시행령 제9조), 법적상한 초과분만 공공주택 (제54조④, 조례·정비계획 50%)
        if project_type == ProjectType.RECONSTRUCTION:
            engine_params["base_rental_ratio"] = RECON_BASE_RENTAL_RATIO
            engine_params["uplift_rental_share"] = RECON_UPLIFT_RENTAL_SHARE
        if req.rental_exclusive_area_m2:
            engine_params["rental_exclusive_area_m2"] = req.rental_exclusive_area_m2
            engine_params["rental_supply_area_m2"] = round(
                rental_supply_from_exclusive(req.rental_exclusive_area_m2), 2
            )

        #공공기여 : 종상향 최소 비율 + 허용 → 상한까지의 상한용적률 산식 (노드별, /zone 이 토지 기준으로 계산).
        #  세부 설정에서 토지 · 공공임대 건축물 · 현금을 기부면적 비율(%)로 섞는다 → AI/engine/public_contribution.py
        #    토지     : 기부한 땅만큼 건축 대지가 준다 (종전자산은 그대로 두고 연면적만 줄인다)
        #    현금     : 기부면적의 절반까지 (시행령 제14조②). 땅 대신 현금이 사업비가 된다
        #    공공임대 : 땅은 그대로, 공공임대를 지어 기부채납한다 (대지지분·설치비 환산은 아래 build_params 뒤에서 잰다)
        #  노드 용적률에 필요한 Σ 계수 × α 는 노드의 토지 기부 비율에서 되돌려 구한다
        if req.contribution_mix is not None:
            contribution_mix, contribution_cash_capped = normalize_mix(
                req.contribution_mix.land, req.contribution_mix.public_rental, req.contribution_mix.cash
            )
        else:
            #비율 없이 버튼 이름만 온 요청 — 그 버튼의 프리셋으로 본다
            contribution_mix = CONTRIBUTION_PRESETS.get(req.contribution_method or "land", CONTRIBUTION_PRESETS["land"])
            contribution_cash_capped = False
        contribution_need_value = contribution_need(req.public_contribution_ratio)
        #종상향 최소 공공기여 (순부담). 노드의 토지 비율보다 클 수 없다 (노드 값 = max(산식, 최소))
        contribution_min_ratio = min(req.min_contribution_ratio or 0.0, req.public_contribution_ratio)
        contribution_active = contribution_need_value > 0 or contribution_min_ratio > 0
        #부지가액 = 개별공시지가 × 2 (운영기준 기본 부지가액가중치, 이촌 강변·강서 고시와 같다).
        #  '대' 필지 토지 감정가(공시지가 × λ, 사업시행인가 시점)에서 λ 를 되돌려 같은 시점의 공시지가를 쓴다
        site_value_per_m2 = rental_land_price_per_m2 / appraisal_ratio * SITE_VALUE_WEIGHT if appraisal_ratio else 0.0
        #건축 대지는 공공임대 몫을 잰 뒤 정한다 (아래). 그 전까지는 원래 대지 — 대지지분 비는 대지 크기와 무관하다
        net_site_area_m2 = req.site_area_m2

        #단계별 ProjectParams.
        #  sale_per_m2 : 일반분양가 / member_time_factor : 조합원분양가를 고시일 값에 묶는 계수
        #  rental_years : 의무 임대 건축비 시점 (일반분양 공고) / cost_multiplier : 도급단가 대비 공사비 배수
        #  uplift_years : 제54조 완화분 인수 시점 (없으면 rental_years)
        def build_params(sale_per_m2, member_time_factor, rental_years, cost_multiplier, uplift_years=None) -> ProjectParams:
            sl = dict(sliders)
            sl["construction_cost_per_pyeong"] = round(cost_contract * cost_multiplier, 1)
            sl["general_price_per_m2"] = round(sale_per_m2, 2)
            #기타사업비는 공사비 × 비율로 잡히는데 확정 이후 증액은 도급 공사비에만 붙는다.
            #  비율을 배수로 나눠 기타사업비를 고시일 기준 금액에 묶어 둔다
            if "other_cost_ratio" in sl:
                sl["other_cost_ratio"] = sl["other_cost_ratio"] / cost_multiplier
            ep = dict(engine_params)
            ep["member_price_time_factor"] = member_time_factor
            #임대 건물 인수가격 시점 보정
            #  의무 임대 : 기본형건축비 고시 월 → 일반분양 공고 시점 (건설공사비지수)
            #  완화분    : 표준건축비 고시 월 → 인수 시점 (개정 실측 인상률)
            ep["rental_cost_multiplier"] = round(rental_multiplier(_shift_ym(now_ym, rental_years)), 4)
            ep["uplift_rental_cost_multiplier"] = round(
                uplift_multiplier(_shift_ym(now_ym, rental_years if uplift_years is None else uplift_years)), 4
            )
            #의무 임대 부속토지 감정가 — 사업시행인가 시점 값이라 단계마다 같다
            ep["rental_land_price_per_m2"] = rental_land_price_per_m2
            return ProjectParams(
                name=req.name,
                project_type=project_type,
                site_area_m2=net_site_area_m2,
                member_count=req.member_count,
                unit_mix_list=unit_mix_list,
                far_base=req.far_base,
                total_prior_asset=total_prior_asset,
                **sl,
                **ep,
            )
        
        #기부면적 비율대로 기여를 채운다 (public_contribution.mixed_contribution).
        #  공공임대 몫이 있으면 λ (공급 1㎡ 의 대지지분 = 주택 몫 대지 ÷ 주택 공급면적)와
        #  b (공급 1㎡ 의 설치비 환산부지)를 관리처분 확정 단계 배분에서 잰다 — 면적·세대 배분은 가격과 무관하다.
        #  지하층면적 비는 기부 세대를 넣기 전 배분에서 잰다.
        #  설치비 = 기본형건축비 (지상층 + 지하층면적 비 × 지하층건축비, 운영기준 : 공공임대는 분양가상한제 기본형건축비),
        #  부지가액과 같은 사업시행인가 시점으로 공사비지수만큼 민다
        land_share_per_supply = conversion_per_supply = 0.0
        rental_supply_area_m2 = 0.0
        if contribution_mix.public_rental > 0 and contribution_active:
            probe = build_params(sale_mgmt, 1.0, mgmt_years, 1.0)
            probe_areas = calc_area(probe)
            probe_costs = calc_construction_cost(probe, probe_areas, calc_allocation(probe, probe_areas))
            land_share_per_supply = (
                req.site_area_m2 * probe_areas.housing_total_m2 / probe_areas.ground_m2 / probe_areas.supply_total_m2
            )
            underground_per_supply = probe_costs.underground_m2 / probe_areas.supply_total_m2
            install_per_supply = (
                base_build_cost_per_m2(probe.rental_floor_band, probe.rental_exclusive_area_m2)
                + underground_per_supply * BASEMENT_BUILD_COST_KRW_THOUSAND / 10
            ) * rental_multiplier(prior_ym)
            conversion_per_supply = install_per_supply / site_value_per_m2 if site_value_per_m2 > 0 else 0.0
            rental_supply_area_m2 = probe.rental_supply_area_m2
        mixed = mixed_contribution(
            contribution_need_value, contribution_min_ratio, req.site_area_m2, contribution_mix,
            land_share_per_supply, conversion_per_supply,
        )
        #토지로만 내면 노드의 토지 비율 그대로다 (같은 식이지만 부동소수 오차로 세대수가 흔들리지 않게)
        if contribution_mix.cash <= 0 and contribution_mix.public_rental <= 0:
            contribution_land_ratio = req.public_contribution_ratio
        else:
            contribution_land_ratio = mixed.land_ratio
        contribution_cash_area_m2 = mixed.cash_area_m2
        #현금 = 환산부지 × 부지가액 (만원). 사업시행인가 시점 금액에 고정해 사업비에 더한다
        contribution_cash = round(contribution_cash_area_m2 * site_value_per_m2, 1)
        #공공임대 세대수 : 필요한 면적을 채우도록 올림
        contribution_rental_count = (
            math.ceil(mixed.rental_supply_m2 / rental_supply_area_m2) if mixed.rental_supply_m2 > 0 else 0
        )
        engine_params["contribution_cash"] = contribution_cash
        engine_params["donated_rental_count"] = contribution_rental_count
        net_site_area_m2 = req.site_area_m2 * (1 - contribution_land_ratio)

        #조합원 개인 종전자산
        #  ① 내 필지 지정 → 그 필지의 토지분 + 건물분. ρ = r_개인 ÷ r_구역 이 1 이 아니게 되어
        #     "내 집이 구역 평균보다 덜 낡았나" 가 분담금에 반영된다
        #  ② 공시가격 직접 입력 → 토지분만 (건물분 0)
        #  ③ 미지정 → 구역 종전자산의 1인분. ρ = 1 이라 구역 평균 조합원의 분담금이 나온다.
        #     기존 동작과 정확히 같아서 폴백을 깨지 않는다
        owner_parcel = None
        exclusive_total = 0.0
        if req.owner.pnu and req.parcel_valuations and recon_prior is None:
            owner_parcel = next((v for v in req.parcel_valuations if v.pnu == req.owner.pnu), None)

        if recon_prior is not None:
            #재건축 : 내 호의 공동주택가격으로 잡는다. 전유면적을 넣으면 그 면적(가장 가까운 면적)의 호당 공시가격,
            #  공시가격을 직접 넣으면 그 값, 둘 다 없으면 단지 1인분
            area_prices = recon.get("area_prices") or []
            if req.owner.exclusive_area_m2 and area_prices:
                _, unit_price, _ = min(area_prices, key=lambda row: abs(float(row[0]) - req.owner.exclusive_area_m2))
                owner_value = float(unit_price) / APT_PRICE_REALIZATION_RATE * apt_growth
            elif req.owner.official_price is not None:
                owner_value = req.owner.official_price / APT_PRICE_REALIZATION_RATE * apt_growth
            else:
                owner_value = total_prior_asset / max(req.member_count, 1)
            owner = OwnerInput(
                desired_unit=req.owner.desired_unit,
                appraisal_ratio=appraisal_ratio,
                appraisal_value=owner_value,
            )
        elif (
            owner_parcel is not None and owner_parcel.housing_price > 0
            and HOUSING_REALIZATION_RATES.get(owner_parcel.housing_kind)
        ):
            #내 필지가 주택이면 공시가격 ÷ 현실화율 (구역 집계와 같은 기준).
            #  공동주택 : 전유면적을 넣으면 그 면적(가장 가까운 면적)의 호당 공시가격, 없으면 필지 호당 평균
            #  단독·다가구 : 주택 한 채 전체 (다가구도 소유자는 한 사람이다)
            rate = HOUSING_REALIZATION_RATES[owner_parcel.housing_kind]
            area_prices = owner_parcel.housing_area_prices or []
            if owner_parcel.housing_kind == "공동" and req.owner.exclusive_area_m2 and area_prices:
                _, unit_price, _ = min(area_prices, key=lambda row: abs(float(row[0]) - req.owner.exclusive_area_m2))
                official = float(unit_price)
            elif owner_parcel.housing_kind == "공동":
                official = owner_parcel.housing_price / max(owner_parcel.housing_units, 1)
            else:
                official = owner_parcel.housing_price
            owner = OwnerInput(
                desired_unit=req.owner.desired_unit,
                appraisal_ratio=appraisal_ratio,
                appraisal_value=official / rate * prior_growth,
            )
        elif owner_parcel is not None:
            #집합건물이면 내 몫으로 나눈다.
            #  분모는 전유면적 합계다 — 연면적(totArea)으로 나누면 공용면적까지 분모에
            #  들어가 내 몫이 과소평가된다 (전용률 74% 아파트면 26% 깎인다).
            #
            #  전유면적 합계는 /zone 에서 받지 않는다. 호·면적구분마다 한 행이라
            #  대단지는 37페이지(9.7초)가 걸리는데, 실제로 쓰이는 건 내 필지 하나뿐이고
            #  그것도 사용자가 전유면적을 입력했을 때만이다 → 여기서 한 번만 부른다
            exclusive_total = 0.0
            if req.owner.exclusive_area_m2:
                exclusive_total = await get_cached_exclusive_total(req.owner.pnu) or 0.0
                if not exclusive_total:
                    exclusive_total = fetch_exclusive_total(req.owner.pnu)
                    await set_cached_exclusive_total(req.owner.pnu, exclusive_total)

            if req.owner.exclusive_area_m2 and exclusive_total > 0:
                share = min(req.owner.exclusive_area_m2 / exclusive_total, 1.0)
            elif owner_parcel.household_count > 1:
                #전유면적을 모르면 세대수로 균등 분할한다.
                #  가정이다 — 같은 건물에 평형이 다르면 어긋난다 (월계동 12번지 실측:
                #  균등 0.00110 vs 전유 50.18㎡ 기준 0.00103, 6% 차)
                share = 1.0 / owner_parcel.household_count
            else:
                share = 1.0

            owner = OwnerInput(
                desired_unit=req.owner.desired_unit,
                appraisal_ratio=appraisal_ratio,
                land_area_m2=owner_parcel.land_area_m2,
                land_price_per_m2=owner_parcel.land_price_per_m2 * prior_growth,
                building_structure=owner_parcel.structure,
                building_area_m2=owner_parcel.building_area_m2 if owner_parcel.has_building else None,
                building_elapsed_years=owner_parcel.elapsed_years + prior_years,
                exclusive_share=share,
                replacement_cost_per_m2=replacement_cost_per_m2,
                building_cost_index=owner_parcel.cost_index,
            )
        elif req.owner.official_price is not None:
            owner = OwnerInput(
                desired_unit=req.owner.desired_unit,
                appraisal_ratio=appraisal_ratio,
                official_price=req.owner.official_price * prior_growth,
            )
        else:
            #1인분. 이미 평가시점으로 민 총액이라 prior_growth 를 또 곱하지 않는다.
            #  ※ appraisal_value 는 본래 "감정평가 통지서를 받은 조합원이 직접 입력한 값" 필드다.
            #    여기서는 "종전자산을 직접 지정" 이라는 같은 동작을 쓰려고 재사용한다.
            #    엔진은 둘을 구분할 필요가 없고(동작이 같다), 어느 쪽인지는 이 라우터가 안다.
            #    나중에 통지서 값 입력 UI 가 생기면 req.owner 쪽 분기로 구분할 것
            owner = OwnerInput(
                desired_unit=req.owner.desired_unit,
                appraisal_ratio=appraisal_ratio,
                appraisal_value=total_prior_asset / max(req.member_count, 1),
            )

        #관리처분 확정 → 준공 정산을 네 단계로 계산한다. 마지막 단계가 화면의 예상 분담금이다
        #  ① 관리처분 확정  : 고시일에 조합이 내놓는 값 (모든 항목을 고시일 시점으로)
        #  ② 분양·임대 시점 : 일반분양·의무 임대 건축비는 착공(일반분양 공고), 완화분 임대 인수는 준공 시점 가격으로.
        #                     조합원분양가는 고시일 값 그대로
        #  ③ 물가변동       : 공사비 기성에 건설공사비지수 상승분이 붙는다
        #  ④ 비물가 초과    : 계약단가가 지수보다 빨리 오르는 몫까지 붙는다 (= 준공 정산)
        #  면적·세대 배분은 가격과 무관해 네 단계가 같다
        member_time_factor = sale_mgmt / sale_start if sale_start else 1.0
        stage_inputs = [
            ("관리처분 확정", sale_mgmt, 1.0, mgmt_years, 1.0, mgmt_years),
            ("분양·임대 시점 반영", sale_start, member_time_factor, start_years, 1.0, complete_years),
            ("공사비 물가변동", sale_start, member_time_factor, start_years, escalation_index, complete_years),
            ("비물가 초과 증액", sale_start, member_time_factor, start_years, escalation_total, complete_years),
        ]

        #자동이면 ① 관리처분 확정 단계에서 비율을 역산해 네 단계 모두에 쓴다.
        #  조합원분양가는 관리처분 때 정해져 고정되고(시점 계수), ②~④ 시점 보정은 그 위에 그대로 얹힌다
        member_ratio_solved = None
        member_ratio_bound = None
        member_price_warnings = []
        if member_price_auto:
            mgmt_params = build_params(sale_mgmt, 1.0, mgmt_years, 1.0)
            mgmt_alloc = calc_allocation(mgmt_params, calc_area(mgmt_params))
            member_ratio_solved = solve_member_price_ratio(mgmt_params, mgmt_alloc, MEMBER_PRICE_TARGET_RATE)
            if member_ratio_solved is None:
                ratio = MEMBER_PRICE_RATIO_MAX
                member_price_warnings.append("조합원 분양 몫이 없어 조합원분양가 비율을 역산하지 못했습니다.")
            else:
                ratio = min(max(member_ratio_solved, MEMBER_PRICE_RATIO_MIN), MEMBER_PRICE_RATIO_MAX)
                if member_ratio_solved < MEMBER_PRICE_RATIO_MIN:
                    member_ratio_bound = "min"
                elif member_ratio_solved > MEMBER_PRICE_RATIO_MAX:
                    member_ratio_bound = "max"
            sliders["member_price_ratio"] = round(ratio, 4)

        stages = []
        for label, sale_per_m2, factor, rental_years, multiplier, uplift_years in stage_inputs:
            params = build_params(sale_per_m2, factor, rental_years, multiplier, uplift_years)
            areas = calc_area(params)
            alloc = calc_allocation(params, areas)
            #평형을 고르게 하지 않고 분양 평형 전부의 분담금을 내려준다.
            #  비례율·권리가액은 평형과 무관해서 한 번만 계산되고 분양가만 평형별로 달라진다
            units = calc_contribution_all(params, alloc, owner)
            #화면 상단 요약(선택 평형)용 레거시 필드.
            #  사용자가 평형 구성을 바꾸면 전에 고른 평형이 사라질 수 있어 첫 평형으로 떨어뜨린다
            selected = next((u for u in units if u.name == owner.desired_unit), units[0])
            project = calc_project(params, alloc)
            stages.append({
                "label": label,
                "proportional_rate": round(project.proportional_rate, 2),
                "total_cost": round(project.total_cost, 1),
                "total_post_asset": round(project.total_post_asset, 1),
                "contribution": round(selected.contribution, 1),
                "unit_contributions": {u.name: round(u.contribution, 1) for u in units},
            })

        #역산 비율이 범위 끝에 걸리면 관리처분 비례율이 목표에서 벗어난다 → 알린다
        mgmt_rate = stages[0]["proportional_rate"]
        if member_ratio_bound == "min":
            floor_text = "0원으로 낮춰도" if MEMBER_PRICE_RATIO_MIN <= 0 else f"일반분양가의 {MEMBER_PRICE_RATIO_MIN:.0%}까지 낮춰도"
            member_price_warnings.append(
                f"조합원분양가를 {floor_text} 관리처분 비례율이 "
                f"{mgmt_rate:.0f}%로 {MEMBER_PRICE_TARGET_RATE:.0f}%를 넘습니다. 사업성이 매우 높은 조건입니다."
            )
        elif member_ratio_bound == "max":
            member_price_warnings.append(
                f"조합원분양가를 일반분양가와 같게 정해도 관리처분 비례율이 {mgmt_rate:.0f}%로 "
                f"{MEMBER_PRICE_TARGET_RATE:.0f}%에 못 미칩니다. 사업성이 낮은 조건입니다."
            )

        #엔진의 "통상 범위" 경고는 ④ 준공 정산 비례율을 본다. 자동이면 ① 이 100% 로 맞춰져 있으므로
        #  비례율이 이상하다는 뜻이 아니라 확정 이후 변화가 크다는 뜻이다 → 확정 → 정산으로 바꿔 적는다
        engine_warnings = project.warnings
        final_rate = stages[-1]["proportional_rate"]
        if member_price_auto and any("통상 범위" in w for w in engine_warnings):
            engine_warnings = [w for w in engine_warnings if "통상 범위" not in w]
            change = "줄어 추가분담금으로" if final_rate < mgmt_rate else "늘어 환급으로"
            member_price_warnings.append(
                f"관리처분 비례율 {mgmt_rate:.0f}%가 준공 정산 때 {final_rate:.0f}%가 됩니다. "
                f"확정 이후 공사비 증액·분양 시점 차이로 권리가액이 종전자산의 {abs(mgmt_rate - final_rate):.0f}%만큼 {change} 돌아옵니다."
            )

        #재건축 안내 : 재건축초과이익 환수와 상가 조합원은 계산에 넣지 않았다
        project_warnings = []
        if project_type == ProjectType.RECONSTRUCTION:
            #재초환은 이 서비스의 계산 범위가 아니다 (2026-10-08 결정) — 주의문만 띄운다
            project_warnings.append(
                "재건축초과이익 환수 부담금은 계산하지 않았습니다. 부과 대상이면 분담금과 별도로 내야 합니다."
            )
            if recon_prior is not None:
                shop_units = int((recon.get("commercial") or {}).get("units") or 0)
                project_warnings.append(
                    f"종전자산은 아파트를 공동주택가격 ÷ 현실화율 {APT_PRICE_REALIZATION_RATE:.0%}로"
                    + (f", 상가 등 {shop_units}호를 토지 지분 + 건물 원가법으로 잡았습니다." if shop_units else " 잡았습니다.")
                )

        #공공기여 안내 (세부 설정의 공공기여 칸 아래에 띄운다) — 계산 결과와 법정 조건
        if not contribution_active:
            contribution_note = "이 용적률은 공공기여 없이 받을 수 있어 비율에 따라 결과가 달라지지 않습니다."
        else:
            parts = []
            if contribution_land_ratio > 0:
                parts.append(f"토지 {req.site_area_m2 * contribution_land_ratio:,.0f}㎡")
            if contribution_cash > 0:
                parts.append(f"현금 {contribution_cash / 10_000:,.1f}억원")
            if contribution_rental_count > 0:
                parts.append(f"공공임대 {contribution_rental_count:,}세대")
            contribution_note = (
                f"기부 내용 : {' + '.join(parts)} (기부면적 {mixed.total_m2:,.0f}㎡ 중 토지 {contribution_mix.land:.0%}"
                f" · 공공임대 {contribution_mix.public_rental:.0%} · 현금 {contribution_mix.cash:.0%})."
            )
            if contribution_cash_capped:
                contribution_note += f" 현금은 기부면적의 절반까지라 {CASH_MAX_SHARE:.0%}로 맞췄습니다."
            if contribution_cash > 0:
                contribution_note += (
                    f" 현금은 공시지가 × {SITE_VALUE_WEIGHT:g} 로 환산했고, 정비계획을 변경할 때만 "
                    "토지등소유자 과반수 동의를 받아 낼 수 있습니다 (도시정비법 시행령 제14조②)."
                )
            if contribution_rental_count > 0:
                contribution_note += (
                    " 공공임대는 인수대금이 없고, 설치비는 기본형건축비로 환산했습니다 (실제 인정 금액은 인허가 때 정해집니다)."
                )

        #루프가 끝난 뒤의 params·alloc·units·project 는 ④ 준공 정산 값이다
        options = unit_options(params, alloc)
        prior_asset = estimate_prior_asset(owner)
        #임대 인수수입 분해 (준공 정산 단계) — 화면·디버깅용
        revenues = calc_post_asset(params, areas, alloc)
        rental_price_announced = takeover_price_per_m2(params.rental_floor_band, params.rental_exclusive_area_m2)
        uplift_price_announced = uplift_takeover_price_per_m2(params.rental_floor_band, params.rental_exclusive_area_m2)

        member_price_ratio = sliders.get("member_price_ratio", 0.0)
        timeline = {
            "now_ym": now_ym,
            "prior_ym": prior_ym,
            "mgmt_ym": mgmt_ym,
            "start_ym": start_ym,
            "complete_ym": complete_ym,
            "prior_years": round(prior_years, 2),
            "mgmt_years": mgmt_years,
            "start_years": round(start_years, 2),
            "complete_years": complete_years,
            #공사비 (만원/평) : 도급단가(고시일) → 기성 평균(준공 정산)
            "cost_contract_per_pyeong": round(cost_contract, 1),
            "cost_final_per_pyeong": round(cost_contract * escalation_total, 1),
            "escalation_index": round(escalation_index, 4),
            "escalation_excess": round(escalation_total / escalation_index, 4),
            "escalation_total": round(escalation_total, 4),
            "excess_rate": round(excess.rate, 4),
            "excess_basis": excess.basis,
            "excess_case_count": excess.case_count,
            "excess_span": excess.span,
            #분양가 (만원/㎡) : 조합원분양가는 고시일 일반분양가 × 비율로 확정된다
            "general_price_mgmt_per_m2": round(sale_mgmt, 2),
            "general_price_start_per_m2": round(sale_start, 2),
            #비율 : auto 면 관리처분 비례율이 target_rate 가 되도록 역산한 값 (solved = 범위 제한 전, bound = 걸린 끝 min/max)
            "member_price_mode": "auto" if member_price_auto else "manual",
            "member_price_target_rate": MEMBER_PRICE_TARGET_RATE if member_price_auto else None,
            "member_price_ratio_solved": round(member_ratio_solved, 4) if member_ratio_solved is not None else None,
            "member_price_ratio_bound": member_ratio_bound,
            "member_price_ratio": member_price_ratio,
            "member_price_per_m2": round(sale_mgmt * member_price_ratio, 2),
            "member_price_per_pyeong": round(sale_mgmt * member_price_ratio / PER_PYEONG_TO_PER_M2, 1),
            "public_contribution_ratio": req.public_contribution_ratio,
            #공공기여 (세부 설정) — 기부면적 비율(%, 합 100 으로 맞춘 값), 기부면적(환산 포함 ㎡), 실제로 뗀 토지 비율,
            #  현금(만원)·환산부지, 기부채납 공공임대 세대수, 부지가액(만원/㎡), 안내 문장
            "contribution_mix": {
                "land": round(contribution_mix.land * 100, 1),
                "public_rental": round(contribution_mix.public_rental * 100, 1),
                "cash": round(contribution_mix.cash * 100, 1),
            },
            "contribution_total_m2": round(mixed.total_m2, 1),
            "contribution_land_ratio": round(contribution_land_ratio, 4),
            "contribution_cash": round(contribution_cash, 1),
            "contribution_cash_area_m2": round(contribution_cash_area_m2, 1),
            "contribution_rental_count": contribution_rental_count,
            "contribution_site_value_per_m2": round(site_value_per_m2, 2),
            "contribution_note": contribution_note,
            #사업 유형과 종전자산을 잡은 방법
            "project_type": project_type.value,
            "prior_basis": (
                f"공동주택가격 ÷ 현실화율 {APT_PRICE_REALIZATION_RATE:.0%}" if recon_prior is not None
                else "공시지가 × λ + 건물 원가법"
            ),
            "net_site_area_m2": round(net_site_area_m2, 1),
            #임대 인수 (만원)
            #  의무 임대 건물 = 기본형건축비(지상층 + 지하층) 80% 를 고시 월에서 일반분양 공고 시점까지 공사비지수로 민 값
            #  완화분 건물    = 표준건축비(지하층 63%)를 고시 월에서 인수 시점까지 개정 실측 인상률로 민 값
            #  부속토지       = 의무 임대만 사업시행인가 시점 감정가 (제54조 완화분은 기부채납이라 0)
            #  단가 필드(…_per_m2)는 지상층 주택공급면적 기준이다
            "rental_takeover_basis": f"기본형건축비(지상층 + 지하층) × ({RENTAL_TAKEOVER_RATIO:.0%} + 가산비 {RENTAL_SURCHARGE_RATIO:.0%}) ({RENTAL_NOTICE}, {RENTAL_ANNOUNCED})",
            "rental_price_announced_per_m2": round(rental_price_announced, 2),
            "rental_price_mgmt_per_m2": round(rental_price_announced * round(rental_multiplier(mgmt_ym), 4), 2),
            "rental_price_final_per_m2": round(rental_price_announced * params.rental_cost_multiplier, 2),
            "rental_uplift_takeover_basis": (
                f"{UPLIFT_BASIS}" + ("" if UPLIFT_RATIO == 1 else f" × {UPLIFT_RATIO:.0%}")
                + (" (지하층 63%)" if UPLIFT_BASIS == "표준건축비" else " (지상층 + 지하층)") + f" ({UPLIFT_NOTICE})"
            ),
            "rental_uplift_price_announced_per_m2": round(uplift_price_announced, 2),
            "rental_uplift_price_final_per_m2": round(uplift_price_announced * params.uplift_rental_cost_multiplier, 2),
            "rental_base_count": alloc.base_rental_count,
            "rental_uplift_count": alloc.uplift_rental_count,
            "rental_land_price_per_m2": round(rental_land_price_per_m2, 2),
            "rental_land_area_m2": round(revenues.rental_land_area_m2, 1),
            "rental_building_revenue": round(revenues.rental_building_revenue, 1),
            "rental_base_building_revenue": round(revenues.rental_base_building_revenue, 1),
            "rental_uplift_building_revenue": round(revenues.rental_uplift_building_revenue, 1),
            "rental_underground_m2": round(revenues.rental_underground_m2, 1),
            "rental_land_revenue": round(revenues.rental_land_revenue, 1),
            "stages": stages,
        }

        #조합원 수 슬라이더 범위는 용적률에 따라 바뀐다 (분양 세대수를 넘을 수 없음)
        if req.household_count:
            member_range = member_count_range(params, alloc, req.household_count)
        else:
            #세대수 자료가 없으면 동의율 기준을 쓸 수 없다. 분양 세대수 안에서 탐색하도록 넓게 준다
            sale_count = sum(u.count for u in alloc.unit_types)
            low = max(1, int(sale_count * MEMBER_COUNT_UNKNOWN_MIN_RATIO))
            member_range = MemberCountRange(
                value=min(max(req.member_count, low), sale_count),
                min=low,
                max=sale_count,
                capped=True,
            )

        #종전자산 분해 — 화면과 디버깅용.
        #  구역은 전수 집계라 토지분·건물분이 나오고, 개인은 r_개인 을 역산해 ρ 를 만든다
        prior_asset_detail = {
            "zone_land_total": round(zone_prior.land_total, 1) if zone_prior else None,
            "zone_building_total": round(zone_prior.building_total, 1) if zone_prior else None,
            #주택 공시가격 ÷ 현실화율로 잡은 몫 (토지분·건물분과 따로 센다)
            "zone_housing_total": round(zone_prior.housing_total, 1) if zone_prior else None,
            "housing_parcel_count": zone_prior.housing_parcel_count if zone_prior else None,
            "owner_basis": (
                "공시가격 ÷ 현실화율" if owner_parcel is not None and owner_parcel.housing_price > 0
                else ("토지분 + 건물분" if owner_parcel is not None else None)
            ),
            "zone_total": round(total_prior_asset, 1),
            "zone_ratio": round(zone_prior.ratio, 4) if zone_prior else None,
            "measured_member_count": zone_prior.member_count if zone_prior else None,
            "building_parcel_count": zone_prior.building_parcel_count if zone_prior else None,
            "owner_personalized": owner_parcel is not None,
            "rho": None,
            #집합건물에서 적용된 내 몫. 전유면적을 입력했으면 전유합계 기준,
            #  없으면 세대수 균등분할이다 (월계동 12번지 실측 6% 차)
            "owner_share": round(owner.exclusive_share, 6) if owner_parcel is not None and owner.exclusive_share else None,
            "owner_exclusive_total_m2": round(exclusive_total, 2) if owner_parcel is not None else None,
        }

        #ρ : 내 필지를 지정했을 때만 의미가 있다 (미지정이면 1인분이라 정확히 1.0)
        if owner_parcel is not None and zone_prior and zone_prior.ratio:
            owner_official = (
                owner_parcel.land_area_m2 * owner_parcel.land_price_per_m2 * prior_growth / 10_000
                * (owner.exclusive_share or 1.0)
            )
            if owner_official:
                prior_asset_detail["rho"] = round(
                    (prior_asset / owner_official) / zone_prior.ratio, 4
                )

    #오류 발생시 Service Unavailable Exception 발생
    except Exception as err:
        logger.warning(f"[ Log ] : Contribution API 호출에서 오류 발생 : {str(err)}")
        raise ServiceUnavailableException("Contribution API 호출에서 오류가 발생했습니다.")

    #모든 계산 결과를 검증한 뒤에만 크레딧을 차감한다
    result_payload = {
        "prior_asset": prior_asset,
        "proportional_rate": project.proportional_rate,
        "right_value": prior_asset * project.proportional_rate / 100,
        "member_price": selected.member_price,
        "contribution": selected.contribution,
        "project": asdict(project),
        "unit_options": [asdict(o) for o in options],
        "unit_contributions": [asdict(u) for u in units],
        "rental_exclusive_area_m2": params.rental_exclusive_area_m2,
        #종전자산 분해. ρ = r_개인 ÷ r_구역 이 1 이 아니면 약분이 깨져 개인화된 것이다
        #  (내 필지를 지정하지 않으면 1인분이라 정확히 1.0 이 나온다)
        "prior_asset_detail": prior_asset_detail,
        "member_count_range": asdict(member_range),
        #사업 일정과 관리처분 확정 → 준공 정산 단계별 분담금
        "timeline": timeline,
        "warnings": project_warnings + member_price_warnings + engine_warnings,
    }
    response = ContributionResponse.model_validate(
        {**result_payload, "credits_remaining": 0}
    )
    unlimited = get_active_organization(session, int(user_id)) is not None
    credits_remaining = await consume_credit_token(int(user_id), req.credit_token, unlimited=unlimited)

    #검증된 응답 모델에 잔액만 반영해 FastAPI 응답 검증 실패로 인한 오차감을 차단
    return response.model_copy(update={"credits_remaining": credits_remaining})