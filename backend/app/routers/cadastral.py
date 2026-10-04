from fastapi import APIRouter, HTTPException
import httpx
import os
from app.schemas.cadastral.cadastral_request import CadastralRequest
from urllib.parse import urlencode
from app.exceptions.exceptions_handler import BadRequestException, ServiceUnavailableException
import logging

#필지 데이터 반환 API 라우터 설정
router = APIRouter(
    prefix="/api/v1",
    tags=["Cadastral Engine"]
)

#백엔드 Logger
logger = logging.getLogger(__name__)

#필지 데이터 반환 API 엔드포인트
@router.post("/cadastral")
async def get_vworld_cadastral(request: CadastralRequest):

    #환경변수 불러오기
    VWORLD_API_KEY = os.getenv("VWORLD_API_KEY")
    VWORLD_DOMAIN = os.getenv("VWORLD_DOMAIN")
    PROXY_URL = os.getenv("PROXY_URL")

    #환경변수 불러오기 실패시 오류 발생
    if not VWORLD_API_KEY:
        raise BadRequestException("VWORLD_API_KEY 환경 변수가 설정되지 않았습니다.")
    if not VWORLD_DOMAIN:
        raise BadRequestException("VWORLD_DOMAIN 환경 변수가 설정되지 않았습니다.")
    if not PROXY_URL:
        raise BadRequestException(="PROXY_URL 환경 변수가 설정되지 않았습니다.")

    #요청값에서 geom_filter 추출
    geom_filter = request.geom_filter

    #BBOX 값 형식에 맞게 조정
    try:
        min_lng, min_lat, max_lng, max_lat = (
            value.strip() for value in geom_filter[geom_filter.index("(") + 1: geom_filter.rindex(")")].split(",")
        )
        box_str = f"BOX({min_lng},{min_lat},{max_lng},{max_lat})"
    except (ValueError, IndexError) as err:
        raise BadRequestException("geom_filter 는 BOX(경도,위도,경도,위도) 형식이어야 합니다.")

    #V-World 필지 호출용 쿼리 파라미터 설정
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

    #프록시 URL 필지 설정용으로 변경
    PROXY_URL = f"{PROXY_URL.rstrip('/')}/req/data"
    
    #딕셔너리를 안전한 URL 인코딩 쿼리 스트링으로 변환
    target_call_url = f"{PROXY_URL}?{urlencode(query_params)}"
    
    #비동기 API 호출
    async with httpx.AsyncClient(verify=False) as client:
        try:
            #완성된 전체 URL로 직접 GET 요청
            response = await client.get(target_call_url, timeout=5.0)
            api_data = response.json()

            #API 성공여부 로깅
            logger.warning(f"[ Log ] : Cadastral API 호출 성공 {box_str}")

            #원하는 형식에 맞게 결과 반환
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
        
        #오류 발생시 Service Unavailable Exception 발생
        except Exception as err:
            logger.warning(f"[ Log ] : Cadastral API 호출 실패 : {str(err)}")
            ServiceUnavailableException("Cadastral API 요청중 오류가 발생했습니다.")
            return None