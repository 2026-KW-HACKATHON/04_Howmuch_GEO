from app.config.engine_defaults import DEFAULT_PROJECT_PERIOD_YEARS, ENGINE_DEFAULTS, ENGINE_DEFAULTS_FOR_PARAMS,MEMBER_COUNT_UNKNOWN_MIN_RATIO, UNIT_MIX
from app.schemas.realestate.realestate_request import ZoneRequest, ContributionRequest
from app.schemas.realestate.realestate_response import ContributionResponse
from app.services.credit_service import consume_credit_token
from app.utils.slider_builder import build_sliders
from app.exceptions.exceptions_handler import BadRequestException, ServiceUnavailableException, UnauthorizedException
from AI.engine.calc import MemberCountRange, calc_allocation, calc_area, calc_contribution, calc_project, member_count_range, unit_options
from AI.engine.schema import ParcelInfo, ProjectType, UnitMix, OwnerInput, ProjectParams, UnitType
from AI.engine.zone import build_zone_summary
from AI.predict.construction_cost import predict_cost_per_pyeong
from AI.predict.sale_price import fetch_trades, predict_sale_price_per_m2
from dataclasses import asdict
from datetime import datetime
from fastapi import APIRouter, HTTPException, Request, status
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

#슬라이더 및 추가 변수들로 계산하는 API
@router.post(
    "/contribution",
    response_model = ContributionResponse,
    summary = "조합원 개인 분담금 및 사업성 계산")
async def get_contribution(req: ContributionRequest, request: Request):
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

        #종전자산 총액 : 선택 구역 공시지가 총액 × 보정률. 개인 종전자산과 같은 근거를 쓴다
        #같은 보정률이 분자·분모에 들어가 분담금에서 약분되므로 이 값의 오차는 비례율 표시만 좌우한다
        if not req.land_value_total:
            raise BadRequestException("구역 공시지가 총액이 없습니다. 지도에서 필지를 선택한 뒤 다시 계산해 주세요.")

        total_prior_asset = req.land_value_total * appraisal_ratio

        params = ProjectParams(
            name=req.name,
            project_type=ProjectType.REDEVELOPMENT,
            site_area_m2=req.site_area_m2,
            member_count=req.member_count,
            unit_mix_list=[UnitMix(**m) for m in UNIT_MIX],
            far_base=req.far_base,
            total_prior_asset=total_prior_asset,
            **sliders,
            **ENGINE_DEFAULTS_FOR_PARAMS,
        )
        
        #조합원 종전자산 : 공시가격을 직접 받지 않으면 선택 구역 공시지가의 1인분으로 추정한다
        #1인분으로 두면 구역 평균 조합원이 되어 분담금이 구역 평균값으로 나온다.
        #내 필지를 지정하면 그 필지 공시가격이 들어와 개인화된다
        if req.owner.official_price is not None:
            prior_asset_kwargs = {"official_price": req.owner.official_price}
        else:
            prior_asset_kwargs = {"official_price": req.land_value_total / max(req.member_count, 1)}

        owner = OwnerInput(
            desired_unit=req.owner.desired_unit,
            appraisal_ratio=appraisal_ratio,
            **prior_asset_kwargs,
        )

        areas = calc_area(params)
        alloc = calc_allocation(params, areas)
        result = calc_contribution(params, alloc, owner)
        options = unit_options(params, alloc)

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

    #오류 발생시 Service Unavailable Exception 발생
    except Exception as err:
        logger.warning(f"[ Log ] : Contribution API 호출에서 오류 발생 : {str(err)}")
        raise ServiceUnavailableException("Contribution API 호출에서 오류가 발생했습니다.")

    #모든 계산 결과를 검증한 뒤에만 크레딧을 차감한다
    result_payload = {
        **asdict(result),
        "unit_options": [asdict(o) for o in options],
        "member_count_range": asdict(member_range),
        "warnings": result.project.warnings,
    }
    response = ContributionResponse.model_validate(
        {**result_payload, "credits_remaining": 0}
    )
    credits_remaining = await consume_credit_token(int(user_id), req.credit_token)

    #검증된 응답 모델에 잔액만 반영해 FastAPI 응답 검증 실패로 인한 오차감을 차단
    return response.model_copy(update={"credits_remaining": credits_remaining})