from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from typing import List, Optional
from AI.engine.calc import calc_project, Allocation
from AI.engine.schema import ProjectType, UnitType, UnitMix, ProjectParams, ProjectResult
from app.schemas.realestate.project.project_request import UnitMixDTO, ProjectParamsDTO, UnitTypeDTO, CalculateProjectRequest, AllocationDTO

#라우터 등록
router = APIRouter(
    prefix="/api/v1/projects",
    tags=["Project Calculation"]
)

#정비사업 수지 및 비례율 계산 API
@router.post(
    "/calculate", 
    response_model=ProjectResult, 
    summary="정비사업 수지 및 비례율 계산"
)
def api_calc_project(payload: CalculateProjectRequest):
    try:
        params_dict = payload.params.model_dump()
        params_dict["unit_mix_list"] = [UnitMix(**m) for m in params_dict["unit_mix_list"]]
        params = ProjectParams(**params_dict)

        alloc_dict = payload.allocation.model_dump()
        alloc_dict["unit_types"] = [UnitType(**u) for u in alloc_dict["unit_types"]]
        alloc = Allocation(**alloc_dict)

        result = calc_project(params, alloc)
        return result

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"서버 내부 오류: {str(e)}"
        )