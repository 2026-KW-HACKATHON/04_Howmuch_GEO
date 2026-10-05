from app.config.engine_defaults import ENGINE_DEFAULTS, ENGINE_DEFAULTS_FOR_PARAMS, MEMBER_COUNT_UNKNOWN_MIN_RATIO, UNIT_MIX
from app.cache.redis import redis_client
from app.services.credit_service import ensure_daily_credit_available, get_daily_credits, issue_credit_token
from app.services.zone_service import get_cached_trades, set_cached_trades, get_cached_land, set_cached_land
from app.schemas.realestate.realestate_request import ZoneRequest, ContributionRequest
from app.schemas.realestate.realestate_response import ZoneResponse
from app.utils.slider_builder import build_sliders
from app.exceptions.exceptions_handler import BadRequestException, ServiceUnavailableException, UnauthorizedException
from AI.engine.schema import ParcelInfo, ProjectType, UnitMix, OwnerInput, ProjectParams, UnitType
from AI.engine.zone import SELECTABLE_ZONING, build_zone_summary
from AI.engine.calc import MemberCountRange, calc_allocation, calc_area, calc_contribution, calc_project, member_count_range, unit_options
from AI.predict.construction_cost import predict_cost_per_pyeong
from AI.predict.sale_price import Trade, fetch_trades, predict_sale_price_per_m2
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from datetime import datetime
from dotenv import load_dotenv
from dataclasses import is_dataclass, asdict
from fastapi import APIRouter, HTTPException, Request, status
from requests.adapters import HTTPAdapter
from typing import Any, List, Optional
from urllib3.util.retry import Retry
import asyncio
import json
import logging
import os
import requests
import time

#스레드풀 생성
executor = ThreadPoolExecutor(max_workers=10)

#백엔드 Logger
logger = logging.getLogger(__name__)

#부동산 계산식 API 라우터 설정
router = APIRouter(
    prefix="/api/v1",
    tags=["RealEstate Engine"]
)

#환경 변수 로드
load_dotenv()

#환경 변수 가져오기
VWORLD_API_KEY = os.getenv("VWORLD_API_KEY")
VWORLD_DOMAIN = os.getenv("VWORLD_DOMAIN")
PROXY_URL = os.getenv("PROXY_URL")

#환경 변수 검증
if not VWORLD_API_KEY:
    raise ValueError("VWORLD_API_KEY 환경 변수가 설정되지 않았습니다.")
if not VWORLD_DOMAIN:
    raise ValueError("VWORLD_DOMAIN 환경 변수가 설정되지 않았습니다.")
if not PROXY_URL:
    raise ValueError("PROXY_URL 환경 변수가 설정되지 않았습니다.")

#PROXY_URL zone.py 용으로 변경 (/ned/data/)
PROXY_URL = f"{PROXY_URL.rstrip('/')}/ned/data/"

#V-World 데이터 API 세션 (재시도 설정)
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

#호출 간격(초)
VWORLD_CALL_GAP = 0.05

#실거래 조회 기간(개월)
TRADE_MONTHS = 12

#부동산 계산식 API 응답 파싱
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

#분양가 시점 보정용 실거래 목록
async def fetch_recent_trades(lawd_cd: str, target_ym: str) -> list:

    #Redis 캐시 조회
    cached = await get_cached_trades(lawd_cd, target_ym)

    #캐시로 있는 값이 존재한다면 해당 값 반환
    if cached is not None:
        return cached

    #target_ym 이전 TRADE_MONTHS 개월
    year, month = (int(v) for v in target_ym.split("-"))
    ym_list = []

    for step in range(TRADE_MONTHS):
        total = year * 12 + (month - 1) - step
        ym_list.append(f"{total // 12}-{total % 12 + 1:02d}")

    #fetch_trades 함수 호출 시도
    try:
        loop = asyncio.get_event_loop()
        trades = await loop.run_in_executor(executor, fetch_trades, lawd_cd, ym_list)

    #오류 발생시 로깅 후 빈 배열 반환
    except Exception as err:
        logger.warning(f"[ Log ] : 실거래가 조회 실패 {lawd_cd} : {err}")
        return []

    #호출 및 trades 데이터 반환 성공시, Redis 캐싱 후 값 반환
    if trades:
        await set_cached_trades(lawd_cd, target_ym, trades)

    return trades

