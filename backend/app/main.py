from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os
import httpx
import gdown
import traceback

#.env 파일 로드
load_dotenv()
FRONTEND_URL = os.getenv("FRONTEND_URL")

#모델 파일 다운로드
MODEL_DIR = os.getenv("MODEL_DIR")
MODEL_URL = os.getenv("MODEL_URL")
MODEL_PATH = os.path.join(MODEL_DIR, "model.pkl")

os.makedirs(MODEL_DIR, exist_ok=True)
if not os.path.exists(MODEL_PATH):
    gdown.download(MODEL_URL, MODEL_PATH, quiet=False)

#Cadastral 데이터 다운로드
CADASTRAL_DATA_DIR = os.getenv("CADASTRAL_DATA_DIR")
CADASTRAL_DATA_URL = os.getenv("CADASTRAL_DATA_URL")
CADASTRAL_DATA_PATH = os.path.join(CADASTRAL_DATA_DIR, "mock_data.py")

os.makedirs(CADASTRAL_DATA_DIR, exist_ok=True)
if not os.path.exists(CADASTRAL_DATA_PATH):
    gdown.download(CADASTRAL_DATA_URL, CADASTRAL_DATA_PATH, quiet=False)

#FastAPI 객체 생성
app = FastAPI()

from app.routers.ai_model import router as model_router
from app.routers.cadastral import router as cadastral_router

#AI 모델 라우터 등록
app.include_router(model_router)
app.include_router(cadastral_router)

#MiddleWare 설정 (개발단계 임시 설정)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)