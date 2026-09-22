from pydantic import BaseModel

#필지 데이터 요청 스키마
class CadastralRequest(BaseModel):
    geom_filter: str