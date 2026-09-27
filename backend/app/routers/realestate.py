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

#부동산 계산식 API 라우터 설정
router = APIRouter(
    prefix="/api/v1",
    tags=["RealEstate Engine"]
)

#환경 변수 로드
load_dotenv()
VWORLD_API_KEY = os.getenv("VWORLD_API_KEY")
DOMAIN = os.getenv("DOMAIN")

#V-World 데이터 API 세션
#  필지마다 한 번씩 순차 호출하므로 커넥션을 재사용한다
#  연속 호출을 하면 서버가 응답 없이 연결을 끊는다(RemoteDisconnected)
#  실측(필지 60개): 재시도 2회 → 7건 실패 / 재시도 4회 + 호출 간격 0.05초 → 0건 실패, 6.5초
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

#실거래 캐시. 시군구·기간이 같으면 다시 부르지 않는다 (월별로 1회씩 호출해야 해서 느리다)
_TRADE_CACHE: dict[tuple[str, str], list] = {}


#분양가 시점 보정용 실거래 목록
#  MOLIT_API_KEY 가 없거나 조회가 실패하면 빈 목록을 돌려준다 (분양 사례만으로 계산된다)
def fetch_recent_trades(lawd_cd: str, target_ym: str) -> list:
    if not os.getenv("MOLIT_API_KEY"):
        return []

    cache_key = (lawd_cd, target_ym)
    if cache_key in _TRADE_CACHE:
        return _TRADE_CACHE[cache_key]

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

    _TRADE_CACHE[cache_key] = trades
    return trades


#필지 특성 캐시. 용도지역·면적·공시지가는 연 단위로만 바뀌므로 프로세스 수명 동안 재사용한다
#  같은 구역을 다시 선택할 때 호출이 0건이 되어 연결 끊김 자체가 줄어든다
#  실패한 응답은 캐시하지 않는다 (다음 요청에서 다시 시도해야 한다)
_LAND_CACHE: dict[str, dict] = {}

#부동산 계산식 API 라우터
def fetch_land_price_per_m2(pnu: str) -> int:
    try:
        url = "https://api.vworld.kr/ned/data/getIndvdLandPrice"
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
#  응답 구조 : {"landCharacteristicss": {"field": [연도별 이력, ...]}}
#    - 최상위 키는 landCharacteristicss (s 두 개)
#    - field 는 딕셔너리가 아니라 연도별 리스트라서 최신 stdrYear 를 골라야 한다
#    - 개별공시지가(pblntfPclnd)도 같은 응답에 들어 있어 따로 조회할 필요가 없다
def fetch_land_characteristics(pnu: str) -> dict:
    default_data = {
        "area_m2": 300.0,
        "zoning": "제2종일반주거지역",
        "land_category": "대",
        "land_price_per_m2": 0,
        "fallback": True,        #조회 실패 표시. 용도지역이 가정값이라 용적률이 왜곡된다
    }

    cached = _LAND_CACHE.get(pnu)
    if cached:
        return cached
    
    try:
        time.sleep(VWORLD_CALL_GAP)
        url = "https://api.vworld.kr/ned/data/getLandCharacteristics"
        params = {
            "key": VWORLD_API_KEY,
            "pnu": pnu,
            "format": "json",
            "domain": DOMAIN
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
        _LAND_CACHE[pnu] = result
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
            land_data = fetch_land_characteristics(p)

            #용도지역 조회가 실패하면 제2종일반주거로 가정된다. 용적률이 왜곡되므로 알려준다
            if land_data.get("fallback"):
                failed_pnus.append(p)

            area_m2 = hint.area_m2 if hint and hint.area_m2 else land_data["area_m2"]

            #공시지가 : 프론트가 보낸 값 → 토지특성 응답 → 개별공시지가 API 순서
            if hint and hint.land_price_per_m2:
                price = hint.land_price_per_m2
            else:
                price = land_data["land_price_per_m2"] or fetch_land_price_per_m2(p)

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
        trades = fetch_recent_trades(lawd_cd, target_ym) if lawd_cd else []
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
        #  land_value_total 은 면적 × 개별공시지가 합계(만원)라서 조합원 수로 나누면 1인 평균 공시가격이 된다
        #  토지분만 반영되므로 건물 가치는 appraisal_ratio 보정에 묻힌다 (6단계 회귀에서 분리 예정)
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