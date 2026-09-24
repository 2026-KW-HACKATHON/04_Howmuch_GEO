from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from typing import List, Optional
from app.schemas.realestate.owner.owner_request import OwnerInputDTO, CalculateContributionRequest
from app.schemas.realestate.project.project_request import UnitMixDTO, ProjectParamsDTO, UnitTypeDTO, AllocationDTO
from AI.engine.calc import calc_contribution, Allocation
from AI.engine.schema import ProjectType, UnitType, UnitMix, ProjectParams, OwnerInput, ContributionResult

#라우터 등록
router = APIRouter(
    prefix="/api/v1/owners",
    tags=["Owner Contribution"]
)

#조합원 개인 분담금 및 권리가액 계산 API
@router.post(
    "/contribution",
    response_model=ContributionResult,
    summary="조합원 개인 분담금 및 권리가액 계산",
)
def api_calc_contribution(payload: CalculateContributionRequest):
    try:
        params_dict = payload.params.model_dump()
        params_dict["unit_mix_list"] = [UnitMix(**m) for m in params_dict["unit_mix_list"]]
        params = ProjectParams(**params_dict)

        alloc_dict = payload.allocation.model_dump()
        alloc_dict["unit_types"] = [UnitType(**u) for u in alloc_dict["unit_types"]]
        alloc = Allocation(**alloc_dict)

        owner = OwnerInput(**payload.owner.model_dump())

        result = calc_contribution(params, alloc, owner)
        return result

    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(err)
        )
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"서버 내부 오류: {str(err)}"
        )