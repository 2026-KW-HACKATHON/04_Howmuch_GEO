from pydantic import BaseModel

#AI 모델 응답 스키마 (Dummy Model)
class PreicePredictionResponse(BaseModel):
    predicted_price: float