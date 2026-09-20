from fastapi import APIRouter, HTTPException
import os
from app.routers.mock_data import MOCK_CADASTRAL_RESPONSE

router = APIRouter(
    tags=["Cadastral"]
)

#AI 모델 예측 API (MOCK 데이터)
@router.post(
    "/cadastral",
)
async def cadastral():

    #.env 에서 키값 Load
    api_key = os.getenv("VWORLD_API_KEY")
    domain = os.getenv("VWORLD_DOMAIN")

    if not api_key:
        raise HTTPException(status_code=500, detail="VWORLD_API_KEY 가 설정되지 않았습니다.")

    if not domain:
        raise HTTPException(status_code=500, detail="VWORLD_DOMAIN 이 설정되지 않았습니다.")
    
    """
    =====================================================================
    현재 개발 환경상 VWorld 에서의 필지데이터 API 호출이 불가능하니 임시 주석처리
    =====================================================================


    #API 를 통하여 요청할 파라미터
    params = {
        "service": "data",
        "version": "2.0",
        "request": "GetFeature",
        "data": "LP_PA_CBND_BUBUN",
        "key": api_key,
        "domain": domain,
        "format": "json",
        "crs": "EPSG:4326",
        "geomFilter": geom_filter,
    }

    #비동기 API 호출부
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(VWORLD_DATA_URL, params=params, timeout=10.0)
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code, 
                    detail=f"V-World API 응답 에러: {response.text}"
                )
            
            #API 를 통해 얻은 JSON 데이터 반환
            return response.json()
            
        except httpx.RequestError as e:
            raise HTTPException(status_code=500, detail=f"V-World API 통신 실패: {str(e)}")
    """

    #대신 사용할 MOCK 데이터
    response = MOCK_CADASTRAL_RESPONSE

    return response