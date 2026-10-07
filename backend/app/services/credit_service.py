from app.exceptions.exceptions_handler import BadRequestException, ServiceUnavailableException
from app.cache.redis import redis_client
from redis.exceptions import RedisError
from datetime import datetime, time, timedelta
import logging
import secrets
from zoneinfo import ZoneInfo

#일일 사용 가능한 크레딧 수 제한
DAILY_CREDIT_LIMIT = 5

#타임존 설정 (서울 시간)
SEOUL_TIMEZONE = ZoneInfo("Asia/Seoul")

#백엔드 로거 설정
logger = logging.getLogger(__name__)

#Lua 를 통하여 Redis에서 키를 가져오고, 없으면 초기화하며, 만료 시간을 설정
_GET_OR_INITIALIZE_SCRIPT = """
local credits = redis.call('GET', KEYS[1])
if not credits then
    redis.call('SET', KEYS[1], ARGV[1], 'EX', ARGV[2])
    credits = ARGV[1]
end
return tonumber(credits)
"""

#Lua 를 통하여 Redis에서 키를 가져오고, 없으면 초기화하며, 만료 시간을 설정하고, 크레딧을 1 감소. 만약 크레딧이 0 이하이면 -1을 반환
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

#크레딧이 차감될 계산을 위한 일회성 토큰을 자정까지 보관
_ISSUE_CREDIT_TOKEN_SCRIPT = """
return redis.call('SET', KEYS[1], 'pending', 'EX', ARGV[1], 'NX')
"""

_FULFILL_PURCHASE_SCRIPT = """
if redis.call('SET', KEYS[2], 'fulfilled', 'NX') then
    return redis.call('INCRBY', KEYS[1], ARGV[1])
end
return tonumber(redis.call('GET', KEYS[1]) or '0')
"""

#계산 성공 후 토큰당 한 번만 크레딧을 차감. 같은 구역의 자동 재계산은 기존 차감을 재사용
_CONSUME_CREDIT_TOKEN_SCRIPT = """
local token_state = redis.call('GET', KEYS[2])
local credits = redis.call('GET', KEYS[1])
if token_state == 'unlimited-consumed' then
    if ARGV[3] == '1' then
        return -3
    end
    return -2
end
if ARGV[3] == '1' and token_state == 'pending' then
    redis.call('SET', KEYS[2], 'unlimited-consumed', 'EX', ARGV[2])
    return -3
end
if token_state == 'consumed' then
    if not credits then
        redis.call('SET', KEYS[1], ARGV[1], 'EX', ARGV[2])
        credits = ARGV[1]
    end
    return tonumber(credits) + purchased
end
if token_state ~= 'pending' then
    return -2
end
if not credits then
    redis.call('SET', KEYS[1], ARGV[1], 'EX', ARGV[2])
    credits = ARGV[1]
end
if tonumber(credits) > 0 then
    credits = redis.call('DECR', KEYS[1])
elseif purchased > 0 then
    purchased = redis.call('DECR', KEYS[3])
else
    return -1
end
redis.call('SET', KEYS[2], 'consumed', 'EX', ARGV[2])
return tonumber(credits) + tonumber(purchased)
"""

#일일 크레딧 키와 TTL(만료 시간)을 계산하는 함수
def _daily_key_and_ttl(user_id: int) -> tuple[str, int, datetime]:

    #현재 시간 (서울 시간 기준)
    now = datetime.now(SEOUL_TIMEZONE)

    #다음 날 자정까지의 시간을 계산하여 TTL을 설정
    resets_at = datetime.combine(
        now.date() + timedelta(days=1),
        time.min,
        tzinfo=SEOUL_TIMEZONE,
    )

    #TTL은 최소 1초 이상으로 설정
    ttl_seconds = max(1, int((resets_at - now).total_seconds()))

    #Redis 키는 "credits:{user_id}:{YYYY-MM-DD}" 형식으로 생성
    return f"credits:{user_id}:{now:%Y-%m-%d}", ttl_seconds, resets_at

#크레딧을 차감할 수 있는 계산 토큰 발급
async def issue_credit_token(user_id: int) -> str:
    daily_key, ttl_seconds, _ = _daily_key_and_ttl(user_id)
    token = secrets.token_urlsafe(32)

    try:
        issued = await redis_client.eval(
            _ISSUE_CREDIT_TOKEN_SCRIPT,
            1,
            f"{daily_key}:token:{token}",
            ttl_seconds,
        )
    except RedisError as err:
        logger.exception("Unable to issue credit token for user %s", user_id)
        raise ServiceUnavailableException(
            message="크레딧 정보를 확인할 수 없습니다. 잠시 후 다시 시도해 주세요."
        ) from err

    if issued is None:
        raise ServiceUnavailableException(
            message="계산 토큰을 발급할 수 없습니다. 다시 시도해 주세요."
        )
    return token

#계산 성공 후 토큰을 소비. 동일 토큰의 재계산은 추가 차감하지 않음
async def consume_credit_token(user_id: int, token: str, unlimited: bool = False) -> int:
    daily_key, ttl_seconds, _ = _daily_key_and_ttl(user_id)

    try:
        remaining = await redis_client.eval(
            _CONSUME_CREDIT_TOKEN_SCRIPT,
            3,
            daily_key,
            f"{daily_key}:token:{token}",
            f"purchased-credits:{user_id}",
            DAILY_CREDIT_LIMIT,
            ttl_seconds,
            1 if unlimited else 0,
        )
    except RedisError as err:
        logger.exception("Unable to consume credit token for user %s", user_id)
        raise ServiceUnavailableException(
            message="크레딧을 확인할 수 없습니다. 잠시 후 다시 시도해 주세요."
        ) from err

    remaining = int(remaining)
    if remaining == -3:
        return -1
    if remaining == -1:
        raise ServiceUnavailableException(
            message="오늘 사용할 수 있는 크레딧을 모두 사용했습니다."
        )
    if remaining == -2:
        raise BadRequestException("계산 토큰이 만료되었거나 유효하지 않습니다. 구역을 다시 분석해 주세요.")
    return remaining

