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

#환경변수가 설정되지 않았다면 Bad Request Exception 반환
if not KAKAO_API_KEY:
    raise BadRequestException("KAKAO_API_KEY 환경 변수가 설정되지 않았습니다.")

#뉴스 조회 API 엔드포인트
@router.post(
    "/news",
    response_model=List[NewsResponse],
    status_code = status.HTTP_200_OK,
)
async def get_region_news(request: NewsRequest):

    headers = {
        "Authorization": f"KakaoAK {KAKAO_API_KEY}"
    }

    cleaned_documents = []
    
    try:
        async with httpx.AsyncClient() as client:

            #요청 호출
            logger.warning(f"[ Log ] : News API 호출 시도 : {str(request.query)}")

            #재개발 뉴스 검색

            search_keyword = f"{request.query} 재개발"
            url = f"https://dapi.kakao.com/v2/search/web?query={search_keyword}&sort=recency&size=8"
            cleaned_documents = []

            res = await client.get(url, headers=headers)

            #성공적이라면 데이터 파싱 후 반환
            if res.status_code == 200:
                raw_documents = res.json().get("documents", [])

                for item in raw_documents:
                    if clean_html(item.get("url")[:12]) == "https://namu" or clean_html(item.get("url")[:25]) == "https://gall.dcinside.com":
                        continue
                    if clean_html(item.get("title")).endswith("pdf"):
                        continue
                    cleaned_documents.append({
                        "title": clean_html(item.get("title")),
                        "contents": clean_html(item.get("contents")),
                        "url": item.get("url"),
                        "published_at": item.get("datetime")
                    })

            #재건축 뉴스 검색

            search_keyword = f"{request.query} 재건축"
            url = f"https://dapi.kakao.com/v2/search/web?query={search_keyword}&sort=recency&size=8"

            res = await client.get(url, headers=headers)

            if res.status_code == 200:
                raw_documents = res.json().get("documents", [])

                for item in raw_documents:
                    if clean_html(item.get("url")[:12]) == "https://namu":
                        continue
                    if clean_html(item.get("title")).endswith("pdf"):
                        continue
                    cleaned_documents.append({
                        "title": clean_html(item.get("title")),
                        "contents": clean_html(item.get("contents")),
                        "url": item.get("url"),
                        "published_at": item.get("datetime")
                    })
            
            #결과 반환
            return cleaned_documents

    except:

        #예외 발생시 Service Unavailable Exception 발생
        logger.warning(f"[ Log ] : News API 호출 실패")
        raise ServiceUnavailableException