#제곱미터당 땅 가격 조회 API 호출용 비동기 함수
async def fetch_land_price_per_m2(pnu: str) -> int:
    try:

        #API 요청을 위한 URL 설정
        url = f"{PROXY_URL.rstrip('/')}/getIndvdLandPrice"

        #요청 파라미터 설정
        params = {
            "key": VWORLD_API_KEY,
            "pnu": pnu,
            "format": "json",
            "domain": VWORLD_DOMAIN,
            "numOfRows": 30,
            "pageNo": 1,
        }

        #요청 전송
        logger.warning(f"[ Log ] : PNU : {pnu} 에 대한 가격을 조회중입니다.")
        response = VWORLD_SESSION.get(url, params=params, timeout=5)

        #응답 파싱
        data = parse_vworld_response(response, "getIndvdLandPrice")
        rows = data.get("indvdLandPrices", {}).get("field", [])

        #rows 데이터가 Dictionary 라면 배열화
        if isinstance(rows, dict):
            rows = [rows]

        #연도별 이력이 오므로 가장 최근 기준연도를 사용
        price = None
        if rows:
            latest = max(rows, key=lambda row: str(row.get("stdrYear", "")))
            price = latest.get("pblntfPclnd")
        
        logger.warning(f"[ Log ] : PNU : {pnu} 의 가격은 {price} 입니다.")

        #price 값이 존재한다면 반환. 없다면 0 반환.
        return int(price) if price else 0

    #API 오류 발생시 로깅 후 price 는 0 반환
    except Exception as err:
        logger.warning(f"[ Log ] : get_land_price_per_m2 API 호출에서 오류가 발생했습니다 : {str(err)}")
        return 0

#토지별 특성 정보 API 호출 비동기 함수
async def fetch_land_characteristics(pnu: str) -> dict:

    #기본값 데이터
    default_data = {
        "area_m2": 300.0,
        "zoning": "제2종일반주거지역",
        "land_category": "대",
        "land_price_per_m2": 0,
        "fallback": True,
    }

    #pnu 값으로 Redis 캐시값 조회
    cached = await get_cached_land(pnu)

    #캐시값이 존재한다면 해당 정보 반환
    if cached:
        return cached
    
    try:
        #일정 시간 대기
        time.sleep(VWORLD_CALL_GAP)

        #프록시 주소를 이용한 요청 URL 값 설정
        url = f"{PROXY_URL.rstrip('/')}/getLandCharacteristics"

        #요청 파라미터 설정
        params = {
            "key": VWORLD_API_KEY,
            "pnu": pnu,
            "format": "json",
            "domain": VWORLD_DOMAIN,
            "numOfRows": 30,
            "pageNo": 1,
        }

        #응답 요청
        response = VWORLD_SESSION.get(url, params=params, timeout=5)

        #응답값 파싱
        data = parse_vworld_response(response, "getLandCharacteristics")
        rows = data.get("landCharacteristicss", {}).get("field", [])

        #rows 가 Dictionary 라면 배열로 전환
        if isinstance(rows, dict):
            rows = [rows]
        
        #rows 가 없다면, 기본값 데이터 반환
        if not rows:
            return default_data

        #연도별 이력 중 최신 기준연도
        land_info = max(rows, key=lambda row: str(row.get("stdrYear", "")))

        #데이터에서 값 추출. 없다면 기본값 사용
        area = float(land_info.get("lndpclAr") or default_data["area_m2"])
        zoning = land_info.get("prposArea1Nm") or land_info.get("prposArea1Cd") or default_data["zoning"]
        land_category = land_info.get("lndcgrCodeNm") or land_info.get("lndcgrCode") or default_data["land_category"]
        price = int(float(land_info.get("pblntfPclnd") or default_data["land_price_per_m2"]))
        
        #결과 종합
        result = {
            "area_m2": area,
            "zoning": zoning,
            "land_category": land_category,
            "land_price_per_m2": price,
            "fallback": False,
        }

        #결과값 Redis 캐싱
        await set_cached_land(pnu, result)

        #결과값 반환
        return result
        
    except Exception as err:
        logger.warning(f"[ Log ] : V-World Land Characteristics API 오류 {pnu}: {err}")
        return default_data

#Pnus 정보를 바탕으로 구체적 정보를 받아오는 API
@router.post(
    "/zone",
    response_model = ZoneResponse,
    summary = "구역 선택 및 요약 집계"
)
async def get_zone(req: ZoneRequest, request: Request):

    #세션에서 user_id 반환
    user_id = request.session.get("user_id")

    #로그인이 안되있다면 Unauthorized Exception 발생
    if user_id is None:
        raise UnauthorizedException("로그인이 필요합니다.")

    #사용자 크레딧이 남아있는지 확인
    await ensure_daily_credit_available(int(user_id))

    try:
        parcels = []

        #프론트가 지적도에서 뽑아 보낸 면적·공시지가. 있으면 데이터 API 조회를 건너뜀
        hints = {h.pnu: h for h in (req.parcels or [])}

        failed_pnus = []

        for p in req.pnus:
            hint = hints.get(p)
            land_data = await fetch_land_characteristics(p)
            print(land_data)

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
        trades = await fetch_recent_trades(lawd_cd, target_ym) if lawd_cd else []
        sale = predict_sale_price_per_m2(target_ym, trades=trades, region=zone.region)

    #오류 발생시 Service Unavailable Exception 발생
    except Exception as e:
        raise ServiceUnavailableException(f"Zone API 호출에서 오류 발생.")

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

    #실제 차감은 /contribution 계산과 응답 검증이 성공한 후에 진행
    credits = await get_daily_credits(int(user_id))
    result["credits_remaining"] = credits["credits_remaining"]
    result["credit_token"] = "pending"
    response = ZoneResponse.model_validate(result)
    response = response.model_copy(
        update={"credit_token": await issue_credit_token(int(user_id))}
    )

    #결과 반환
    return response