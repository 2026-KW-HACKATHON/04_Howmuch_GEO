from dataclasses import asdict
from datetime import datetime
from fastapi import APIRouter, HTTPException, Request, status
from typing import Any, List, Optional
from app.config.engine_defaults import ENGINE_DEFAULTS, ENGINE_DEFAULTS_FOR_PARAMS, MEMBER_COUNT_UNKNOWN_MIN_RATIO, UNIT_MIX
from app.utils.slider_builder import build_sliders
from AI.engine.schema import ParcelInfo, ProjectType, UnitMix, OwnerInput, ProjectParams, UnitType
from AI.engine.zone import SELECTABLE_ZONING, build_zone_summary
from AI.engine.calc import MemberCountRange, calc_allocation, calc_area, calc_contribution, calc_project, member_count_range, unit_options
from AI.predict.construction_cost import predict_cost_per_pyeong
from AI.predict.sale_price import Trade, fetch_trades, predict_sale_price_per_m2
from app.schemas.realestate.realestate_request import ZoneRequest, ContributionRequest
from dotenv import load_dotenv
from dataclasses import is_dataclass, asdict
import os
import requests
import time
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from app.cache.redis import redis_client
from app.services.credit_service import consume_daily_credit, ensure_daily_credit_available
from app.services.zone_service import get_cached_trades, set_cached_trades, get_cached_land, set_cached_land
import json
import asyncio
from concurrent.futures import ThreadPoolExecutor
import logging

#스레드풀 생성
executor = ThreadPoolExecutor(max_workers=10)

logger = logging.getLogger(__name__)

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


if not PROXY_URL:
    raise ValueError("PROXY_URL 환경 변수가 설정되지 않았습니다.")

PROXY_URL = f"{PROXY_URL.rstrip('/')}/ned/data/"


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


def parse_vworld_response(response: requests.Response, api_name: str) -> dict[str, Any]:
    content_type = response.headers.get("Content-Type", "unknown")
    if not response.ok:
        raise ValueError(
            f"{api_name} returned HTTP {response.status_code} "
            f"(content-type={content_type}, bytes={len(response.content)})"
        )

    try:
        data = response.json()
    except requests.exceptions.JSONDecodeError as e:
        body_preview = " ".join(response.text.split())[:300]
        raise ValueError(
            f"{api_name} returned a non-JSON response "
            f"(HTTP {response.status_code}, content-type={content_type}, "
            f"bytes={len(response.content)}, body={body_preview!r})"
        ) from e
    if not isinstance(data, dict):
        raise ValueError(f"{api_name} returned JSON with an unexpected top-level type")
    return data


#호출 간격(초)
VWORLD_CALL_GAP = 0.05

#실거래 조회 기간(개월)
TRADE_MONTHS = 12

#분양가 시점 보정용 실거래 목록
async def fetch_recent_trades(lawd_cd: str, target_ym: str) -> list:
    cached = await get_cached_trades(lawd_cd, target_ym)
    if cached is not None:
        return cached

    if not os.getenv("MOLIT_API_KEY"):
        print(f"[Cache BYPASS] Trade API key missing ({lawd_cd}:{target_ym})")
        return []

    # target_ym 이전 TRADE_MONTHS 개월
    year, month = (int(v) for v in target_ym.split("-"))
    ym_list = []
    for step in range(TRADE_MONTHS):
        total = year * 12 + (month - 1) - step
        ym_list.append(f"{total // 12}-{total % 12 + 1:02d}")

    try:
        loop = asyncio.get_event_loop()
        trades = await loop.run_in_executor(executor, fetch_trades, lawd_cd, ym_list)
    except Exception as e:
        logger.warning(f"[Warning] 실거래가 조회 실패 {lawd_cd}: {e}")
        return []

    if trades:
        await set_cached_trades(lawd_cd, target_ym, trades)
    return trades

