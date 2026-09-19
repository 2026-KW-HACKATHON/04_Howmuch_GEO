from fastapi import FastAPI
from app.routers.ai_model import router as model_router

#FastAPI 객체 생성
app = FastAPI()

#AI 모델 라우터 등록
app.include_router(model_router)