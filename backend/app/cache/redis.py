from dotenv import load_dotenv
import redis.asyncio as aioredis
import os

#.env 로드
load_dotenv()

#환경변수 로드
REDIS_URL = os.getenv("REDIS_URL")

#환경변수 실패시 오류 반환
if not REDIS_URL:
    raise ValueError("REDIS_URL 환경 변수가 설정되지 않았습니다.")

#Redis 클라이언트 설정
redis_client = aioredis.from_url(
    REDIS_URL,
    encoding="utf-8",
    decode_responses=True
)