#일일 크레딧 정보를 가져오는 함수
async def get_daily_credits(user_id: int) -> dict[str, int | str]:

    #Redis 키와 TTL을 계산
    key, ttl_seconds, resets_at = _daily_key_and_ttl(user_id)

    #Redis에서 키를 가져오고, 없으면 초기화하며, 만료 시간을 설정
    try:
        daily_remaining = await redis_client.eval(
            _GET_OR_INITIALIZE_SCRIPT,
            1,
            key,
            DAILY_CREDIT_LIMIT,
            ttl_seconds,
        )
        purchased_remaining = await redis_client.get(f"purchased-credits:{user_id}")

    #Redis에서 키를 가져오지 못했거나 오류가 발생하면 HTTP 503 에러를 발생시키고, 로깅
    except RedisError as err:
        logger.exception("Unable to load daily credits for user %s", user_id)
        raise ServiceUnavailableException(
            message="크레딧 정보를 불러올 수 없습니다. 잠시 후 다시 시도해 주세요."
        ) from err

    #Redis에서 가져온 남은 크레딧 수와 일일 크레딧 제한, 초기화 시간을 반환
    return {
        "credits_remaining": int(daily_remaining) + int(purchased_remaining or 0),
        "daily_credits_remaining": int(daily_remaining),
        "purchased_credits": int(purchased_remaining or 0),
        "daily_credit_limit": DAILY_CREDIT_LIMIT,
        "resets_at": resets_at.isoformat(),
    }


async def fulfill_credit_purchase(user_id: int, partner_order_id: str, credits: int) -> int:
    try:
        return int(await redis_client.eval(
            _FULFILL_PURCHASE_SCRIPT,
            2,
            f"purchased-credits:{user_id}",
            f"credit-purchase-fulfilled:{partner_order_id}",
            credits,
        ))
    except RedisError as err:
        logger.exception("Unable to fulfill credit purchase %s", partner_order_id)
        raise ServiceUnavailableException(
            message="결제는 승인됐지만 크레딧 반영을 확인할 수 없습니다. 고객센터에 문의해 주세요."
        ) from err

#일일 크레딧을 초기화하는 함수. Redis에서 해당 사용자의 크레딧을 초기화하고, 만료 시간을 설정
async def reset_daily_credits(user_id: int) -> dict[str, int | str]:

    #Redis 키와 TTL을 계산
    key, ttl_seconds, resets_at = _daily_key_and_ttl(user_id)

    #Redis에서 해당 키를 초기화하고, 만료 시간을 설정.
    try:
        await redis_client.set(key, DAILY_CREDIT_LIMIT, ex=ttl_seconds)

    #오류 발생 시 HTTP 503 에러를 발생시키고, 로깅
    except RedisError as err:
        logger.exception("Unable to reset daily credits for user %s", user_id)
        raise ServiceUnavailableException(
            message="크레딧을 초기화할 수 없습니다. 잠시 후 다시 시도해 주세요."
        ) from err

    #Redis에서 초기화된 남은 크레딧 수와 일일 크레딧 제한, 초기화 시간을 반환
    return {
        "credits_remaining": DAILY_CREDIT_LIMIT,
        "daily_credit_limit": DAILY_CREDIT_LIMIT,
        "resets_at": resets_at.isoformat(),
    }

#일일 크레딧이 남아 있는지 확인하고, 없으면 HTTP 429 에러를 발생시키는 함수
async def ensure_daily_credit_available(user_id: int) -> None:

    #Redis에서 해당 사용자의 일일 크레딧 정보를 가져옴
    credits = await get_daily_credits(user_id)

    #만약 남은 크레딧이 0 이하이면 HTTP 503 에러를 발생시키고, 로깅
    if credits["credits_remaining"] <= 0:
        raise ServiceUnavailableException(
            message="오늘 사용할 수 있는 크레딧을 모두 사용했습니다."
        )

#일일 크레딧을 소비하는 함수. 남은 크레딧이 0 이하이면 HTTP 429 에러를 발생시킴
async def consume_daily_credit(user_id: int) -> int:

    #Redis 키와 TTL을 계산
    key, ttl_seconds, _ = _daily_key_and_ttl(user_id)

    #Redis에서 해당 키를 가져오고, 없으면 초기화하며, 만료 시간을 설정하고, 크레딧을 1 감소.
    try:
        remaining = await redis_client.eval(
            _CONSUME_SCRIPT,
            1,
            key,
            DAILY_CREDIT_LIMIT,
            ttl_seconds,
        )

    #만약 Redis에서 키를 가져오지 못했거나 오류가 발생하면 HTTP 503 에러를 발생시키고, 로깅
    except RedisError as err:
        logger.exception("Unable to consume daily credit for user %s", user_id)
        raise ServiceUnavailableException(
            message="크레딧을 확인할 수 없습니다. 잠시 후 다시 시도해 주세요."
        ) from err

    #만약 크레딧이 0 이하이면 -1을 반환
    if int(remaining) < 0:
        raise ServiceUnavailableException(
            message="오늘 사용할 수 있는 크레딧을 모두 사용했습니다."
        )
    
    #남은 크레딧 수를 반환
    return int(remaining)