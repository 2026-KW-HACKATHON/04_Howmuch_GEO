from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os
import gdown

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