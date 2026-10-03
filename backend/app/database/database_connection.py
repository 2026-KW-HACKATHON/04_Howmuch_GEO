from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

#환경 변수 로드
load_dotenv()

#PostgreSQL 데이터베이스 연결 설정
POSTGRESQL_DATABASE_URL = os.getenv("POSTGRESQL_DATABASE_URL")

#PostgreSQL 데이터베이스 URL이 설정되지 않은 경우 예외 발생
if not POSTGRESQL_DATABASE_URL:
    raise ValueError("[ Backend ] : POSTGRESQL_DATABASE_URL 환경 변수가 설정되지 않았습니다.")

#SQLAlchemy 엔진 생성
engine = create_engine(POSTGRESQL_DATABASE_URL, echo = True)

#SQLAlchemy 세션 팩토리 생성
SessionFactory = sessionmaker(
    autocommit = False,
    autoflush = False,
    expire_on_commit = False,
    bind = engine
)

#데이터베이스 세션을 제공하는 의존성 함수
def get_db():
    session = SessionFactory()
    try:
        yield session
    finally:
        session.close()