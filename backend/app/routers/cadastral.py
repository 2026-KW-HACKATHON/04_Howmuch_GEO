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

    #WFS 엔드포인트는 geomFilter(= /req/data API 파라미터) 를 무시하고 bbox 를 받는다
    #  무시되면 화면 범위와 무관하게 전국 앞쪽 필지가 와서 지도에 아무것도 안 보인다
    #  프론트는 BOX(경도,위도,경도,위도) 로 보내지만 bbox 는 위도,경도 순서다
    try:
        min_lng, min_lat, max_lng, max_lat = (
            value.strip() for value in geom_filter[geom_filter.index("(") + 1: geom_filter.rindex(")")].split(",")
        )
        bbox = f"{min_lat},{min_lng},{max_lat},{max_lng},EPSG:4326"
    except (ValueError, IndexError):
        print(f"[Warning] get_vworld_cadastral geom_filter 형식 오류: {geom_filter}")
        raise HTTPException(status_code=400, detail="geom_filter 는 BOX(경도,위도,경도,위도) 형식이어야 합니다.")

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
        "bbox": bbox,
        "maxFeatures": "1000",
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