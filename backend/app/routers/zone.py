from app.config.engine_defaults import (
    ENGINE_DEFAULTS, ENGINE_DEFAULTS_FOR_PARAMS, HOUSING_REALIZATION_RATES, MEMBER_COUNT_UNKNOWN_MIN_RATIO, UNIT_MIX,
)
from app.cache.redis import redis_client
from app.services.credit_service import ensure_daily_credit_available, get_daily_credits, issue_credit_token
from app.services.building_ledger_service import elapsed_years, fetch_apartment_complex, fetch_building
from app.services.zone_service import (
    get_cached_trades, set_cached_trades, get_cached_land, set_cached_land,
    get_cached_building, set_cached_building, get_cached_possession, set_cached_possession,
    get_cached_apartment, set_cached_apartment, get_cached_apartment_prices, set_cached_apartment_prices,
    get_cached_house_price, set_cached_house_price,
)
from app.schemas.realestate.realestate_request import ZoneRequest, ContributionRequest
from app.schemas.realestate.realestate_response import ProjectTypeResponse, ZoneResponse
from app.utils.slider_builder import build_sliders
from app.exceptions.exceptions_handler import BadRequestException, ServiceUnavailableException, UnauthorizedException
from AI.engine.prior_asset import ParcelValuation, aggregate_zone, building_cost_index, is_public_owner, ordinance_member_count
from AI.engine.schema import (
    PER_PYEONG_TO_PER_M2, ParcelInfo, ProjectType, UnitMix, OwnerInput, ProjectParams, UnitType,
)
from AI.engine.zone import (
    FAR_TIERS, SELECTABLE_ZONING, base_zoning, build_zone_summary, business_correction_factor, far_plan,
    normalize_zoning, reconstruction_correction_factor, upzoning,
)
from AI.engine.project_type import RECONSTRUCTION, ParcelUse, classify_project, is_apartment
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
import statistics
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

#실거래 신고가 끝난 달만 쓴다 — 신고 기한이 계약 후 30일이라(부동산 거래신고 등에 관한 법률 제3조)
#  이번 달·지난달 거래는 아직 덜 들어와 있다.
#  실측 (노원구, 2026-10 기준) : 2026-10 은 2건, 2026-09 는 176건(평소 500~900건).
#  이 두 달을 넣으면 월별 중앙값이 튀어 상승률이 월 +0.97% → −0.00% 로 꺾이고 분양가가 13% 낮게 나왔다
REPORTING_LAG_MONTHS = 2


#분양가 시점 보정용 실거래 목록
async def fetch_recent_trades(lawd_cd: str, target_ym: str) -> list:
    year, month = (int(v) for v in target_ym.split("-"))
    last = year * 12 + (month - 1) - REPORTING_LAG_MONTHS
    last_ym = f"{last // 12}-{last % 12 + 1:02d}"

    #Redis 캐시 조회. 예전 방식(목표월까지)으로 저장된 항목도 있어 신고 완료월까지만 남긴다
    cached = await get_cached_trades(lawd_cd, target_ym)

    #캐시로 있는 값이 존재한다면 해당 값 반환
    if cached is not None:
        return [t for t in cached if t.ym <= last_ym]

    #신고가 끝난 달부터 거슬러 TRADE_MONTHS 개월
    ym_list = []

    for step in range(TRADE_MONTHS):
        total = last - step
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

#건축물대장 조회 (캐시 경유)
#  종전자산의 건물분을 구하는 데 쓴다. 건물분이 없으면 개인·구역에 같은 배수가 들어가
#  분담금에서 약분되므로, 이 값이 개인별 차이를 만드는 유일한 입력이다.
#  실패하면 나대지로 떨어진다 (건물분 0 = 기존 동작) — 조용히 틀리지 않게 fallback 을 남긴다
async def fetch_building_cached(pnu: str) -> dict:
    cached = await get_cached_building(pnu)
    if cached:
        return cached

    #동기 호출이지만 기존 V-World 호출과 같은 방식이다 (건축HUB 는 병렬에 민감하다)
    ledger = fetch_building(pnu)
    data = asdict(ledger)

    #조회 자체가 실패한 경우는 캐시하지 않는다. 키 설정·일시 장애가 굳어버린다
    if not ledger.fallback:
        await set_cached_building(pnu, data)

    return data


