from pydantic import BaseModel

#AI 모델 요청 스키마 (Dummy Model)
class PreicePredictionRequest(BaseModel):
    area: float
    floor: int
    building_age: int
    subway_distance: float