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

@router.post("/cadastral")
async def get_vworld_cadastral(request: CadastralRequest):
    api_key = os.getenv("VWORLD_API_KEY")
    domain = os.getenv("DOMAIN")
    proxy_url = os.getenv("PROXY_URL")

    # 1. 환경 변수 유효성 검사 및 로깅 보완
    if not api_key or not domain or not proxy_url:
        print(f"[Warning] 환경 변수 누락 -> API_KEY: {bool(api_key)}, DOMAIN: {bool(domain)}, PROXY_URL: {bool(proxy_url)}")
        return MOCK_CADASTRAL_RESPONSE

    # 2. ⚠️ URL 파라미터 중복 충돌 방지 처리
    # httpx.get() 호출 시 params 인자를 따로 전달하므로, 베이스 URL에는 절대로 쿼리 스트링(?나 경로)이 중복 조합되면 안 됩니다.
    base_proxy = proxy_url.rstrip("/")
    vworld_wfs_url = f"{base_proxy}/req/wfs" 

    geom_filter = request.geom_filter

    try:
        min_lng, min_lat, max_lng, max_lat = (
            value.strip() for value in geom_filter[geom_filter.index("(") + 1: geom_filter.rindex(")")].split(",")
        )
        bbox = f"{min_lat},{min_lng},{max_lat},{max_lng},EPSG:4326"
    except (ValueError, IndexError):
        print(f"[Warning] get_vworld_cadastral geom_filter 형식 오류: {geom_filter}")
        raise HTTPException(status_code=400, detail="geom_filter 는 BOX(경도,위도,경도,위도) 형식이어야 합니다.")

    # 3. 브이월드 규격에 맞는 파라미터 정의
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

    async with httpx.AsyncClient(verify=False) as client:
        try:
            # 최종 호출 로그 확인용 출력
            print(f"[Info] 호출 URL: {vworld_wfs_url}")
            print(f"[Info] 호출 파라미터: {params}")
            
            # ⚠️ 프록시는 SSL이 없으므로 httpx가 내부 검증 절차를 거치지 않도록 verify=False를 추가하는 것이 안전합니다.
            response = await client.get(vworld_wfs_url, params=params, timeout=10.0)
            
            if response.status_code != 200:
                print(f"[Warning] 프록시 통신 실패 (상태 코드: {response.status_code})")
                print(f"[Detail] 응답 내용: {response.text}")
                return MOCK_CADASTRAL_RESPONSE
            
            api_data = response.json()

            # 4. 브이월드 자체 인증 실패 레이아웃 잡아내기
            if "response" in api_data and api_data["response"].get("status") == "NOT_FOUND":
                print(f"[Warning] 브이월드 인증 거부 또는 데이터 없음. 응답: {api_data}")
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
            
        except (httpx.RequestError, httpx.TimeoutException) as err:
            print(f"[Warning] 백엔드 -> 프록시 네트워크 통신 오류: {str(err)}")
            return MOCK_CADASTRAL_RESPONSE