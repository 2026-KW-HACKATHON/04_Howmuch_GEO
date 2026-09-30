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
from app.core.redis import redis_client
import json

#부동산 계산식 API 라우터 설정
router = APIRouter(
    prefix="/api/v1",
    tags=["RealEstate Engine"]
)

#환경 변수 로드
load_dotenv()
VWORLD_API_KEY = os.getenv("VWORLD_API_KEY")
VWORLD_DOMAIN = os.getenv("VWORLD_DOMAIN")
PROXY_URL = os.getenv("PROXY_URL")

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

#Redis 를 통한 Trade 캐시 불러오기
async def get_cached_trades(lawd_cd: str, target_ym: str) -> Optional[list]:
    if not redis_client:
        return None
    cache_key = f"trade:{lawd_cd}:{target_ym}"
    try:
        val = await redis_client.get(cache_key)
        print("[ Log ] : Get from cache")
        if val:
            return json.loads(val)
    except Exception as e:
        print(f"[Warning] Redis Read Error (Trade): {e}")
    return None

#Redis 를 통한 Trade 캐시 저장
async def set_cached_trades(lawd_cd: str, target_ym: str, trades: list):
    if not redis_client:
        return
    cache_key = f"trade:{lawd_cd}:{target_ym}"
    try:
        await redis_client.setex(cache_key, 86400, json.dumps(trades))
        print("[ Log ] : Save cache")
    except Exception as e:
        print(f"[Warning] Redis Write Error (Trade): {e}")

#분양가 시점 보정용 실거래 목록
async def fetch_recent_trades(lawd_cd: str, target_ym: str) -> list:
    if not os.getenv("MOLIT_API_KEY"):
        return []

    cached = await get_cached_trades(lawd_cd, target_ym)
    if cached is not None:
        return cached

    #target_ym 이전 TRADE_MONTHS 개월
    year, month = (int(v) for v in target_ym.split("-"))
    ym_list = []
    for step in range(TRADE_MONTHS):
        total = year * 12 + (month - 1) - step
        ym_list.append(f"{total // 12}-{total % 12 + 1:02d}")

    try:
        trades = fetch_trades(lawd_cd, ym_list)
    except Exception as e:
        print(f"[Warning] 실거래가 조회 실패 {lawd_cd}: {e}")
        return []

    set_cached_trades(lawd_cd, target_ym, trades)
    return trades

#Redis 를 통한 Land 캐시 불러오기
async def get_cached_land(pnu: str) -> Optional[dict]:
    if not redis_client:
        return None
    cache_key = f"land:{pnu}"
    try:
        val = await redis_client.get(cache_key)
        print("[ Log ] : Get from cache")
        if val:
            return json.loads(val)
    except Exception as e:
        print(f"[Warning] Redis Read Error (Land): {e}")
    return None

#Redis 를 통한 Land 캐시 저장하기
async def set_cached_land(pnu: str, data: dict):
    if not redis_client:
        return
    cache_key = f"land:{pnu}"
    try:
        await redis_client.setex(cache_key, 604800, json.dumps(data))
        print("[ Log ] : Save cache")
    except Exception as e:
        print(f"[Warning] Redis Write Error (Land): {e}")

#부동산 계산식 API 라우터
async def fetch_land_price_per_m2(pnu: str) -> int:
    try:
        url = PROXY_URL + "/ned/data/getIndvdLandPrice"

        params = {
            "key": VWORLD_API_KEY,
            "pnu": pnu,
            "format": "json"
        }
        
        response = VWORLD_SESSION.get(url, params=params, timeout=5)
        data = response.json()

        price_info = data.get("indvdLandPrices", {}).get("field", {})
        price = price_info.get("pblntfPclnd")
        
        return int(price) if price else 0
    except Exception as e:
        print(f"[Warning] get_land_price_per_m2 오류 (Price): {e}")
        return 0

