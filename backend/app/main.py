from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from app.exceptions.exceptions_handler import add_exception_handlers
from app.database.database_connection import engine
from dotenv import load_dotenv
from app.database.orm import Base
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

#환경 변수 로드
FRONTEND_URL = os.getenv("FRONTEND_URL")
COOKIE_SECRET_KEY = os.getenv("COOKIE_SECRET_KEY")

#FastAPI 객체 생성
app = FastAPI()

#FastAPI 라우터 import
from app.routers.cadastral import router as cadastral_router
from app.routers.zone import router as zone_router
from app.routers.contribution import router as contribution_router
from app.routers.user import router as user_router
from app.routers.news import router as news_router
from app.routers.payment import router as payment_router
from app.routers.organization import router as organization_router

#Database 테이블 생성 이벤트 핸들러 등록
@app.on_event("startup")
def create_tables():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

#AI 모델 라우터 등록
app.include_router(cadastral_router)
app.include_router(zone_router)
app.include_router(contribution_router)
app.include_router(user_router)
app.include_router(news_router)
app.include_router(payment_router)
app.include_router(organization_router)

#사용자 정의 예외 처리기 등록
add_exception_handlers(app)

#Cookie 세션 관리 MiddleWare 설정
app.add_middleware(
    SessionMiddleware,
    secret_key=COOKIE_SECRET_KEY,
    same_site="none",
    https_only=True
)

#MiddleWare 설정 (개발단계 임시 설정)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)