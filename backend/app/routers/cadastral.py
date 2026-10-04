from fastapi import APIRouter, HTTPException
import httpx
import os
import traceback
from app.schemas.cadastral.cadastral_request import CadastralRequest
from urllib.parse import urlencode

#필지 데이터 반환 API 라우터 설정
router = APIRouter(
    prefix="/api/v1",
    tags=["Cadastral Engine"]
)

#필지 데이터 반환 API 엔드포인트
@router.post("/cadastral")
async def get_vworld_cadastral(request: CadastralRequest):

    #환경변수 불러오기
    VWORLD_API_KEY = os.getenv("VWORLD_API_KEY")
    VWORLD_DOMAIN = os.getenv("VWORLD_DOMAIN")
    PROXY_URL = os.getenv("PROXY_URL")

    #환경변수 불러오기 실패시 오류 발생
    if not VWORLD_API_KEY:
        raise HTTPException(status_code=500, detail="VWORLD_API_KEY 환경 변수가 설정되지 않았습니다.")
    if not VWORLD_DOMAIN:
        raise HTTPException(status_code=500, detail="VWORLD_DOMAIN 환경 변수가 설정되지 않았습니다.")
    if not PROXY_URL:
        raise HTTPException(status_code=500, detail="PROXY_URL 환경 변수가 설정되지 않았습니다.")

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
        "key": VWORLD_API_KEY,
        "domain": VWORLD_DOMAIN,
        "format": "json",
        "geomFilter": box_str,
        "epsg": "4326",
        "size": 1000
    }
    PROXY_URL = f"{PROXY_URL.rstrip('/')}/req/data"
    
    # 딕셔너리를 안전한 URL 인코딩 쿼리 스트링으로 변환
    target_call_url = f"{PROXY_URL}?{urlencode(query_params)}"
    
    async with httpx.AsyncClient(verify=False) as client:
        try:
            # 완성된 전체 URL로 직접 GET 요청 (타임아웃 15초로 넉넉하게)
            response = await client.get(target_call_url, timeout=5.0)
            
            print(response)
            if response.status_code != 200:
                return None
            
            api_data = response.json()

            if "response" in api_data and api_data["response"].get("status") == "NOT_FOUND":
                return None

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
            return None