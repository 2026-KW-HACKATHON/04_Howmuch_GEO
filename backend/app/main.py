from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os
import httpx
import gdown
import traceback

#.env 파일 로드
load_dotenv()
MODEL_DIR = os.getenv("MODEL_DIR")
MODEL_URL = os.getenv("MODEL_URL")
MODEL_PATH = os.path.join(MODEL_DIR, "model.pkl")
FRONTEND_URL = os.getenv("FRONTEND_URL")

#모델 파일 다운로드
os.makedirs(MODEL_DIR, exist_ok=True)
if not os.path.exists(MODEL_PATH):
    gdown.download(MODEL_URL, MODEL_PATH, quiet=False)

#FastAPI 객체 생성
app = FastAPI()

from app.routers.ai_model import router as model_router

#AI 모델 라우터 등록
app.include_router(model_router)

#MiddleWare 설정 (개발단계 임시 설정)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

VWORLD_API_KEY = os.getenv("VWORLD_API_KEY")
VWORLD_WFS_URL = os.getenv("VWORLD_WFS_URL")
VWORLD_DOMAIN = os.getenv("VWORLD_DOMAIN")

@app.get("/api/cadastral")
async def proxy_cadastral(
    bbox: str = Query(..., description="BOX(minx,miny,maxx,maxy)"),
):
    params = {
        "service": "data",
        "version": "2.0.0",
        "request": "GetFeature",
        "typeName": "lp_pa_cbnd_bubun",
        "data": "lp_pa_cbnd_bubun",
        "key": VWORLD_API_KEY,
        "domain": VWORLD_DOMAIN,
        "format": "json",
        "crs": "EPSG:4326",
        "geomFilter": bbox,
        "size": "1000",
    }

    async with httpx.AsyncClient(verify=False, timeout=5.0) as client:
        try:
            response = await client.get(VWORLD_WFS_URL, params=params)

            if response.status_code == 200:
                return response.json()

            raise HTTPException(
                status_code=response.status_code, detail="V-World API 응답 오류"
            )

        except (httpx.ConnectTimeout, httpx.ConnectError) as e:
            print(
                f"Codespaces 네트워크 제한으로 V-World 우회:"
                f" {str(e)}"
            )

            return {
                "type": "FeatureCollection",
                "features": [],
                "properties": {
                    "message": "Local Codespaces network restriction fallback"
                },
            }