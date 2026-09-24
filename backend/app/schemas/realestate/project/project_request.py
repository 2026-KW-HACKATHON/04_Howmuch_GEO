from pydantic import BaseModel
from typing import List, Optional
from AI.engine.schema import ProjectType

#UnitMixDTO 스키마
class UnitMixDTO(BaseModel):
    name: str
    exclusive_area_m2: float
    supply_area_m2: float
    share: float

#ProjectParamsDTO 스키마
class ProjectParamsDTO(BaseModel):
    name: str
    project_type: ProjectType
    site_area_m2: float
    floor_area_ratio: float
    underground_ratio: float
    member_count: int
    general_price_per_m2: float
    member_price_ratio: float
    rental_price_per_unit: float = 0.0
    construction_cost_per_pyeong: float
    other_cost_ratio: float
    total_prior_asset: Optional[float] = None
    avg_prior_asset: Optional[float] = None
    proportional_rate: Optional[float] = None
    rental_ratio: float
    rental_supply_area_m2: float
    commercial_ratio: float
    community_ratio: float
    housing_supply_efficiency: float
    commercial_price_ratio: float
    unit_mix_list: List[UnitMixDTO]

#UnitTypeDTO 스키마
class UnitTypeDTO(BaseModel):
    name: str
    exclusive_area_m2: float
    supply_area_m2: float
    count: int

#AllocationDTO 스키마
class AllocationDTO(BaseModel):
    unit_types: List[UnitTypeDTO]
    rental_count: int
    sale_supply_m2: float

#CalculateProjectRequest 스키마
class CalculateProjectRequest(BaseModel):
    params: ProjectParamsDTO
    allocation: AllocationDTO