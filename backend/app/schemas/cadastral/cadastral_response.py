from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

#Service 메타 데이터
class ServiceInfo(BaseModel):
    name: str = Field(default="data", description="서비스명")
    version: str = Field(default="2.0", description="버전")
    operation: str = Field(default="GetFeature", description="오퍼레이션")
    time: str = Field(default="120(ms)", description="응답 시간")

#Result detail
class CadastralResult(BaseModel):
    featureCollection: Dict[str, Any] = Field(
        default_factory=dict, 
        description="GeoJSON FeatureCollection 객체"
    )

#Response 내부 Wrapper
class CadastralResponseBody(BaseModel):
    service: ServiceInfo
    status: str = Field(default="OK", description="응답 상태")
    result: CadastralResult

#필지 API 반환 스키마
class CadastralResponse(BaseModel):
    response: CadastralResponseBody