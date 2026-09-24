from pydantic import BaseModel
from typing import List, Optional
from app.schemas.realestate.project.project_request import ProjectParamsDTO, AllocationDTO

#OwnerInputDTO 스키마
class OwnerInputDTO(BaseModel):
    desired_unit: str
    appraisal_value: Optional[float] = None
    official_price: Optional[float] = None
    land_area_m2: Optional[float] = None
    land_price_per_m2: Optional[float] = None
    appraisal_ratio: float

#CalculateContributionRequest 스키마
class CalculateContributionRequest(BaseModel):
    params: ProjectParamsDTO
    allocation: AllocationDTO
    owner: OwnerInputDTO