from app.cache.redis import redis_client
from AI.predict.sale_price import Trade
from dataclasses import is_dataclass, asdict
from typing import Optional
import logging
import json

#백엔드 Logger
logger = logging.getLogger(__name__)

#Redis 를 통한 Trade 캐시 불러오기
async def get_cached_trades(lawd_cd: str, target_ym: str) -> Optional[list]:

    #trades:lawd_cd:target_ym 형태의 키를 사용
    cache_key = f"trades:{lawd_cd}:{target_ym}"

    try:
        #Redis 에서 해당 키로 저장된 값을 가져오기
        data = await redis_client.get(cache_key)

        #Redis 에서 꺼내온 값이 있다면
        if data:

            #Redis에서 꺼내온 JSON 문자열을 파이썬 객체로 변환 및 성공 로깅
            raw_list = json.loads(data)
            logger.warning(f"[ Log ] : Redis 캐시 불러오기 성공 : Trade : {cache_key}")

            #꺼내온 객체가 dict이면 Trade 객체로 변환, 아니면 그대로 반환
            return [Trade(**item) if isinstance(item, dict) else item for item in raw_list]
        
        #Redis에 해당 키가 없으면 MISS 로깅 후 None 반환
        logger.warning(f"[ Log ] : Redis 캐시 존재하지 않음 : Trade : {cache_key}")
        return None

    #Redis에서 꺼내온 값이 JSON으로 디코딩되지 않거나 다른 오류 발생 시
    except Exception as err:

        #경고 로깅 후 None 반환
        logger.warning(f"[ Log ] : Redis 캐시 불러오기 실패 : Redis 읽기/디코딩 오류 : Trade : {cache_key}: {str(err)}")
        return None

#Redis 를 통한 Trade 캐시 저장
async def set_cached_trades(lawd_cd: str, target_ym: str, trades: list) -> None:

    #trades 리스트가 비어있으면 저장하지 않고 바로 반환
    if not trades:
        return

    #trades:lawd_cd:target_ym 형태의 키를 사용
    cache_key = f"trades:{lawd_cd}:{target_ym}"

    try:
        #trades_dict 리스트를 만들어 각 Trade 객체를 dict로 변환
        trades_dict = []
        for trade in trades:

            #Pydantic v2 모델인 경우 model_dump() 메서드를 사용하여 dict로 변환
            if hasattr(trade, "model_dump"):
                trades_dict.append(trade.model_dump())
            
            #Pydantic v1 모델인 경우 dict() 메서드를 사용하여 dict로 변환
            elif hasattr(trade, "dict"):
                trades_dict.append(trade.dict())
            
            #Dataclass 인 경우 asdict() 함수를 사용하여 dict로 변환
            elif is_dataclass(trade):
                trades_dict.append(asdict(trade))
            
            #이미 dict인 경우 그대로 추가
            elif isinstance(trade, dict):
                trades_dict.append(trade)

            #일반 Custom Class 인 경우 __dict__ 속성을 사용하여 dict로 변환
            elif hasattr(trade, "__dict__"):
                trades_dict.append(trade.__dict__)
            
            #그 외의 경우, 직렬화할 수 없는 객체이므로 str()로 변환하여 저장
            else:
                trades_dict.append(str(trade))

        #trades_dict를 JSON 문자열로 직렬화하고 Redis에 저장, TTL은 86400초 (=1일)
        serialized_data = json.dumps(trades_dict, ensure_ascii=False)
        await redis_client.set(cache_key, serialized_data, ex=86400)


        #Redis에 저장 성공 시 로깅
        logger.warning(f"[ Log ] : Redis 캐시 저장 성공 : Trade : {cache_key} : (TTL 86400s)")

    #Redis 저장 중 오류 발생 시 경고 로깅
    except Exception as err:
        logger.warning(f"[ Log ] : Redis 캐시 저장 실패 : Redis 쓰기 오류 : Trade : {cache_key} : {str(err)}")

#Redis 를 통한 Land 캐시 불러오기
async def get_cached_land(pnu: str) -> Optional[dict]:

    #Land 객체를 Redis에서 불러오기 위해 land:{pnu} 형태의 키를 사용
    cache_key = f"land:{pnu}"

    try:
        #Redis에서 해당 키로 저장된 값을 가져오기
        val = await redis_client.get(cache_key)

        #Redis에서 꺼내온 값이 있다면 JSON 문자열을 파이썬 객체로 변환 및 성공 로깅
        if val:
            logger.warning(f"[ Log ] : Redis 캐시 불러오기 성공 : Land : {cache_key}")
            return json.loads(val)

        #Redis에 해당 키가 없으면 MISS 로깅 후 None 반환
        else:
            logger.warning(f"[ Log ] : Redis 캐시 존재하지 않음 : Land : {cache_key}")
    
    #Redis에서 꺼내온 값이 JSON으로 디코딩되지 않거나 다른 오류 발생 시 경고 로깅
    except Exception as err:
        logger.warning(f"[ Log ] : Redis 캐시 불러오기 실패 : Redis 읽기/디코딩 오류 : Land : {cache_key} : {err}")
    
    #Redis에서 값을 가져오지 못했거나 오류가 발생한 경우 None 반환
    return None

