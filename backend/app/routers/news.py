from app.exceptions.exceptions_handler import BadRequestException, ServiceUnavailableException
from app.schemas.news.news_request import NewsRequest
from app.schemas.news.news_response import NewsResponse
from fastapi import APIRouter, status
import httpx
import re
import html
import os
import logging
from typing import List

#뉴스 조회 라우터
router = APIRouter(
    prefix="/api/v1",
    tags=["News Router"]
)

#HTML 클리너
def clean_html(text: str) -> str:

    #값이 없다면 빈 문자열 반환
    if not text:
        return ""
    
    #HTML 태그 제거
    clean_text = re.sub(r'<[^>]+>', '', text)

    #HTML 엔티티 복원 및 반환
    return html.unescape(clean_text)

#백엔드 Logger
logger = logging.getLogger(__name__)

#환경변수 로드
KAKAO_API_KEY = os.getenv("KAKAO_API_KEY")

if not KAKAO_API_KEY:
    raise BadRequestException("VWORLD_API_KEY 환경 변수가 설정되지 않았습니다.")


@router.post(
    "/news",
    response_model=List[NewsResponse],
    status_code = status.HTTP_200_OK,
)
async def get_region_news(request: NewsRequest):
    search_keyword = f"{request.query} 재개발"

    url = f"https://dapi.kakao.com/v2/search/web?query={search_keyword}&sort=recency&size=8"

    headers = {
        "Authorization": f"KakaoAK {KAKAO_API_KEY}"
    }
    
    try:
        async with httpx.AsyncClient() as client:
            logger.warning(f"[ Log ] : News API 호출 시도 : {str(request.query)}")
            res = await client.get(url, headers=headers)
            if res.status_code == 200:
                raw_documents = res.json().get("documents", [])
                cleaned_documents = []

                for item in raw_documents:
                    cleaned_documents.append({
                    "title": clean_html(item.get("title")),
                    "contents": clean_html(item.get("contents")),
                    "url": item.get("url"),
                    "published_at": item.get("datetime")
                })
                
                return cleaned_documents
                
            return []
    except:
        logger.warning(f"[ Log ] : News API 호출 실패")
        raise ServiceUnavailableException
