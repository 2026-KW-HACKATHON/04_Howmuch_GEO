from dataclasses import asdict
from fastapi import APIRouter, HTTPException, status
from typing import List, Optional
from app.config.engine_defaults import ENGINE_DEFAULTS, ENGINE_DEFAULTS_FOR_PARAMS, UNIT_MIX
from app.utils.slider_builder import build_sliders
from AI.engine.schema import ParcelInfo, ProjectType, UnitMix, OwnerInput, ProjectParams, UnitType
from AI.engine.zone import build_zone_summary
from AI.engine.calc import calc_contribution, calc_project, calc_area, Allocation
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
    
    try:
        zone = build_zone_summary(parcels)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
        
    return {
        "zone": asdict(zone),
        "sliders": build_sliders(zone)
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
            **req.sliders,  # 프론트엔드 슬라이더 값 병합
            **ENGINE_DEFAULTS_FOR_PARAMS,
        )
        
        owner = OwnerInput(
            desired_unit=req.owner.desired_unit,
            official_price=req.owner.official_price,
            appraisal_ratio=ENGINE_DEFAULTS["appraisal_ratio"],
        )

        areas = calc_area(params)
        
        unit_types = []
        for mix in params.unit_mix_list:
            mix_supply_total = areas.supply_total_m2 * mix.share
            count = max(1, round(mix_supply_total / mix.supply_area_m2))
            unit_types.append(
                UnitType(
                    name=mix.name,
                    exclusive_area_m2=mix.exclusive_area_m2,
                    supply_area_m2=mix.supply_area_m2,
                    count=count
                )
            )

        total_units = sum(u.count for u in unit_types)
        rental_count = int(total_units * params.rental_ratio)
        sale_supply_m2 = sum(u.count * u.supply_area_m2 for u in unit_types)

        alloc = Allocation(
            unit_types=unit_types,
            rental_count=rental_count,
            sale_supply_m2=sale_supply_m2
        )

        result = calc_contribution(params, alloc, owner)

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"서버 내부 오류: {str(e)}")

    return {
        **asdict(result),
        "warnings": result.project.warnings,
    }