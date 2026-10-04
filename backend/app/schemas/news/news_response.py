from datetime import datetime
from pydantic import BaseModel, HttpUrl, Field

#뉴스 데이터 응답 스키마
class NewsResponse(BaseModel):
    title: str = Field(..., description="뉴스 제목")
    contents: str = Field(..., description="뉴스 본문 요약")
    url: HttpUrl = Field(..., description="뉴스 원문 링크")
    published_at: datetime = Field(..., description="발행 일시")