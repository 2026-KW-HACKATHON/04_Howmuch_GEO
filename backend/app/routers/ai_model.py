from fastapi import APIRouter
from app.schemas.ai_model.ai_model_request import PreicePredictionRequest
from app.schemas.ai_model.ai_model_response import PreicePredictionResponse
from app.models.ai_model import predict_price

router = APIRouter(
    tags=["Model"]
)

#AI 모델 예측 API (Dummy Model)
@router.post(
    "/predict",
    response_model=PreicePredictionResponse
)
def predict(data: PreicePredictionRequest):
    features = [
        data.area,
        data.floor,
        data.building_age,
        data.subway_distance
    ]

    result_price = predict_price(features)
    return PreicePredictionResponse(predicted_price=result_price)