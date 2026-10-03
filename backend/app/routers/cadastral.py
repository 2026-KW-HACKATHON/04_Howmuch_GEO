from fastapi import APIRouter, HTTPException
import httpx
import os
import traceback
from app.routers.mock_data import MOCK_CADASTRAL_RESPONSE
from app.schemas.cadastral.cadastral_request import CadastralRequest
from urllib.parse import urlencode

router = APIRouter(
    prefix="/api/v1",
    tags=["Cadastral Engine"]
)

@router.post("/cadastral")
async def get_vworld_cadastral(request: CadastralRequest):
    api_key = os.getenv("VWORLD_API_KEY")
    VWORLD_DOMAIN = os.getenv("VWORLD_DOMAIN")
    PROXY_URL = os.getenv("PROXY_URL") + "/req/data"

    if not api_key or not VWORLD_DOMAIN:
        return MOCK_CADASTRAL_RESPONSE

    geom_filter = request.geom_filter

    try:
        min_lng, min_lat, max_lng, max_lat = (
            value.strip() for value in geom_filter[geom_filter.index("(") + 1: geom_filter.rindex(")")].split(",")
        )
        box_str = f"BOX({min_lng},{min_lat},{max_lng},{max_lat})"
    except (ValueError, IndexError) as e:
        raise HTTPException(status_code=400, detail="geom_filter 는 BOX(경도,위도,경도,위도) 형식이어야 합니다.")

    query_params = {
        "service": "data",
        "request": "GetFeature",
        "data": "lp_pa_cbnd_bubun",
        "key": api_key,
        "domain": VWORLD_DOMAIN,
        "format": "json",
        "geomFilter": box_str,
        "epsg": "4326",
        "size": 1000
    }
    
    # 딕셔너리를 안전한 URL 인코딩 쿼리 스트링으로 변환
    target_call_url = f"{PROXY_URL}?{urlencode(query_params)}"
    
    async with httpx.AsyncClient(verify=False) as client:
        try:
            # 완성된 전체 URL로 직접 GET 요청 (타임아웃 15초로 넉넉하게)
            response = await client.get(target_call_url, timeout=15.0)
            
            if response.status_code != 200:
                return MOCK_CADASTRAL_RESPONSE
            
            api_data = response.json()

            if "response" in api_data and api_data["response"].get("status") == "NOT_FOUND":
                return MOCK_CADASTRAL_RESPONSE

            feature_collection = (
                api_data.get("response", {})
                .get("result", {})
                .get("featureCollection", api_data)
            )
            
            return {
                "response": {
                    "service": {
                        "name": "data",
                        "version": "2.0",
                        "operation": "GetFeature",
                        "time": "120(ms)"
                    },
                    "status": "OK",
                    "result": {
                        "featureCollection": feature_collection
                    }
                }
            }
            
        except Exception as err:
            print(f"[CRITICAL] 통신 또는 처리 중 예외 발생!")
            print(f"[Error Type]: {type(err).__name__}")
            print(f"[Error Message]: {str(err)}")
            traceback.print_exc()
            return MOCK_CADASTRAL_RESPONSE