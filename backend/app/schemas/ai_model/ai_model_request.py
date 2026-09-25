from pydantic import BaseModel, Field
from typing import List, Optional
from AI.engine.schema import ProjectType, UnitMix

#AI 모델 요청 스키마
class PreicePredictionRequest(BaseModel):
    pass