#토지소유정보 조회 (캐시 경유) — 국·공유지를 종전자산·조합원 수에서 빼는 데 쓴다
#  필지 조회(fetch_land_characteristics)와 같은 프록시·세션을 쓰되 그 함수는 건드리지 않는다.
#  실패하면 소유구분을 모르는 채(빈 값) 둔다 — 그 필지는 예전처럼 사유지로 계산된다
#소유정보 동시 조회 수. 모든 필지를 조회하므로 첫 조회만 병렬로 당긴다 (캐시 30일).
#  V-World 프록시에 무리가 가지 않게 작게 둔다
POSSESSION_WORKERS = 4
possession_executor = ThreadPoolExecutor(max_workers=POSSESSION_WORKERS)

#소유정보는 소유자(지분)마다 한 행이다. 첫 행만 보면 공유·집합건물 대지권 필지를 잘못 가른다
#  실측 : 월계동 17 (미성아파트 부지, 건물은 13번지로 등록) 4,679행 중 첫 행이 '시 도유지' 지분이고
#  첫 1,000행 중 993행이 개인 → 첫 행만 보고 국공유로 빼서 구역 종전자산의 38%(4,827억)가 사라졌다.
#  그래서 앞의 몇 행을 표본으로 읽어, 소유자가 여럿이고 사유 지분이 섞여 있으면 가장 많은 사유 구분을 쓴다
POSSESSION_SAMPLE_ROWS = 20


def _request_possession(pnu: str) -> dict:
    time.sleep(VWORLD_CALL_GAP)
    response = VWORLD_SESSION.get(
        f"{PROXY_URL.rstrip('/')}/getPossessionAttr",
        params={
            "key": VWORLD_API_KEY,
            "pnu": pnu,
            "format": "json",
            "domain": VWORLD_DOMAIN,
            "numOfRows": POSSESSION_SAMPLE_ROWS,
            "pageNo": 1,
        },
        timeout=5,
    )
    possessions = parse_vworld_response(response, "getPossessionAttr").get("possessions", {})
    rows = possessions.get("field", [])
    if isinstance(rows, dict):
        rows = [rows]
    if not rows:
        return {"owner_type": "", "owner_code": "", "fallback": True}

    owner_count = int(possessions.get("totalCount") or len(rows))
    owners = [((r.get("posesnSeCodeNm") or "").strip(), (r.get("posesnSeCode") or "").strip()) for r in rows]
    #국공유로 보는 건 표본이 모두 국공유일 때뿐이다. 사유 지분이 하나라도 있으면 가장 많은 사유 구분을 쓴다
    private = [o for o in owners if not is_public_owner(o[0])]
    pool = private or owners
    owner_type, owner_code = max(set(pool), key=pool.count)
    #1997-01-15 전부터 지분을 가진 소유자 수 (소유권 변동일자 ownshipChgDe) — 다가구 가구별 분양대상자 판정 (조례 부칙 제28조제1항).
    #  변동일이 주소변경일인 행도 있어(원인 '주소변경') 실제 취득은 더 이를 수 있다 → 이 값은 하한이다
    before_1997 = sum(1 for r in rows if (r.get("ownshipChgDe") or "9999") < "1997-01-15")
    return {
        "owner_type": owner_type,
        "owner_code": owner_code,
        "owner_count": owner_count,
        "owners_before_1997": before_1997,
        "fallback": False,
    }


async def fetch_land_possession(pnu: str) -> dict:
    cached = await get_cached_possession(pnu)
    if cached:
        return cached

    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(possession_executor, _request_possession, pnu)
        if not result.get("fallback"):
            await set_cached_possession(pnu, result)
        return result

    except Exception as err:
        logger.warning(f"[ Log ] : V-World 토지소유정보 오류 {pnu}: {err}")
        return {"owner_type": "", "owner_code": "", "fallback": True}


#아파트 단지 정보 (캐시 경유) — 재건축 판정(부속지번)·조합원 수(총괄표제부 세대수)·현황용적률에 쓴다.
#  아파트 필지에만 부른다
async def fetch_apartment_complex_cached(pnu: str) -> dict:
    cached = await get_cached_apartment(pnu)
    if cached:
        return cached
    data = asdict(fetch_apartment_complex(pnu))
    if not data.get("fallback"):
        await set_cached_apartment(pnu, data)
    return data


#공동주택가격 요약 (V-World 프록시 getApartHousingPriceAttr) — 재건축 종전자산의 바탕
#  호별 공시가격(토지 + 건물)의 합계·호수·전용면적별 중앙값. 올해 공시가 없으면 작년 값
#  ※ 2024년부터 같은 호가 두 번씩 들어 있다 (실측 10세대 → 20행) → (단지, 동, 호, 전용면적) 으로 중복 제거
#  ※ 연도(stdrYear)를 꼭 건다. 안 걸면 2006년부터 전부 와서 미미삼은 98,250행이다
APT_PRICE_MAX_PAGES = 20
APT_PRICE_EMPTY = {"year": None, "unit_count": 0, "official_total": 0.0, "area_prices": [], "fallback": True}


