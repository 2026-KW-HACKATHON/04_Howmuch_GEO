from dataclasses import asdict
from datetime import datetime
from fastapi import APIRouter, HTTPException, status
from typing import List, Optional
from app.config.engine_defaults import ENGINE_DEFAULTS, ENGINE_DEFAULTS_FOR_PARAMS, MEMBER_COUNT_UNKNOWN_MIN_RATIO, UNIT_MIX
from app.utils.slider_builder import build_sliders
from AI.engine.schema import ParcelInfo, ProjectType, UnitMix, OwnerInput, ProjectParams, UnitType
from AI.engine.zone import build_zone_summary
from AI.engine.calc import MemberCountRange, calc_allocation, calc_area, calc_contribution, calc_project, member_count_range, unit_options
from AI.predict.construction_cost import predict_cost_per_pyeong
from AI.predict.sale_price import fetch_trades, predict_sale_price_per_m2
from app.schemas.realestate.realestate_request import ZoneRequest, ContributionRequest
from dotenv import load_dotenv
import os
import requests
import time
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import json

#부동산 계산식 API 라우터 설정
router = APIRouter(
    prefix="/api/v1",
    tags=["Contribution Engine"]
)

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
    summary="조합원 개인 분담금 및 사업성 계산")
async def get_contribution(req: ContributionRequest):
    try:
        params = ProjectParams(
            name=req.name,
            project_type=ProjectType.REDEVELOPMENT,
            site_area_m2=req.site_area_m2,
            member_count=req.member_count,
            unit_mix_list=[UnitMix(**m) for m in UNIT_MIX],
            far_base=req.far_base,
            **req.sliders,
            **ENGINE_DEFAULTS_FOR_PARAMS,
        )
        
        #조합원 종전자산 : 공시가격을 직접 받지 않으면 선택 구역 공시지가의 1인분으로 추정한다
        if req.owner.official_price is not None:
            prior_asset_kwargs = {"official_price": req.owner.official_price}
        elif req.land_value_total:
            prior_asset_kwargs = {"official_price": req.land_value_total / max(req.member_count, 1)}
        else:
            prior_asset_kwargs = {"appraisal_value": ENGINE_DEFAULTS["avg_prior_asset"]}

        owner = OwnerInput(
            desired_unit=req.owner.desired_unit,
            appraisal_ratio=ENGINE_DEFAULTS["appraisal_ratio"],
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

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        print(f"[Warning] 조합원 개인 분담금 및 사업성 계산 중 오류 발생: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"[Warning] 서버 내부 오류: {str(e)}")

    return {
        **asdict(result),
        "unit_options": [asdict(o) for o in options],
        #슬라이더를 다시 그릴 수 있게 갱신된 조합원 수 범위를 함께 내려준다
        "member_count_range": asdict(member_range),
        "warnings": result.project.warnings,
    }