#Redis 를 통한 Land 캐시 저장하기
async def set_cached_land(pnu: str, data: dict):

    #Land 객체가 비어있으면 저장하지 않고 바로 반환
    if not data:
        return

    #Land 객체를 Redis에 저장하기 위해 land:{pnu} 형태의 키를 사용
    cache_key = f"land:{pnu}"

    try:
        #Land 객체를 JSON 문자열로 직렬화하고 Redis에 저장, TTL은 604800초 (=7일)
        serialized_data = json.dumps(data, ensure_ascii=False, default=str)
        await redis_client.setex(cache_key, 604800, serialized_data)

        #Redis에 저장 성공 시 로깅
        logger.warning(f"[ Log ] : Redis 캐시 저장 성공 : Land : {cache_key} : (TTL 604800s)")

    #Redis 저장 중 오류 발생 시 경고 로깅
    except Exception as err:
        logger.warning(f"[ Log ] : Redis 캐시 저장 실패 : Redis 쓰기 오류 : Land : {cache_key} : {err}")

#Redis 를 통한 건축물대장 캐시 불러오기
#  land:{pnu} 에 합치지 않고 따로 둔다 — 이미 7일 TTL 로 캐시된 기존 항목을 깨지 않고,
#  건축물대장은 거의 변하지 않아 더 긴 TTL 을 줄 수 있다
async def get_cached_building(pnu: str) -> Optional[dict]:
    cache_key = f"bld:{pnu}"

    try:
        val = await redis_client.get(cache_key)
        if val:
            logger.warning(f"[ Log ] : Redis 캐시 불러오기 성공 : Building : {cache_key}")
            return json.loads(val)
        logger.warning(f"[ Log ] : Redis 캐시 존재하지 않음 : Building : {cache_key}")

    except Exception as err:
        logger.warning(f"[ Log ] : Redis 캐시 불러오기 실패 : Building : {cache_key} : {err}")

    return None


#Redis 를 통한 건축물대장 캐시 저장하기
#  TTL 30일. 사용승인일·구조·연면적은 바뀌지 않고, 신축·멸실만 반영이 늦어진다.
#  재개발 구역은 신축이 거의 없어 이 지연이 문제되지 않는다
async def set_cached_building(pnu: str, data: dict) -> None:
    if not data:
        return

    cache_key = f"bld:{pnu}"

    try:
        serialized_data = json.dumps(data, ensure_ascii=False, default=str)
        await redis_client.setex(cache_key, 2592000, serialized_data)
        logger.warning(f"[ Log ] : Redis 캐시 저장 성공 : Building : {cache_key} : (TTL 2592000s)")

    except Exception as err:
        logger.warning(f"[ Log ] : Redis 캐시 저장 실패 : Building : {cache_key} : {err}")



#Redis 를 통한 전유면적 합계 캐시
#  전유공용 조회는 호·면적구분마다 한 행이라 대단지는 37페이지(9.7초 실측)가 걸린다.
#  값 자체는 거의 변하지 않아 길게 캐시한다 (TTL 30일)
async def get_cached_exclusive_total(pnu: str) -> Optional[float]:
    cache_key = f"exc:{pnu}"

    try:
        val = await redis_client.get(cache_key)
        if val is not None:
            logger.warning(f"[ Log ] : Redis 캐시 불러오기 성공 : Exclusive : {cache_key}")
            return float(val)
        logger.warning(f"[ Log ] : Redis 캐시 존재하지 않음 : Exclusive : {cache_key}")

    except Exception as err:
        logger.warning(f"[ Log ] : Redis 캐시 불러오기 실패 : Exclusive : {cache_key} : {err}")

    return None


async def set_cached_exclusive_total(pnu: str, total: float) -> None:
    #0 은 "다 못 받았다" 는 뜻이라 캐시하지 않는다. 일시 장애가 굳어버린다
    if not total:
        return

    cache_key = f"exc:{pnu}"

    try:
        await redis_client.setex(cache_key, 2592000, str(total))
        logger.warning(f"[ Log ] : Redis 캐시 저장 성공 : Exclusive : {cache_key} : (TTL 2592000s)")

    except Exception as err:
        logger.warning(f"[ Log ] : Redis 캐시 저장 실패 : Exclusive : {cache_key} : {err}")
