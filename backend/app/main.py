from fastapi import FastAPI
from app.routers.ai_model import router as model_router
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os

#FastAPI 객체 생성
app = FastAPI()

#AI 모델 라우터 등록
app.include_router(model_router)

#.env 파일 로드
load_dotenv()
frontend_url = os.getenv("FRONTEND_URL")

#MiddleWare 설정 (개발단계 임시 설정)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)