def _request_apartment_prices(pnu: str) -> dict:
    this_year = datetime.now().year
    for year in (this_year, this_year - 1):
        units: dict[tuple, float] = {}
        for page in range(1, APT_PRICE_MAX_PAGES + 1):
            time.sleep(VWORLD_CALL_GAP)
            response = VWORLD_SESSION.get(
                f"{PROXY_URL.rstrip('/')}/getApartHousingPriceAttr",
                params={
                    "key": VWORLD_API_KEY,
                    "pnu": pnu,
                    "stdrYear": str(year),
                    "format": "json",
                    "domain": VWORLD_DOMAIN,
                    "numOfRows": 1000,
                    "pageNo": page,
                },
                timeout=10,
            )
            data = parse_vworld_response(response, "getApartHousingPriceAttr")
            root = next((v for v in data.values() if isinstance(v, dict) and "field" in v), {})
            rows = root.get("field", [])
            if isinstance(rows, dict):
                rows = [rows]
            for row in rows:
                if str(row.get("stdrYear")) != str(year):
                    continue
                unit = (row.get("aphusNm"), row.get("dongNm"), row.get("hoNm"), row.get("prvuseAr"))
                units[unit] = float(row.get("pblntfPc") or 0) / 10_000     # 원 → 만원
            if len(rows) < 1000:
                break
        if units:
            by_area: dict[float, list[float]] = {}
            for (_, _, _, area), price in units.items():
                by_area.setdefault(round(float(area or 0), 2), []).append(price)
            return {
                "year": year,
                "unit_count": len(units),
                "official_total": round(sum(units.values()), 1),
                "area_prices": [[a, round(statistics.median(v), 1), len(v)] for a, v in sorted(by_area.items())],
                "fallback": False,
            }
    return dict(APT_PRICE_EMPTY)


async def fetch_apartment_prices(pnu: str) -> dict:
    cached = await get_cached_apartment_prices(pnu)
    if cached:
        return cached
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(possession_executor, _request_apartment_prices, pnu)
        if not result.get("fallback"):
            await set_cached_apartment_prices(pnu, result)
        return result
    except Exception as err:
        logger.warning(f"[ Log ] : V-World 공동주택가격 오류 {pnu}: {err}")
        return dict(APT_PRICE_EMPTY)


#개별주택가격 (V-World 프록시 getIndvdHousingPriceAttr) — 재개발 구역의 단독·다가구 종전자산
#  올해 공시가 없으면 작년 값. 같은 해에 같은 행이 두 번 오기도 한다 (실측 2025년 2행) → (동, 건물 면적)으로 중복 제거
HOUSE_PRICE_EMPTY = {"year": None, "house_price": 0.0, "fallback": True}


def _request_house_price(pnu: str) -> dict:
    this_year = datetime.now().year
    for year in (this_year, this_year - 1):
        time.sleep(VWORLD_CALL_GAP)
        response = VWORLD_SESSION.get(
            f"{PROXY_URL.rstrip('/')}/getIndvdHousingPriceAttr",
            params={
                "key": VWORLD_API_KEY,
                "pnu": pnu,
                "stdrYear": str(year),
                "format": "json",
                "domain": VWORLD_DOMAIN,
                "numOfRows": 20,
                "pageNo": 1,
            },
            timeout=10,
        )
        data = parse_vworld_response(response, "getIndvdHousingPriceAttr")
        root = next((v for v in data.values() if isinstance(v, dict) and "field" in v), {})
        rows = root.get("field", [])
        if isinstance(rows, dict):
            rows = [rows]
        houses = {
            (row.get("dongCode"), row.get("buldSn"), row.get("buldAllTotAr")): float(row.get("housePc") or 0) / 10_000
            for row in rows if str(row.get("stdrYear")) == str(year)
        }
        if houses:
            return {"year": year, "house_price": round(sum(houses.values()), 1), "fallback": False}
    return dict(HOUSE_PRICE_EMPTY)


async def fetch_house_price(pnu: str) -> dict:
    cached = await get_cached_house_price(pnu)
    if cached:
        return cached
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(possession_executor, _request_house_price, pnu)
        if not result.get("fallback"):
            await set_cached_house_price(pnu, result)
        return result
    except Exception as err:
        logger.warning(f"[ Log ] : V-World 개별주택가격 오류 {pnu}: {err}")
        return dict(HOUSE_PRICE_EMPTY)


