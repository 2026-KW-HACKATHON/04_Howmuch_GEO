import secrets
from datetime import datetime, timezone
from app.exceptions.exceptions_handler import BadRequestException, ServiceUnavailableException, UnauthorizedException
from app.schemas.payment.payment_request import PaymentRequest
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database.database_connection import get_db
from app.models.account import Organization, PaymentOrder
from app.services.plan_service import get_plan, add_plan_duration
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
async def kakao_pay_ready(body: PaymentRequest, request: Request, session: Session = Depends(get_db)):

    #로그인된 사용자인지 확인
    user_id = request.session.get("user_id")
    if user_id is None:
        raise UnauthorizedException("로그인이 필요합니다.")

    #사용자가 조합장인 조합 조회
    organization = session.execute(
        select(Organization).where(
            Organization.leader_user_id == int(user_id)
        )
    ).scalar_one_or_none()

    #사용자가 조합장인 조직이 없거나 결제 불가상태라면 Bad Request Exception 발생
    if not organization:
        raise BadRequestException("조합장 플랜 결제는 조합장 계정만 할 수 있습니다.")
    if organization.status not in {"pending_payment", "active"}:
        raise BadRequestException("현재 결제할 수 없는 조합 상태입니다.")

    #조합의 플랜 코드 반환
    plan = get_plan(organization.plan_code)

    #플랜코드가 없다면 Bad Request Exception 발생
    if not plan:
        raise BadRequestException("유효하지 않은 조합 플랜입니다.")

    #플랜에 대하여 결제 요청 준비
    logger.warning("[ Log ] : 결제 준비 API 시도중.")
    url = f"{KAKAO_PAYMENT_BASE_URL}/ready"
    partner_order_id = secrets.token_urlsafe(24)

    headers = {
        "Authorization": f"SECRET_KEY {KAKAO_PAYMENT_SECERT_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "cid": KAKAO_PAYMENT_CID,
        "partner_order_id": partner_order_id,
        "partner_user_id": str(user_id),
        "item_name": plan.name,
        "quantity": 1,
        "total_amount": plan.price,
        "tax_free_amount": 0,
        "approval_url": f"{BACKEND_URL}/api/v1/kakao-pay/approve?partner_order_id={partner_order_id}",
        "cancel_url": f"{BACKEND_URL}/api/v1/kakao-pay/cancel?partner_order_id={partner_order_id}",
        "fail_url": f"{BACKEND_URL}/api/v1/kakao-pay/fail?partner_order_id={partner_order_id}"
    }

    #비동기 결제 요청
    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=payload)

    #요청 실패시 Service Unavailable Exception 발생
    if response.status_code != 200:
        logger.warning("[ Log ] : 결제 준비 API 호출 실패.")
        raise ServiceUnavailableException(response.json())
    
    #반환 결과 PaymentOrder DB 에 저장 및 반환
    result = response.json()

    session.add(PaymentOrder(
        partner_order_id=partner_order_id,
        user_id=int(user_id),
        organization_id=organization.organization_id,
        plan_code=plan.code,
        tid=result["tid"],
        status="ready",
    ))
    session.commit()
    logger.warning("[ Log ] : 결제 준비 API 성공.")
    return {"next_redirect_pc_url": result["next_redirect_pc_url"], "tid": result["tid"], "item_name": plan.name, "price": plan.price}

#결제 승인 API 엔드포인트
@router.get(
    "/kakao-pay/approve"
)
async def kakao_pay_approve(
    pg_token: str = Query(...),
    partner_order_id: str = Query(...),
    session: Session = Depends(get_db),
):
    #Partner Order ID 로 정보 조회
    logger.warning("[ Log ] : 결제 승인 API 시도중.")
    order = session.execute(
        select(PaymentOrder).where(
            PaymentOrder.partner_order_id == partner_order_id
        )
    ).scalar_one_or_none()

    #정보다 없다면 Service Unavailable Exception 발생
    if not order or not order.tid or order.status != "ready":
        logger.warning("[ Log ] : 결제 승인 API 실패.")
        raise ServiceUnavailableException("결제 준비 정보(tid)를 찾을 수 없습니다.")

    #정보의 조직 id 로 조직 조회
    organization = session.get(Organization, order.organization_id)

    #플랜 코드 조회
    plan = get_plan(order.plan_code)

    #조직 정보나 플랜 코드가 없다면 Service Unavailable Exception 발생
    if not organization or not plan:
        raise ServiceUnavailableException("결제할 조합 플랜 정보를 찾을 수 없습니다.")

    #요청 준비
    url = f"{KAKAO_PAYMENT_BASE_URL}/approve"
    headers = {
        "Authorization": f"SECRET_KEY {KAKAO_PAYMENT_SECERT_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "cid": KAKAO_PAYMENT_CID,
        "tid": order.tid,
        "partner_order_id": partner_order_id,
        "partner_user_id": str(order.user_id),
        "pg_token": pg_token
    }

    #비동기 요청
    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=payload)

    #요청 실패시 Service Unavailable Exception 발생
    if response.status_code != 200:
        logger.warning("[ Log ] : 결제 승인 API 실패.")
        raise ServiceUnavailableException(response.json())

    #결제 최종 승인시 정보 저장 및 페이지 Redirect
    now = datetime.now(timezone.utc)
    start = organization.paid_until if organization.paid_until and organization.paid_until > now else now
    organization.paid_until = add_plan_duration(start, plan.duration_months)
    organization.status = "active"
    order.status = "approved"
    session.commit()
    logger.warning("[ Log ] : 결제 승인 API 성공.")
    return RedirectResponse(url=f"{os.getenv('FRONTEND_URL')}/payment?status=success", status_code=303)

#결제 취소 API 엔드포인트
@router.get("/kakao-pay/cancel")
def kakao_pay_cancel(partner_order_id: str | None = Query(default=None), session: Session = Depends(get_db)):
    logger.warning("[ Log ] : 결제가 취소되었습니다.")
    _update_payment_status(session, partner_order_id, "cancelled")
    return RedirectResponse(url=f"{os.getenv('FRONTEND_URL')}/payment?status=cancel", status_code=303)

#결제 실패 API 엔드포인트
@router.get("/kakao-pay/fail")
def kakao_pay_fail(partner_order_id: str | None = Query(default=None), session: Session = Depends(get_db)):
    logger.warning("[ Log ] : 결제가 실패했습니다.")
    _update_payment_status(session, partner_order_id, "failed")
    return RedirectResponse(url=f"{os.getenv('FRONTEND_URL')}/payment?status=fail", status_code=303)

#결제 정보 업데이트 함수
def _update_payment_status(session: Session, partner_order_id: str | None, new_status: str) -> None:

    #Partner Order ID 가 존재하지 않는다면 반환
    if not partner_order_id:
        return
    
    #PaymentOrder 데이터베이스에서 해당하는 주문정보 조회
    order = session.execute(
        select(PaymentOrder).where(
            PaymentOrder.partner_order_id == partner_order_id
        )
    ).scalar_one_or_none()

    #상태 전환 및 저장
    if order and order.status == "ready":
        order.status = new_status
        session.commit()