#부동산 계산식 API 라우터
async def fetch_land_characteristics(pnu: str) -> dict:
    default_data = {
        "area_m2": 300.0,
        "zoning": "제2종일반주거지역",
        "land_category": "대",
        "land_price_per_m2": 0,
        "fallback": True,        #조회 실패 표시. 용도지역이 가정값이라 용적률이 왜곡된다
    }

    cached = await get_cached_land(pnu)
    if cached:
        return cached
    
    try:
        time.sleep(VWORLD_CALL_GAP)
        url = PROXY_URL + "/ned/data/getLandCharacteristics"
        params = {
            "key": VWORLD_API_KEY,
            "pnu": pnu,
            "format": "json",
            "domain": VWORLD_DOMAIN
        }
        response = VWORLD_SESSION.get(url, params=params, timeout=5)
        data = response.json()
        
        rows = data.get("landCharacteristicss", {}).get("field", [])
        if isinstance(rows, dict):
            rows = [rows]
        
        if not rows:
            return default_data

        #연도별 이력 중 최신 기준연도
        land_info = max(rows, key=lambda row: str(row.get("stdrYear", "")))

        area = float(land_info.get("lndpclAr") or 300.0)
        zoning = land_info.get("prposArea1Nm") or land_info.get("prposArea1Cd") or "제2종일반주거지역"
        land_category = land_info.get("lndcgrCodeNm") or land_info.get("lndcgrCode") or "대"
        price = int(float(land_info.get("pblntfPclnd") or 0))
        
        result = {
            "area_m2": area,
            "zoning": zoning,
            "land_category": land_category,
            "land_price_per_m2": price,
            "fallback": False,
        }
        set_cached_land(pnu, result)
        return result
        
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

        #프론트가 지적도에서 뽑아 보낸 면적·공시지가. 있으면 데이터 API 조회를 건너뛴다
        hints = {h.pnu: h for h in (req.parcels or [])}

        failed_pnus = []

        for p in req.pnus:
            hint = hints.get(p)
            land_data = await fetch_land_characteristics(p)

            #용도지역 조회가 실패하면 제2종일반주거로 가정된다. 용적률이 왜곡되므로 알려준다
            if land_data.get("fallback"):
                failed_pnus.append(p)

            area_m2 = hint.area_m2 if hint and hint.area_m2 else land_data["area_m2"]

            #공시지가 : 프론트가 보낸 값 → 토지특성 응답 → 개별공시지가 API 순서
            if hint and hint.land_price_per_m2:
                price = hint.land_price_per_m2
            else:
                price = land_data["land_price_per_m2"] or await fetch_land_price_per_m2(p)

            parcels.append(
                ParcelInfo(
                    pnu=p, 
                    area_m2=area_m2, 
                    land_price_per_m2=price, 
                    zoning=land_data["zoning"], 
                    land_category=land_data["land_category"]
                )
            )
        
        target_ym = req.target_ym or datetime.now().strftime("%Y-%m")
        zone = build_zone_summary(parcels)

        if failed_pnus:
            zone.warnings.append(
                f"{len(failed_pnus)}개 필지의 용도지역을 불러오지 못해 제2종일반주거지역으로 가정했습니다. "
                "용적률이 실제와 다를 수 있습니다."
            )

        #공사비와 분양가는 같은 시점으로 예측한다. 시점이 어긋나면 비례율이 크게 왜곡된다
        cost = predict_cost_per_pyeong(target_ym, region=zone.region)

        #분양가 : 인근 분양 사례 + 실거래 추세 보정 (PNU 앞 5자리 = 시군구 코드)
        lawd_cd = zone.pnus[0][:5] if zone.pnus else ""
        trades = await fetch_recent_trades(lawd_cd, target_ym) if lawd_cd else []
        sale = predict_sale_price_per_m2(target_ym, trades=trades, region=zone.region)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"[Warning] 구역 데이터 집계 중 오류 발생: {str(e)}")

    return {
        "zone": asdict(zone),
        "far_base": zone.far_min,
        "target_ym": target_ym,
        "sliders": build_sliders(zone, cost, req.household_count, sale=sale),
        "cost_prediction": asdict(cost),
        "sale_prediction": asdict(sale),
    }