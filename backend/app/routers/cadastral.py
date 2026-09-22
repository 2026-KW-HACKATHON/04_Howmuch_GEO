from fastapi import APIRouter, HTTPException
import httpx
import os
from app.routers.mock_data import MOCK_CADASTRAL_RESPONSE
from app.schemas.cadastral.cadastral_request import CadastralRequest

router = APIRouter(
    tags=["Cadastral"]
)

#Mock 필지 데이터 호출용 API
@router.post(
    "/cadastral/mock",
)
async def get_mock_cadastral():

    #대신 사용할 MOCK 데이터
    response = MOCK_CADASTRAL_RESPONSE

    return response


#Vworld 필지 데이터 호출용 API
@router.post(
    "/cadastral/vworld",
)
async def get_vworld_cadastral(request: CadastralRequest):

    #.env 에서 키값 Load
    api_key = os.getenv("VWORLD_API_KEY")
    domain = os.getenv("VWORLD_DOMAIN")
    vworld_wfs_url = os.getenv("VWORLD_WFS_URL")

    if not api_key:
        raise HTTPException(status_code=500, detail="VWORLD_API_KEY 가 설정되지 않았습니다.")

    if not domain:
        raise HTTPException(status_code=500, detail="VWORLD_DOMAIN 이 설정되지 않았습니다.")

    if not vworld_wfs_url:
        raise HTTPException(status_code=500, detail="VWORLD_WFS_URL 이 설정되지 않았습니다.")

    geom_filter = request.geom_filter

    #API 를 통하여 요청할 파라미터
    params = {
        "service": "data",
        "version": "2.0.0",
        "request": "GetFeature",
        "data": "lp_pa_cbnd_bubun",
        "typeName": "lp_pa_cbnd_bubun",
        "key": api_key,
        "domain": domain,
        "output": "json",
        "srsName": "EPSG:4326",
        "geomFilter": geom_filter,
        "size": "1000",
    }

    #비동기 API 호출부
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(vworld_wfs_url, params=params, timeout=10.0)
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code, 
                    detail=f"V-World API 응답 에러: {response.text}"
                )
            
            #API 를 통해 얻은 JSON 데이터 반환
            api_data = response.json()

            #React 프론트엔드에서 JSON 조회의 통일성을 위한 Response 형식 지정
            feature_collection = (
                api_data.get("response", {})
                .get("result", {})
                .get("featureCollection", api_data)
            )
            wrapped_response = {
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

            return wrapped_response
            
        except httpx.RequestError as e:
            raise HTTPException(status_code=500, detail=f"V-World API 통신 실패: {str(e)}")