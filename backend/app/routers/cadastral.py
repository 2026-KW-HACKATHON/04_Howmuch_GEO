from fastapi import APIRouter
from app.routers.mock_data import MOCK_CADASTRAL_RESPONSE

router = APIRouter(
    tags=["Cadastral"]
)

#Cadastral 데이터 반환 API
@router.get(
    "/cadastral",
)
async def get_cadastral():
    response = MOCK_CADASTRAL_RESPONSE

    return response