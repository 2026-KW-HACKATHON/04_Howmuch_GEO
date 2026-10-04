from pydantic import BaseModel

#뉴스 데이터 요청 스키마
class NewsRequest(BaseModel):
    query: str