#부동산 계산식 API 라우터
async def fetch_land_price_per_m2(pnu: str) -> int:
    try:
        url = PROXY_URL + "getIndvdLandPrice"

        #numOfRows 를 주지 않으면 기본 10건만 와서 최신 연도가 잘린다.
        #  pageNo 가 없으면 numOfRows 가 무시되므로 둘을 함께 넘긴다
        params = {
            "key": VWORLD_API_KEY,
            "pnu": pnu,
            "format": "json",
            "domain": VWORLD_DOMAIN,
            "numOfRows": 30,
            "pageNo": 1,
        }
        logger.info(f"[Log] Fetching land price for PNU {pnu}")
        response = VWORLD_SESSION.get(url, params=params, timeout=5)
        data = parse_vworld_response(response, "getIndvdLandPrice")

        rows = data.get("indvdLandPrices", {}).get("field", [])
        if isinstance(rows, dict):
            rows = [rows]

        #연도별 이력이 오므로 가장 최근 기준연도를 쓴다
        price = None
        if rows:
            latest = max(rows, key=lambda row: str(row.get("stdrYear", "")))
            price = latest.get("pblntfPclnd")
        
        logger.info(f"[Log] Land Price for PNU {pnu} is {price}")
        return int(price) if price else 0
    except Exception as e:
        logger.warning(f"[Warning] get_land_price_per_m2 오류 (Price): {e}")
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
        url = PROXY_URL + "getLandCharacteristics"

        params = {
            "key": VWORLD_API_KEY,
            "pnu": pnu,
            "format": "json",
            "domain": VWORLD_DOMAIN,
            "numOfRows": 30,
            "pageNo": 1,
        }
        response = VWORLD_SESSION.get(url, params=params, timeout=5)
        data = parse_vworld_response(response, "getLandCharacteristics")
        
        rows = data.get("landCharacteristics", {}).get("field", [])
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
        await set_cached_land(pnu, result)
        return result
        
    except Exception as e:
        logger.warning(f"[Warning] V-World Land Characteristics API 오류 {pnu}: {e}")
        return default_data

#Pnus 정보를 바탕으로 구체적 정보를 받아오는 API
@router.post(
    "/zone",
    summary="구역 선택 및 요약 집계"
)
async def get_zone(req: ZoneRequest, request: Request):
    user_id = request.session.get("user_id")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="로그인이 필요합니다.",
        )
    await ensure_daily_credit_available(int(user_id))

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

            #용도지역 : 사용자가 고른 값이 있으면 그것을 전 필지에 적용한다.
            #  용적률 범위(far_min~far_max)가 여기서 정해지고, 그게 슬라이더 범위가 된다.
            #  조회값을 그대로 쓰면 한 구역에 여러 용도지역이 섞여 가중평균이 되는데,
            #  정비계획에서 용도지역을 새로 정하는 사업 성격과 맞지 않는다
            zoning = req.zoning or land_data["zoning"]

            parcels.append(
                ParcelInfo(
                    pnu=p,
                    area_m2=area_m2,
                    land_price_per_m2=price,
                    zoning=zoning,
                    land_category=land_data["land_category"]
                )
            )
        
        target_ym = req.target_ym or datetime.now().strftime("%Y-%m")
        zone = build_zone_summary(parcels)

        #사용자가 용도지역을 직접 골랐으면 조회 실패는 용적률에 영향을 주지 않는다
        if failed_pnus and not req.zoning:
            zone.warnings.append(
                f"{len(failed_pnus)}개 필지의 용도지역을 불러오지 못해 제2종일반주거지역으로 가정했습니다. "
                "용적률이 실제와 다를 수 있습니다. 용도지역을 직접 선택하면 이 가정을 덮어씁니다."
            )

        #공사비와 분양가는 같은 시점으로 예측한다. 시점이 어긋나면 비례율이 크게 왜곡된다
        cost = predict_cost_per_pyeong(target_ym, region=zone.region)

        #분양가 : 인근 분양 사례 + 실거래 추세 보정 (PNU 앞 5자리 = 시군구 코드)
        lawd_cd = zone.pnus[0][:5] if zone.pnus else ""
        print(f"[Check] lawd_cd 값: '{lawd_cd}' (Type: {type(lawd_cd)})")
        trades = await fetch_recent_trades(lawd_cd, target_ym) if lawd_cd else []
        sale = predict_sale_price_per_m2(target_ym, trades=trades, region=zone.region)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"[Warning] 구역 데이터 집계 중 오류 발생: {str(e)}")

    result = {
        "zone": asdict(zone),
        "far_base": zone.far_min,
        "target_ym": target_ym,
        #프론트 용도지역 버튼 목록. 엔진 FAR_TABLE 과 어긋나지 않게 서버가 내려준다
        "zoning_options": SELECTABLE_ZONING,
        "selected_zoning": req.zoning,
        "sliders": build_sliders(zone, cost, req.household_count, sale=sale),
        "cost_prediction": asdict(cost),
        "sale_prediction": asdict(sale),
    }
    result["credits_remaining"] = await consume_daily_credit(int(user_id))
    return result