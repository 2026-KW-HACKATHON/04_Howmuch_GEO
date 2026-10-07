from app.exceptions.exceptions_handler import BadRequestException, ServiceUnavailableException
from app.schemas.payment.payment_request import PaymentRequest
from fastapi import APIRouter, Query
from fastapi.responses import RedirectResponse
import httpx
import logging
import os

#결제 라우터
router = APIRouter(
    prefix="/api/v1",
    tags=["Payment"]
)

#백엔드 Logger
logger = logging.getLogger(__name__)

#환경변수 로드
KAKAO_PAYMENT_SECERT_KEY = os.getenv("KAKAO_PAYMENT_SECERT_KEY")
KAKAO_PAYMENT_CID = os.getenv("KAKAO_PAYMENT_CID")
KAKAO_PAYMENT_BASE_URL = os.getenv("KAKAO_PAYMENT_BASE_URL")
BACKEND_URL = os.getenv("BACKEND_URL")

memory_db = {}

#환경변수 유무 확인
if not KAKAO_PAYMENT_SECERT_KEY:
    raise BadRequestException("KAKAO_PAYMENT_SECERT_KEY 환경 변수가 설정되지 않았습니다.")
if not KAKAO_PAYMENT_CID:
    raise BadRequestException("KAKAO_PAYMENT_CID 환경 변수가 설정되지 않았습니다.")
if not KAKAO_PAYMENT_BASE_URL:
    raise BadRequestException("KAKAO_PAYMENT_BASE_URL 환경 변수가 설정되지 않았습니다.")
if not BACKEND_URL:
    raise BadRequestException("BACKEND_URL 환경 변수가 설정되지 않았습니다.")

#결제 API 엔드포인트
@router.post("/kakao-pay/ready")
async def kakao_pay_ready(request: PaymentRequest):
    logger.warning("[ Log ] : 결제 준비 API 시도중.")
    url = f"{KAKAO_PAYMENT_BASE_URL}/ready"

    headers = {
        "Authorization": f"SECRET_KEY {KAKAO_PAYMENT_SECERT_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "cid": KAKAO_PAYMENT_CID,
        "partner_order_id": "order_id_12345",
        "partner_user_id": "user_id_999",
        "item_name": request.item_name,
        "quantity": request.quantity,
        "total_amount": request.price,
        "tax_free_amount": request.tax_free_amount,
        "approval_url": f"{BACKEND_URL}/api/v1/kakao-pay/approve",
        "cancel_url": f"{BACKEND_URL}/api/v1/kakao-pay/cancel",
        "fail_url": f"{BACKEND_URL}/api/v1/kakao-pay/fail"
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=payload)

    if response.status_code != 200:
        logger.warning("[ Log ] : 결제 준비 API 호출 실패.")
        raise ServiceUnavailableException(response.json())
    
    result = response.json()

    memory_db["tid"] = result["tid"]
    logger.warning("[ Log ] : 결제 준비 API 성공.")
    return {"next_redirect_pc_url": result["next_redirect_pc_url"], "tid": result["tid"]}

#결제 승인 API 엔드포인트
@router.get(
    "/kakao-pay/approve"
)
async def kakao_pay_approve(pg_token: str = Query(...)):

    logger.warning("[ Log ] : 결제 승인 API 시도중.")
    tid = memory_db.get("tid")

    if not tid:
        logger.warning("[ Log ] : 결제 승인 API 실패.")
        raise ServiceUnavailableException("결제 준비 정보(tid)를 찾을 수 없습니다.")

    url = f"{KAKAO_PAYMENT_BASE_URL}/approve"
    headers = {
        "Authorization": f"SECRET_KEY {KAKAO_PAYMENT_SECERT_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "cid": KAKAO_PAYMENT_CID,
        "tid": tid,
        "partner_order_id": "order_id_12345",
        "partner_user_id": "user_id_999",
        "pg_token": pg_token
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=payload)

    if response.status_code != 200:
        logger.warning("[ Log ] : 결제 승인 API 실패.")
        raise ServiceUnavailableException(response.json())

    logger.warning("[ Log ] : 결제 승인 API 성공.")
    return RedirectResponse(url=f"{os.getenv('FRONTEND_URL')}/payment?status=success", status_code=303)

#결제 취소 API 엔드포인트
@router.get("/kakao-pay/cancel")
def kakao_pay_cancel():
    logger.warning("[ Log ] : 결제가 취소되었습니다.")
    return RedirectResponse(url=f"{os.getenv('FRONTEND_URL')}/payment?status=cancel", status_code=303)

#결제 실패 API 엔드포인트
@router.get("/kakao-pay/fail")
def kakao_pay_fail():
    logger.warning("[ Log ] : 결제가 실패했습니다.")
    return RedirectResponse(url=f"{os.getenv('FRONTEND_URL')}/payment?status=fail", status_code=303)