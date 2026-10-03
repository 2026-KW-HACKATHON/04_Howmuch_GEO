import logging
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo
from fastapi import HTTPException, status
from redis.exceptions import RedisError
from app.cache.redis import redis_client

#일일 사용 가능한 크레딧 수 제한
DAILY_CREDIT_LIMIT = 5

#타임존 설정 (서울 시간)
SEOUL_TIMEZONE = ZoneInfo("Asia/Seoul")

#로거 설정
logger = logging.getLogger(__name__)

#Redis에서 키를 가져오고, 없으면 초기화하며, 만료 시간을 설정
_GET_OR_INITIALIZE_SCRIPT = """
local credits = redis.call('GET', KEYS[1])
if not credits then
    redis.call('SET', KEYS[1], ARGV[1], 'EX', ARGV[2])
    credits = ARGV[1]
end
return tonumber(credits)
"""

#Redis에서 키를 가져오고, 없으면 초기화하며, 만료 시간을 설정하고, 크레딧을 1 감소. 만약 크레딧이 0 이하이면 -1을 반환
_CONSUME_SCRIPT = """
local credits = redis.call('GET', KEYS[1])
if not credits then
    redis.call('SET', KEYS[1], ARGV[1], 'EX', ARGV[2])
    credits = ARGV[1]
end
if tonumber(credits) <= 0 then
    return -1
end
return redis.call('DECR', KEYS[1])
"""

#일일 크레딧 키와 TTL(만료 시간)을 계산하는 함수
def _daily_key_and_ttl(user_id: int) -> tuple[str, int, datetime]:
    now = datetime.now(SEOUL_TIMEZONE)
    resets_at = datetime.combine(
        now.date() + timedelta(days=1),
        time.min,
        tzinfo=SEOUL_TIMEZONE,
    )
    ttl_seconds = max(1, int((resets_at - now).total_seconds()))
    return f"credits:{user_id}:{now:%Y-%m-%d}", ttl_seconds, resets_at

#일일 크레딧 정보를 가져오는 함수
async def get_daily_credits(user_id: int) -> dict[str, int | str]:
    key, ttl_seconds, resets_at = _daily_key_and_ttl(user_id)
    try:
        remaining = await redis_client.eval(
            _GET_OR_INITIALIZE_SCRIPT,
            1,
            key,
            DAILY_CREDIT_LIMIT,
            ttl_seconds,
        )
    except RedisError as exc:
        logger.exception("Unable to load daily credits for user %s", user_id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="크레딧 정보를 불러올 수 없습니다. 잠시 후 다시 시도해 주세요.",
        ) from exc

    return {
        "credits_remaining": int(remaining),
        "daily_credit_limit": DAILY_CREDIT_LIMIT,
        "resets_at": resets_at.isoformat(),
    }

#일일 크레딧을 초기화하는 함수. Redis에서 해당 사용자의 크레딧을 초기화하고, 만료 시간을 설정
async def reset_daily_credits(user_id: int) -> dict[str, int | str]:
    key, ttl_seconds, resets_at = _daily_key_and_ttl(user_id)
    try:
        await redis_client.set(key, DAILY_CREDIT_LIMIT, ex=ttl_seconds)
    except RedisError as exc:
        logger.exception("Unable to reset daily credits for user %s", user_id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="크레딧을 초기화할 수 없습니다. 잠시 후 다시 시도해 주세요.",
        ) from exc

    return {
        "credits_remaining": DAILY_CREDIT_LIMIT,
        "daily_credit_limit": DAILY_CREDIT_LIMIT,
        "resets_at": resets_at.isoformat(),
    }


#일일 크레딧이 남아 있는지 확인하고, 없으면 HTTP 429 에러를 발생시키는 함수
async def ensure_daily_credit_available(user_id: int) -> None:
    credits = await get_daily_credits(user_id)
    if credits["credits_remaining"] <= 0:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="오늘 사용할 수 있는 크레딧을 모두 사용했습니다.",
        )

#일일 크레딧을 소비하는 함수. 남은 크레딧이 0 이하이면 HTTP 429 에러를 발생시킴
async def consume_daily_credit(user_id: int) -> int:
    key, ttl_seconds, _ = _daily_key_and_ttl(user_id)
    try:
        remaining = await redis_client.eval(
            _CONSUME_SCRIPT,
            1,
            key,
            DAILY_CREDIT_LIMIT,
            ttl_seconds,
        )
    except RedisError as exc:
        logger.exception("Unable to consume daily credit for user %s", user_id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="크레딧을 확인할 수 없습니다. 잠시 후 다시 시도해 주세요.",
        ) from exc

    if int(remaining) < 0:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="오늘 사용할 수 있는 크레딧을 모두 사용했습니다.",
        )
    return int(remaining)