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
from dotenv import load_dotenv
import os
import requests

#부동산 계산식 API 라우터 설정
router = APIRouter(
    prefix="/api/v1",
    tags=["RealEstate Engine"]
)

#환경 변수 로드
load_dotenv()
VWORLD_API_KEY = os.getenv("VWORLD_API_KEY")
DOMAIN = os.getenv("DOMAIN")

#부동산 계산식 API 라우터
def fetch_land_price_per_m2(pnu: str) -> int:
    try:
        url = "https://api.vworld.kr/ned/data/getIndvdLandPrice"
        params = {
            "key": VWORLD_API_KEY,
            "pnu": pnu,
            "format": "json"
        }
        response = requests.get(url, params=params, timeout=5)
        data = response.json()

        price_info = data.get("indvdLandPrices", {}).get("field", {})
        price = price_info.get("pblntfPclnd")
        
        return int(price) if price else 0
    except Exception as e:
        print(f"[Warning] get_land_price_per_m2 오류 (Price): {e}")
        return 0

#부동산 계산식 API 라우터
def fetch_land_characteristics(pnu: str) -> dict:
    default_data = {
        "area_m2": 300.0,
        "zoning": "제2종일반주거지역",
        "land_category": "대"
    }
    
    try:
        url = "https://api.vworld.kr/ned/data/getLandCharacteristics"
        params = {
            "key": VWORLD_API_KEY,
            "pnu": pnu,
            "format": "json",
            "domain": DOMAIN
        }
        response = requests.get(url, params=params, timeout=5)
        data = response.json()
        
        land_info = data.get("landCharacteristics", {}).get("field", {})
        
        if not land_info:
            return default_data

        area = float(land_info.get("lndpclAr", 300.0))
        zoning = land_info.get("prposArea1Nm") or land_info.get("prposArea1Cd") or "제2종일반주거지역"
        land_category = land_info.get("lndcgrNm") or land_info.get("lndcgrCode") or "대"
        
        return {
            "area_m2": area,
            "zoning": zoning,
            "land_category": land_category
        }
        
    except Exception as e:
        print(f"[Warning] V-World Land Characteristics API 오류 {pnu}: {e}")
        return default_data

#Pnus 정보를 바탕으로 구체적 정보를 받아오는 API
@router.post(
    "/zone",
    summary="구역 선택 및 요약 집계"
)
async def get_zone(req: ZoneRequest):
    try:
        parcels = []

        for p in req.pnus:
            land_data = fetch_land_characteristics(p)
            price = fetch_land_price_per_m2(p)
            
            parcels.append(
                ParcelInfo(
                    pnu=p, 
                    area_m2=land_data["area_m2"], 
                    land_price_per_m2=price, 
                    zoning=land_data["zoning"], 
                    land_category=land_data["land_category"]
                )
            )
        
        target_ym = req.target_ym or datetime.now().strftime("%Y-%m")
        zone = build_zone_summary(parcels)
        cost = predict_cost_per_pyeong(target_ym, region=zone.region)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"[Warning] 구역 데이터 집계 중 오류 발생: {str(e)}")

    return {
        "zone": asdict(zone),
        "far_base": zone.far_min,
        "sliders": build_sliders(zone, cost, req.household_count),
        "cost_prediction": asdict(cost),
    }


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
        
        owner = OwnerInput(
            desired_unit=req.owner.desired_unit,
            official_price=req.owner.official_price,
            appraisal_ratio=ENGINE_DEFAULTS["appraisal_ratio"],
        )

        areas = calc_area(params)
        alloc = calc_allocation(params, areas)
        result = calc_contribution(params, alloc, owner)
        options = unit_options(params, alloc)

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        print(f"[Warning] 조합원 개인 분담금 및 사업성 계산 중 오류 발생: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"[Warning] 서버 내부 오류: {str(e)}")

    return {
        **asdict(result),
        "unit_options": [asdict(o) for o in options],
        "warnings": result.project.warnings,
    }