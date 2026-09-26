from dataclasses import asdict
from datetime import datetime
from fastapi import APIRouter, HTTPException, status
from typing import List, Optional
from app.config.engine_defaults import ENGINE_DEFAULTS, ENGINE_DEFAULTS_FOR_PARAMS, UNIT_MIX
from app.utils.slider_builder import build_sliders
from AI.engine.schema import ParcelInfo, ProjectType, UnitMix, OwnerInput, ProjectParams, UnitType
from AI.engine.zone import build_zone_summary
from AI.engine.calc import calc_allocation, calc_area, calc_contribution, calc_project, unit_options
from AI.predict.construction_cost import predict_cost_per_pyeong
from app.schemas.realestate.realestate_request import ZoneRequest, ContributionRequest

#부동산 계산식 API 라우터 설정
router = APIRouter(
    prefix="/api/v1",
    tags=["RealEstate Engine"]
)

#Pnus 정보를 바탕으로 구체적 정보를 받아오는 API
@router.post("/zone", summary="구역 선택 및 요약 집계")
async def get_zone(req: ZoneRequest):
    parcels = [
        ParcelInfo(pnu=p, area_m2=300.0, land_price_per_m2=3_800_000, zoning="제2종일반주거지역", land_category="대")
        for p in req.pnus
    ]
    
    #공사비 예측 기준 시점 : 요청값(착공 예상 연월)이 없으면 현재 연월
    target_ym = req.target_ym or datetime.now().strftime("%Y-%m")

    try:
        zone = build_zone_summary(parcels)
        cost = predict_cost_per_pyeong(target_ym, region=zone.region)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "zone": asdict(zone),
        #far_base : 임대 의무비율의 기준점. 슬라이더가 아니라 고정값이라 따로 내려준다
        "far_base": zone.far_min,
        "sliders": build_sliders(zone, cost, req.household_count),
        #cost_prediction : 공사비 슬라이더의 근거 (사례 수·지수·경고). 계산에는 쓰이지 않는다
        "cost_prediction": asdict(cost),
    }


#슬라이더 및 추가 변수들로 계산하는 API
@router.post("/contribution", summary="조합원 개인 분담금 및 사업성 계산")
async def get_contribution(req: ContributionRequest):
    try:
        params = ProjectParams(
            name=req.name,
            project_type=ProjectType.REDEVELOPMENT,
            site_area_m2=req.site_area_m2,
            member_count=req.member_count,
            unit_mix_list=[UnitMix(**m) for m in UNIT_MIX],
            far_base=req.far_base,          # 임대 의무비율 기준점 (ZoneSummary.far_min)
            **req.sliders,  # 프론트엔드 슬라이더 값 병합
            **ENGINE_DEFAULTS_FOR_PARAMS,
        )
        
        owner = OwnerInput(
            desired_unit=req.owner.desired_unit,
            official_price=req.owner.official_price,
            appraisal_ratio=ENGINE_DEFAULTS["appraisal_ratio"],
        )

        #세대수 배분은 엔진이 계산한다 (용적률에 따라 총·분양·임대 세대수가 함께 바뀜)
        areas = calc_area(params)
        alloc = calc_allocation(params, areas)

        result = calc_contribution(params, alloc, owner)
        options = unit_options(params, alloc)

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"서버 내부 오류: {str(e)}")

    return {
        **asdict(result),
        #평형 선택 버튼 목록 (이름·공급면적·세대수·조합원분양가)
        "unit_options": [asdict(o) for o in options],
        "warnings": result.project.warnings,
    }