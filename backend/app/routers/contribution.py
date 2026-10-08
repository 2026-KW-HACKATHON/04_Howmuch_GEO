from app.config.engine_defaults import (
    DEFAULT_PROJECT_PERIOD_YEARS,
    ENGINE_DEFAULTS,
    ENGINE_DEFAULTS_FOR_PARAMS,
    LAND_PRICE_ANNUAL_RATE,
    MEMBER_COUNT_UNKNOWN_MIN_RATIO,
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
    calc_contribution_all,
    estimate_prior_asset,
    calc_project,
    member_count_range,
    rental_supply_from_exclusive,
    unit_mix_from_household_ratio,
    unit_options,
)
from AI.engine.prior_asset import ParcelValuation, aggregate_zone
from AI.engine.rental_cost import ANNUAL_INCREASE_RATE as RENTAL_ANNUAL_INCREASE
from AI.engine.schema import (
    PER_PYEONG_TO_PER_M2, ParcelInfo, ProjectType, UnitMix, OwnerInput, ProjectParams, UnitType,
)
from AI.engine.zone import build_zone_summary
from AI.predict import trend
from AI.predict.construction_cost import load_index, predict_cost_per_pyeong
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
import os
import requests
import time

#부동산 계산식 API 라우터 설정
router = APIRouter(
    prefix="/api/v1",
    tags=["Contribution Router"]
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
        #슬라이더에서 뺐으므로 평소에는 ENGINE_DEFAULTS 의 고정값(1.543)이 쓰인다
        appraisal_ratio = sliders.pop("appraisal_ratio", ENGINE_DEFAULTS["appraisal_ratio"])

        #사업 기간도 ProjectParams 의 필드가 아니다.
        #공사비·분양가를 어느 시점으로 밀지 정하는 값이라 예측 모델 쪽에서 쓴다 (target_ym)
        period_years = sliders.pop("project_period_years", DEFAULT_PROJECT_PERIOD_YEARS)

        #슬라이더에 보이는 공사비·분양가는 "오늘 기준" 값이다.
        #  사용자가 아는 금액을 조절하게 두고, 계산만 사업기간 뒤 시점으로 민다.
        #  (화면에는 "예상 분담금 (N년 후 기준)" 으로 어느 시점 금액인지 표시된다)
        #  공사비는 건설공사비지수로, 분양가는 측정한 연평균 상승률로 보정한다
        now_ym = datetime.now().strftime("%Y-%m")
        target_ym = f"{datetime.now().year + int(period_years)}-{datetime.now().month:02d}"

        #종전자산 건물분의 재조달원가는 공사비와 "같은 값, 다른 시점" 이다.
        #  보정 전(오늘 기준) 값을 미리 잡아둔다 — 아래에서 sliders 가 덮어써진다
        base_cost_per_pyeong = sliders.get("construction_cost_per_pyeong", 0.0)
        cost_index = load_index()
        cost_rate = trend.estimate_annual_rate(cost_index).annual_rate

        if period_years:
            if "construction_cost_per_pyeong" in sliders:
                sliders["construction_cost_per_pyeong"] = round(
                    sliders["construction_cost_per_pyeong"]
                    * trend.index_at(target_ym, cost_index, cost_rate)
                    / trend.index_at(now_ym, cost_index, cost_rate),
                    1,
                )

            #분양가도 공사비와 같은 방식 — 지수 파일로 보정한다.
            #  예전에는 측정값(연 8.03%)을 상수로 박아뒀는데 지역·시점이 고정되는 문제가 있었다
            if "general_price_per_m2" in sliders:
                sliders["general_price_per_m2"] = round(
                    escalate_sale(sliders["general_price_per_m2"], now_ym, target_ym),
                    2,
                )

        #종전자산도 사업기간만큼 민다.
        #  단 시점이 다르다 — 종전자산은 "사업시행계획인가 고시일" 기준으로 평가하고(도시정비법),
        #  그 날은 관리처분인가보다 중앙값 3.3년 앞선다. 그래서 (사업기간 − 3.3)년만 민다.
        #  이걸 빼먹으면 분모(종전자산)만 제자리인 채 분자(종후자산)가 커져 비례율이 폭증한다
        prior_years = max(float(period_years) - PRIOR_ASSET_LEAD_YEARS, 0.0)
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
        #    그 값은 관리처분(target_ym) 까지 밀려 있어 종전자산 평가시점보다 3.3년 앞선다.
        #    공사비 연 3.97% 면 3.3년치가 13.7% 과대이고, 그만큼 건물분이 부풀어
        #    비례율이 과소 → 분담금이 과대해진다. 평가시점(prior_ym) 으로 다시 민다
        prior_ym = _shift_ym(now_ym, prior_years)
        replacement_cost_per_m2 = (
            base_cost_per_pyeong
            * trend.index_at(prior_ym, cost_index, cost_rate)
            / trend.index_at(now_ym, cost_index, cost_rate)
            * PER_PYEONG_TO_PER_M2
        )
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
                )
                for v in req.parcel_valuations
            ]
            zone_prior = aggregate_zone(
                valuations,
                land_multiplier=appraisal_ratio,
                replacement_cost_per_m2=replacement_cost_per_m2,
            )
            total_prior_asset = zone_prior.total
        else:
            #필지 원자료가 없으면 예전 방식(토지분만). 건물분이 빠져 다시 약분된다
            total_prior_asset = req.land_value_total * appraisal_ratio * prior_growth

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
        if req.rental_exclusive_area_m2:
            engine_params["rental_exclusive_area_m2"] = req.rental_exclusive_area_m2
            engine_params["rental_supply_area_m2"] = round(
                rental_supply_from_exclusive(req.rental_exclusive_area_m2), 2
            )

        #임대 인수수입도 관리처분 시점으로 민다 (표준건축비는 2023년 고시값)
        engine_params["rental_cost_multiplier"] = round(
            (1 + RENTAL_ANNUAL_INCREASE) ** float(period_years), 4
        )

        params = ProjectParams(
            name=req.name,
            project_type=ProjectType.REDEVELOPMENT,
            site_area_m2=req.site_area_m2,
            member_count=req.member_count,
            unit_mix_list=unit_mix_list,
            far_base=req.far_base,
            total_prior_asset=total_prior_asset,
            **sliders,
            **engine_params,
        )
        
        #조합원 개인 종전자산
        #  ① 내 필지 지정 → 그 필지의 토지분 + 건물분. ρ = r_개인 ÷ r_구역 이 1 이 아니게 되어
        #     "내 집이 구역 평균보다 덜 낡았나" 가 분담금에 반영된다
        #  ② 공시가격 직접 입력 → 토지분만 (건물분 0)
        #  ③ 미지정 → 구역 종전자산의 1인분. ρ = 1 이라 구역 평균 조합원의 분담금이 나온다.
        #     기존 동작과 정확히 같아서 폴백을 깨지 않는다
        owner_parcel = None
        exclusive_total = 0.0
        if req.owner.pnu and req.parcel_valuations:
            owner_parcel = next((v for v in req.parcel_valuations if v.pnu == req.owner.pnu), None)

        if owner_parcel is not None:
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

        areas = calc_area(params)
        alloc = calc_allocation(params, areas)
        options = unit_options(params, alloc)

        #평형을 고르게 하지 않고 분양 평형 전부의 분담금을 내려준다.
        #  비례율·권리가액은 평형과 무관해서 한 번만 계산되고 분양가만 평형별로 달라진다
        units = calc_contribution_all(params, alloc, owner)

        #화면 상단 요약(선택 평형)용 레거시 필드.
        #  사용자가 평형 구성을 바꾸면 전에 고른 평형이 사라질 수 있어 첫 평형으로 떨어뜨린다
        selected = next((u for u in units if u.name == owner.desired_unit), units[0])
        project = calc_project(params, alloc)
        prior_asset = estimate_prior_asset(owner)

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
            "zone_total": round(total_prior_asset, 1),
            "zone_ratio": round(zone_prior.ratio, 4) if zone_prior else None,
            "measured_member_count": zone_prior.member_count if zone_prior else None,
            "building_parcel_count": zone_prior.building_parcel_count if zone_prior else None,
            "owner_personalized": owner_parcel is not None,
            "rho": None,
            #집합건물에서 적용된 내 몫. 전유면적을 입력했으면 전유합계 기준,
            #  없으면 세대수 균등분할이다 (월계동 12번지 실측 6% 차)
            "owner_share": round(owner.exclusive_share, 6) if owner_parcel is not None else None,
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
        "warnings": project.warnings,
    }
    response = ContributionResponse.model_validate(
        {**result_payload, "credits_remaining": 0}
    )
    unlimited = get_active_organization(session, int(user_id)) is not None
    credits_remaining = await consume_credit_token(int(user_id), req.credit_token, unlimited=unlimited)

    #검증된 응답 모델에 잔액만 반영해 FastAPI 응답 검증 실패로 인한 오차감을 차단
    return response.model_copy(update={"credits_remaining": credits_remaining})