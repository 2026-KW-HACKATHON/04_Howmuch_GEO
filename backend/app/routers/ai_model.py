from fastapi import APIRouter, HTTPException, status
from app.schemas.ai_model.ai_model_request import PreicePredictionRequest
from app.schemas.ai_model.ai_model_response import PreicePredictionResponse
from AI.engine.schema import ProjectParams, OwnerInput, ProjectType, UnitMix, UnitType
from AI.engine.calc import calc_contribution, Allocation

#AI Model 라우터 설정
router = APIRouter(
    prefix="/api/v1/model",
    tags=["Model"]
)

#예측 라우터
@router.post(
    "/predict",
    response_model=PreicePredictionResponse,
    summary="AI 모델 예측"
)
def predict(data: PreicePredictionRequest):
    try:
        return "[ 테스트 데이터 ]"
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"서버 내부 오류: {str(e)}")