#주택 공시가격의 종류 : 공동주택(다세대·연립·아파트) → 공동주택가격, 단독주택(단독·다가구·다중) → 개별주택가격
def housing_kind_of(main_purpose: str) -> str:
    purpose = main_purpose or ""
    if "공동주택" in purpose:
        return "공동"
    if "단독주택" in purpose:
        return "단독"
    return ""


#사업 유형 미리 판정 — 필지를 고르는 즉시 선택한 필지 칸에 [ 재건축 ] / [ 재개발 ] 배지를 띄운다.
#  구역 분석(/zone)과 같은 입력·규칙(classify_project)으로 판정만 한다. 크레딧을 쓰지 않고(로그인만 확인),
#  조회 함수는 모두 /zone 과 같은 캐시(소유정보·토지특성·건축물대장·단지 부속지번)를 쓰므로 분석 때 다시 부르지 않는다.
#  /zone 의 판정이 최종이다 — 이 값은 분석 전 미리보기다
@router.post(
    "/zone/type",
    response_model = ProjectTypeResponse,
    summary = "사업 유형 미리 판정 (크레딧 없음)"
)
async def get_project_type(req: ZoneRequest, request: Request):
    if request.session.get("user_id") is None:
        raise UnauthorizedException("로그인이 필요합니다.")
    hints = {h.pnu: h for h in (req.parcels or [])}
    owners = dict(zip(req.pnus, await asyncio.gather(*(fetch_land_possession(p) for p in req.pnus))))
    uses = []
    for p in req.pnus:
        land_data = await fetch_land_characteristics(p)
        hint = hints.get(p)
        bld = await fetch_building_cached(p)
        uses.append(
            ParcelUse(
                pnu=p,
                has_building=bool(bld.get("has_building")),
                main_purpose=bld.get("main_purpose") or "",
                etc_purpose=bld.get("etc_purpose") or "",
                floors=int(bld.get("floors") or 0),
                owner_type=owners.get(p, {}).get("owner_type", ""),
                land_category=land_data["land_category"],
                land_area_m2=hint.area_m2 if hint and hint.area_m2 else land_data["area_m2"],
            )
        )
    apartment_pnus = [u.pnu for u in uses if u.has_building and is_apartment(u.main_purpose, u.etc_purpose, u.floors)]
    complexes = [await fetch_apartment_complex_cached(pnu) for pnu in apartment_pnus]
    annex = {a for c in complexes for a in (c.get("annex_pnus") or [])}
    kind = classify_project(uses, annex)
    return ProjectTypeResponse(project_type=kind.project_type, project_type_reason=kind.reason)


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

        #건축물대장 수집용. 종전자산 토지분+건물분과 조합원 수 실측에 쓴다
        valuations = []
        ledger_failed = []
        #재개발/재건축 판정용 (주용도·기타용도·층수·소유구분·지목)
        uses = []

        #토지 소유구분 : 국·공유지는 조합원 자산이 아니다 → 모든 필지를 조회한다.
        #  주택·근생 건물이 있는 대지도 국공유일 수 있어 거르지 않는다.
        #  첫 조회만 느리고(캐시 30일) 그것도 동시 POSSESSION_WORKERS 개로 당긴다
        owners = dict(zip(req.pnus, await asyncio.gather(*(fetch_land_possession(p) for p in req.pnus))))

        #필지의 원래 용도지역과 면적. 사용자가 용도지역을 골라도 덮어쓰지 않은 값이다
        #  → 종상향 판정의 기준(가장 평균되는 용도지역)을 여기서 만든다.
        #  조회에 실패해 제2종일반주거로 가정된 필지는 기준을 왜곡하므로 뺀다
        original_zonings = []

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
            if not land_data.get("fallback"):
                original_zonings.append((land_data["zoning"], area_m2))

            parcels.append(
                ParcelInfo(
                    pnu=p,
                    area_m2=area_m2,
                    land_price_per_m2=price,
                    zoning=zoning,
                    land_category=land_data["land_category"]
                )
            )

            #건축물대장 : 종전자산 건물분 + 조합원 수 실측에 쓴다
            bld = await fetch_building_cached(p)
            if bld.get("fallback"):
                ledger_failed.append(p)

            owner_type = owners.get(p, {}).get("owner_type", "")

            uses.append(
                ParcelUse(
                    pnu=p,
                    has_building=bool(bld.get("has_building")),
                    main_purpose=bld.get("main_purpose") or "",
                    etc_purpose=bld.get("etc_purpose") or "",
                    floors=int(bld.get("floors") or 0),
                    owner_type=owner_type,
                    land_category=land_data["land_category"],
                    land_area_m2=area_m2,
                )
            )

            valuations.append(
                ParcelValuation(
                    pnu=p,
                    land_area_m2=area_m2,
                    land_price_per_m2=price,
                    structure=bld.get("structure") or "",
                    building_area_m2=float(bld.get("floor_area_m2") or 0.0),
                    elapsed_years=float(bld.get("elapsed_years") or 0.0),
                    #조합원(분양대상자) 수 : 단독·다가구는 1명 (서울시 도시정비조례 제36조제2항제3호),
                    #  1997-01-15 전 가구별 지분 다가구만 가구별 (부칙 제28조제1항) — prior_asset.ordinance_member_count
                    household_count=ordinance_member_count(
                        bld.get("main_purpose") or "",
                        bld.get("approval_ymd") or "",
                        int(bld.get("household_count") or 1),
                        int(owners.get(p, {}).get("owner_count") or 0),
                        owners.get(p, {}).get("owners_before_1997"),
                    ),
                    has_building=bool(bld.get("has_building")),
                    land_category=land_data["land_category"],
                    #재조달원가 상대지수 (행안부 시가표준액 조정기준의 구조·용도지수, 아파트 = 1.0). 나대지는 쓰지 않는다
                    cost_index=building_cost_index(
                        bld.get("structure") or "",
                        bld.get("main_purpose") or "",
                        int(bld.get("floors") or 0),
                        bld.get("etc_purpose") or "",
                    ) if bld.get("has_building") else 1.0,
                    owner_type=owner_type,
                )
            )

        #주택 공시가격 : 주택 필지의 종전자산은 공시가격 ÷ 현실화율로 잡는다 (공동 69% · 단독 53.6%).
        #  나대지·근린생활시설 등은 지금처럼 토지 + 원가법. 첫 조회만 느리고(캐시 30일) 동시 POSSESSION_WORKERS 개로 당긴다
        kinds = {u.pnu: housing_kind_of(u.main_purpose) if u.has_building else "" for u in uses}
        housing_pnus = [p for p, k in kinds.items() if k]
        housing_prices = dict(zip(housing_pnus, await asyncio.gather(*(
            fetch_apartment_prices(p) if kinds[p] == "공동" else fetch_house_price(p) for p in housing_pnus
        ))))
        for v in valuations:
            info = housing_prices.get(v.pnu)
            if not info or info.get("fallback"):
                continue
            v.housing_kind = kinds[v.pnu]
            if v.housing_kind == "공동":
                v.housing_price = float(info.get("official_total") or 0.0)
                v.housing_units = int(info.get("unit_count") or 0)
            else:
                v.housing_price = float(info.get("house_price") or 0.0)

        target_ym = req.target_ym or datetime.now().strftime("%Y-%m")
        zone = build_zone_summary(parcels)

        #사용자가 용도지역을 직접 골랐으면 조회 실패는 용적률에 영향을 주지 않는다
        if failed_pnus and not req.zoning:
            zone.warnings.append(
                f"{len(failed_pnus)}개 필지의 용도지역을 불러오지 못해 제2종일반주거지역으로 가정했습니다. "
                "용적률이 실제와 다를 수 있습니다. 용도지역을 직접 선택하면 이 가정을 덮어씁니다."
            )

        #종상향 : 필지 원래 용도지역의 면적가중 평균 단계보다 높은 용도지역을 고르면 종상향으로 본다.
        #  최소 공공기여율은 서울시 2030 기본계획 표(1단계 10%, 1종→3종 20% 등)를 따른다.
        #  사용자가 용도지역을 고르지 않았으면 판정하지 않는다 (섞인 구역에서 대표값이 평균보다 높을 수 있다)
        base = base_zoning(original_zonings) if req.zoning else None
        upzone = upzoning(base, req.zoning)

        #사업성 보정계수 : 서울시 평균 공시지가(재개발) ÷ 구역 '대' 필지 면적가중평균 (1.00 ~ 2.00)
        #  허용용적률 인센티브(20%p)에 곱해져 허용·상한을 올린다 (서울시 정비사업 사업성 개선방안).
        #  필지 공시지가의 기준 년도 : 개별공시지가는 매년 5월 31일까지 결정·공시된다
        #  (부동산 가격공시에 관한 법률 시행령) → 6월부터는 올해 값, 그 전에는 작년 값이 최신이다
        now = datetime.now()
        parcel_year = now.year if now.month >= 6 else now.year - 1

        #사업 유형 : 아파트 단지(들)만 고르면 재건축, 아파트 외 사유 필지가 섞이면 재개발 (AI/engine/project_type.py).
        #  아파트 필지에만 총괄표제부·부속지번을 조회한다 (캐시 30일)
        apartment_pnus = [u.pnu for u in uses if u.has_building and is_apartment(u.main_purpose, u.etc_purpose, u.floors)]
        complexes = {pnu: await fetch_apartment_complex_cached(pnu) for pnu in apartment_pnus}
        annex = {a for c in complexes.values() for a in (c.get("annex_pnus") or [])}
        kind = classify_project(uses, annex)
        #건물이 하나도 없는 선택 : 아파트 단지는 건축물대장이 대표지번 한 곳에만 등록되기도 한다
        #  (월계동신 : 436번지 대지 1,245㎡ 에 864세대 전부, 동이 선 483·산190 에는 대장이 없다).
        #  그 지번을 빼고 고르면 단지로 인식하지 못하고 조합원·종전이 크게 틀린다 → 안내만 한다
        if not any(u.has_building for u in uses) and any(u.land_category in ("대", "임야") for u in uses):
            zone.warnings.append(
                "고른 필지에 건축물대장이 없습니다. 아파트 단지라면 대장이 단지의 대표지번 한 곳에 등록돼 있을 수 있어, "
                "그 필지도 함께 골라야 단지로 인식됩니다."
            )

        reconstruction = None
        current_far = None
        if kind.project_type == RECONSTRUCTION:
            #재건축 단지 = 아파트 필지 + 부속지번. 대지면적·현황용적률·조합원 수·종전자산(공동주택가격)을 여기서 모은다
            complex_pnus = set(kind.apartment_pnus) | set(kind.annex_pnus)
            complex_parcels = [p for p in parcels if p.pnu in complex_pnus]
            complex_land = sum(p.area_m2 for p in complex_parcels)
            #조합원 수 = 총괄표제부 세대수 (없으면 표제부 합계)
            households = sum(int(c.get("households") or 0) for c in complexes.values()) or sum(
                v.household_count for v in valuations if v.pnu in kind.apartment_pnus
            )
            #현황용적률 = 용적률 산정 연면적 ÷ 단지 대지면적 (재건축 과밀단지 판정, 세부기준 "건축물대장상 주택단지의 용적률")
            far_area = sum(float(c.get("far_area_m2") or 0) for c in complexes.values())
            current_far = far_area / complex_land * 100 if complex_land > 0 and far_area > 0 else None

            prices = [await fetch_apartment_prices(pnu) for pnu in kind.apartment_pnus]
            merged: dict[float, list] = {}
            for price in prices:
                for area, median_price, count in price.get("area_prices") or []:
                    slot = merged.setdefault(float(area), [0.0, 0])
                    slot[0] += median_price * count
                    slot[1] += count
            #상가 등 비주거 조합원 — 공동주택가격이 없어 토지 지분(연면적 비율) + 건물 원가법으로 잡는다 (/contribution).
            #  재개발 근린생활시설과 같은 방법이다. 토지 지분은 대지권 대신 연면적 비율로 나눈다 (호별 대지권을 받지 않으므로)
            shop_units = sum(int(c.get("commercial_units") or 0) for c in complexes.values())
            commercial = None
            if shop_units:
                shop_area = sum(float(c.get("commercial_floor_area_m2") or 0) for c in complexes.values())
                total_area = sum(float(c.get("total_floor_area_m2") or 0) for c in complexes.values())
                main_shop = max(complexes.values(), key=lambda c: float(c.get("commercial_floor_area_m2") or 0))
                structure = main_shop.get("commercial_structure") or ""
                commercial = {
                    "units": shop_units,
                    "floor_area_m2": round(shop_area, 1),
                    "land_share_m2": round(complex_land * shop_area / total_area, 1) if total_area > 0 else 0.0,
                    "land_price_per_m2": round(
                        sum(p.area_m2 * p.land_price_per_m2 for p in complex_parcels) / complex_land
                    ) if complex_land > 0 else 0,
                    "structure": structure,
                    "elapsed_years": round(elapsed_years(main_shop.get("commercial_approval_ymd") or ""), 2),
                    "cost_index": building_cost_index(structure, "근린생활시설"),
                }

            reconstruction = {
                #조합원 = 아파트 세대 + 상가 등 비주거 호수 (미미삼 3,930 + 105 — 추진위 토지등소유자 3,986 과 +1.2%)
                "members": households + shop_units,
                "commercial": commercial,
                "households": households,
                "site_area_m2": round(complex_land, 1),
                "current_far": round(current_far, 1) if current_far else None,
                "official_year": max((p.get("year") or 0) for p in prices) or None,
                "unit_count": sum(int(p.get("unit_count") or 0) for p in prices),
                "official_total": round(sum(float(p.get("official_total") or 0) for p in prices), 1),
                #전용면적별 호당 공시가격 (만원) — 조합원이 전유면적을 넣으면 그 면적의 값으로 종전자산을 잡는다
                "area_prices": [[a, round(v[0] / v[1], 1), v[1]] for a, v in sorted(merged.items()) if v[1]],
                "annex_pnus": kind.annex_pnus,
            }
            if any(p.get("fallback") for p in prices):
                zone.warnings.append(
                    "공동주택가격을 불러오지 못한 단지가 있어 재건축 종전자산이 과소할 수 있습니다."
                )

            #재건축 보정계수 = 서울시 공동주택 평균 공시지가 ÷ 단지 평균 + α(대지면적) + β(세대밀도)
            #  β 의 "가용 용적률" = (기본계획 허용(보정 전) + 법적상한) ÷ 2 (zone.reconstruction_correction_factor 근거)
            tiers = FAR_TIERS.get(normalize_zoning(zone.zoning or ""))
            correction = reconstruction_correction_factor(
                [(p.land_category, p.area_m2, p.land_price_per_m2) for p in complex_parcels],
                parcel_year=parcel_year,
                site_area_m2=complex_land,
                households=households,
                available_far=(float(tiers[1]) + float(tiers[3])) / 2 if tiers else float(zone.far_max),
            )
        else:
            correction = business_correction_factor(
                [(p.land_category, p.area_m2, p.land_price_per_m2) for p in parcels],
                parcel_year=parcel_year,
            )

        #용적률 계획 : 4단 + 보정계수 + 종상향 + 노드별 상한용적률 공공기여(토지).
        #  재건축은 현황용적률을 넘겨 과밀단지면 현황을 허용용적률로 인정한다
        plan = far_plan(zone.zoning, zone.far_min, zone.far_max, correction.factor, base_zoning=base,
                        current_far=current_far)
        if plan.note:
            zone.warnings.append(plan.note)

        #공사비와 분양가는 같은 시점으로 예측한다. 시점이 어긋나면 비례율이 크게 왜곡된다
        cost = predict_cost_per_pyeong(target_ym, region=zone.region)

        #분양가 : 인근 분양 사례 + 실거래 추세 보정 (PNU 앞 5자리 = 시군구 코드)
        lawd_cd = zone.pnus[0][:5] if zone.pnus else ""
        trades = await fetch_recent_trades(lawd_cd, target_ym) if lawd_cd else []
        sale = predict_sale_price_per_m2(target_ym, trades=trades, region=zone.region)

        #종전자산 = 토지분 + 건물분. 구역 전수로 합산한다.
        #  재조달원가는 공사비 예측값을 쓴다 — 감정평가 실무기준이 재조달원가를
        #  "기준시점에 재생산하는 데 필요한 적정원가" 로 정의하기 때문이다.
        #  (지방세 건물신축가격기준액은 과세용 보수값이라 쓰지 않는다)
        replacement_cost_per_m2 = cost.cost_per_pyeong * PER_PYEONG_TO_PER_M2
        prior = aggregate_zone(
            valuations,
            land_multiplier=ENGINE_DEFAULTS["appraisal_ratio"],
            replacement_cost_per_m2=replacement_cost_per_m2,
            housing_rates=HOUSING_REALIZATION_RATES,
        )

        #건축물대장을 못 받은 필지는 나대지로 떨어진다. 건물분이 빠지면 분담금이
        #구역 평균값으로만 나오므로(약분) 반드시 알려준다
        if ledger_failed:
            zone.warnings.append(
                f"{len(ledger_failed)}개 필지의 건축물대장을 불러오지 못해 건물분을 0 으로 두었습니다. "
                "그 필지는 나대지로 계산됩니다."
            )
        zone.warnings.extend(prior.warnings)

    #오류 발생시 Service Unavailable Exception 발생
    except Exception as e:
        raise ServiceUnavailableException(f"Zone API 호출에서 오류 발생.")

    result = {
        "zone": asdict(zone),
        #제54조 임대 의무의 기준점 = 정비계획 상한용적률 (보정계수 반영).
        #  도시정비법 제54조④ 초과용적률 = 법적상한용적률 − 정비계획으로 정하여진 용적률.
        #  기준~상한은 정비계획이 정한 용적률이라 임대 의무가 없고, 상한을 넘는 법적상한 구간에만 붙는다.
        #  ※ #67 에서는 기준용적률을 넣었다 — 조문을 잘못 읽어 기준→허용→상한 구간에도
        #    임대 의무가 붙었고, 그래서 용적률을 올려도 분담금이 거의 움직이지 않았다 (2026-10-07 정정)
        "far_base": plan.ceiling,
        "target_ym": target_ym,
        #프론트 용도지역 버튼 목록. 엔진 FAR_TABLE 과 어긋나지 않게 서버가 내려준다
        "zoning_options": SELECTABLE_ZONING,
        "selected_zoning": req.zoning,
        "sliders": build_sliders(
            zone, cost, req.household_count, project_type=kind.project_type, sale=sale,
            #재건축 조합원 수 = 총괄표제부 세대수 + 상가 호수 (표제부 세대 합계·부속지번 필지 수가 섞이지 않게)
            measured_member_count=(
                reconstruction["members"] if reconstruction and reconstruction["members"]
                #건축물대장으로 센 실측값을 쓴다 (원가법 건물 필지든 주택 공시가격 필지든 대장을 받은 필지가 있으면)
                else (prior.member_count if (prior.building_parcel_count or prior.housing_parcel_count) else None)
            ),
            far=plan,
        ),
        #사업 유형 판정 (선택한 필지 칸 옆에 표시) — 재건축이면 단지 정보를 /contribution 에 그대로 돌려보낸다
        "project_type": kind.project_type,
        "project_type_reason": kind.reason,
        "reconstruction": reconstruction,
        #사업성 보정계수와 종상향 판정 (프론트 안내문용).
        #  실제 공공기여율은 용적률 노드마다 다르다 → sliders.floor_area_ratio.contributions
        "business_correction": asdict(correction),
        "upzoning": asdict(upzone),
        "cost_prediction": asdict(cost),
        "sale_prediction": asdict(sale),
        #종전자산(토지분+건물분)과 실측 조합원 수.
        #  필지별 원자료(parcels)를 같이 내려준다. /contribution 이 사업기간만큼 민
        #  평가시점(사업시행인가)으로 다시 집계해야 하는데, 건물은 그때까지 더 낡고
        #  재조달원가는 오른다. 두 효과의 상쇄 정도가 구조마다 달라(철근콘크리트 −4.6%,
        #  잔가율 하한에 붙은 벽돌 +46%) 구역 평균 한 배수로는 뭉갤 수 없다.
        #  프론트가 이 목록을 그대로 /contribution 에 돌려보내면 API 추가 호출이 없다
        "prior_asset": {
            "land_total": round(prior.land_total, 1),
            "building_total": round(prior.building_total, 1),
            "total": round(prior.total, 1),
            "official_total": round(prior.official_total, 1),
            "housing_total": round(prior.housing_total, 1),
            "housing_parcel_count": prior.housing_parcel_count,
            "ratio": round(prior.ratio, 4),
            "member_count": prior.member_count,
            "parcel_count": prior.parcel_count,
            "building_parcel_count": prior.building_parcel_count,
            "replacement_cost_per_m2": round(replacement_cost_per_m2, 2),
            "parcels": [
                {
                    "pnu": v.pnu,
                    "land_area_m2": round(v.land_area_m2, 2),
                    "land_price_per_m2": v.land_price_per_m2,
                    "structure": v.structure,
                    "building_area_m2": round(v.building_area_m2, 2),
                    "elapsed_years": round(v.elapsed_years, 2),
                    "household_count": v.household_count,
                    "has_building": v.has_building,
                    "land_category": v.land_category,
                    "cost_index": round(v.cost_index, 4),
                    "owner_type": v.owner_type,
                    #주택 공시가격 (있으면 종전자산 = 공시가격 ÷ 현실화율). 공동은 전용면적별 호당 값도 — 내 호 고를 때
                    "housing_kind": v.housing_kind,
                    "housing_price": v.housing_price,
                    "housing_units": v.housing_units,
                    "housing_area_prices": (housing_prices.get(v.pnu) or {}).get("area_prices") if v.housing_kind == "공동" else None,
                }
                for v in valuations
            ],
        },
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