from fastapi import APIRouter, HTTPException
import httpx
import os
from app.routers.mock_data import MOCK_CADASTRAL_RESPONSE
from app.schemas.cadastral_model.cadastral_request import CadastralRequest

#지적도 라우터 설정
router = APIRouter(
    prefix="/api/v1",
    tags=["Cadastral"]
)

#지적도 데이터 API 라우터
@router.post("/cadastral/")
async def get_vworld_cadastral(request: CadastralRequest):
    api_key = os.getenv("VWORLD_API_KEY")
    domain = os.getenv("DOMAIN")
    vworld_wfs_url = os.getenv("VWORLD_WFS_URL")

    if not api_key or not domain or not vworld_wfs_url:
        print("[Warning] V-World 환경 변수가 부족하여 Mock 데이터를 반환합니다.")
        return MOCK_CADASTRAL_RESPONSE

    geom_filter = request.geom_filter

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

    #V-World API 호출 및 응답 처리
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(vworld_wfs_url, params=params, timeout=10.0)
            
            if response.status_code != 200:
                print(f"[Warning] get_vworld_cadastral V-World API 통신 실패: {str(response.status_code)}")
                return MOCK_CADASTRAL_RESPONSE
            
            api_data = response.json()

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
            
        except (httpx.RequestError, httpx.TimeoutException) as err:

            #V-World API 통신 실패 시 Mock 데이터 반환
            print(f"[Warning] get_vworld_cadastral 통신 실패: {str(err)}")
            return MOCK_CADASTRAL_RESPONSE