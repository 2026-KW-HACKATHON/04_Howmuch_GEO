from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os, sys
import httpx
import gdown
import traceback

#Docker 환경에서 상위 Dir 를 통하여 /AI/engine 디렉터리 접근을 위한 경로 추가
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.abspath(os.path.join(current_dir, "../../"))
print(root_dir)
if root_dir not in sys.path:
    sys.path.append(root_dir)

#.env 파일 로드
load_dotenv()
FRONTEND_URL = os.getenv("FRONTEND_URL")

#Cadastral 데이터 다운로드
CADASTRAL_DATA_DIR = os.getenv("CADASTRAL_DATA_DIR")
CADASTRAL_DATA_URL = os.getenv("CADASTRAL_DATA_URL")
CADASTRAL_DATA_PATH = os.path.join(CADASTRAL_DATA_DIR, "mock_data.py")

os.makedirs(CADASTRAL_DATA_DIR, exist_ok=True)
if not os.path.exists(CADASTRAL_DATA_PATH):
    gdown.download(CADASTRAL_DATA_URL, CADASTRAL_DATA_PATH, quiet=False)

#FastAPI 객체 생성
app = FastAPI()

from app.routers.cadastral import router as cadastral_router
from app.routers.zone import router as zone_router
from app.routers.contribution import router as contribution_router

#AI 모델 라우터 등록
app.include_router(cadastral_router)
app.include_router(zone_router)
app.include_router(contribution_router)

#MiddleWare 설정 (개발단계 임시 설정)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)