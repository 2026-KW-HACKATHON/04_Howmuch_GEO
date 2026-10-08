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
from app.models.credit_purchase import CreditPurchaseOrder
from app.services.plan_service import get_plan, add_plan_duration
from app.services.organization_service import has_unlimited_credits
from app.services.credit_service import fulfill_credit_purchase
import httpx
import logging
import os

#결제 라우터
router = APIRouter(
    prefix="/api/v1",
    tags=["Payment Router"]
)

#백엔드 Logger
logger = logging.getLogger(__name__)

PERSONAL_CREDIT_PACK_SIZE = 5
PERSONAL_CREDIT_PACK_PRICE = 500

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

#크레딧 충전 API 엔드포인트
@router.post("/kakao-pay/credits/ready")
async def kakao_credit_purchase_ready(request: Request, session: Session = Depends(get_db)):
    user_id = request.session.get("user_id")
    if user_id is None:
        raise UnauthorizedException("로그인이 필요합니다.")

    user_id = int(user_id)
    if has_unlimited_credits(session, user_id):
        raise BadRequestException("조합 플랜 이용자는 개인 크레딧을 구매할 필요가 없습니다.")

    partner_order_id = secrets.token_urlsafe(24)
    callback_base = f"{BACKEND_URL}/api/v1/kakao-pay/credits"
    payload = {
        "cid": KAKAO_PAYMENT_CID,
        "partner_order_id": partner_order_id,
        "partner_user_id": str(user_id),
        "item_name": "개인 크레딧 5회권",
        "quantity": 1,
        "total_amount": PERSONAL_CREDIT_PACK_PRICE,
        "tax_free_amount": 0,
        "approval_url": f"{callback_base}/approve?partner_order_id={partner_order_id}",
        "cancel_url": f"{callback_base}/cancel?partner_order_id={partner_order_id}",
        "fail_url": f"{callback_base}/fail?partner_order_id={partner_order_id}",
    }
    headers = {
        "Authorization": f"SECRET_KEY {KAKAO_PAYMENT_SECERT_KEY}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(f"{KAKAO_PAYMENT_BASE_URL}/ready", headers=headers, json=payload)

    if response.status_code != 200:
        logger.warning("KakaoPay credit ready failed: %s", response.text)
        raise ServiceUnavailableException("크레딧 결제를 시작하지 못했습니다.")

    result = response.json()
    if not result.get("tid") or not result.get("next_redirect_pc_url"):
        raise ServiceUnavailableException("카카오페이 결제 준비 응답이 올바르지 않습니다.")

    session.add(CreditPurchaseOrder(
        partner_order_id=partner_order_id,
        user_id=user_id,
        tid=result["tid"],
        credit_amount=PERSONAL_CREDIT_PACK_SIZE,
        price=PERSONAL_CREDIT_PACK_PRICE,
        status="ready",
    ))
    session.commit()

    return {
        "next_redirect_pc_url": result["next_redirect_pc_url"],
        "tid": result["tid"],
        "item_name": "개인 크레딧 5회권",
        "price": PERSONAL_CREDIT_PACK_PRICE,
        "credit_amount": PERSONAL_CREDIT_PACK_SIZE,
    }

#크레딧 충전 승인 API 엔드포인트
@router.get("/kakao-pay/credits/approve")
async def kakao_credit_purchase_approve(
    pg_token: str = Query(...),
    partner_order_id: str = Query(...),
    session: Session = Depends(get_db),
):
    order = session.execute(
        select(CreditPurchaseOrder)
        .where(CreditPurchaseOrder.partner_order_id == partner_order_id)
        .with_for_update()
    ).scalar_one_or_none()

    if not order or not order.tid or order.status != "ready":
        raise BadRequestException("유효한 크레딧 결제 주문을 찾을 수 없습니다.")

    headers = {
        "Authorization": f"SECRET_KEY {KAKAO_PAYMENT_SECERT_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "cid": KAKAO_PAYMENT_CID,
        "tid": order.tid,
        "partner_order_id": order.partner_order_id,
        "partner_user_id": str(order.user_id),
        "pg_token": pg_token,
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(f"{KAKAO_PAYMENT_BASE_URL}/approve", headers=headers, json=payload)

    if response.status_code != 200:
        logger.warning("[ Log ] : KakaoPay 크레딧 승인 실패 : %s", response.text)
        raise ServiceUnavailableException("카카오페이 결제가 승인되지 않았습니다.")

    approval = response.json()
    paid_total = (approval.get("amount") or {}).get("total")
    if (
        approval.get("tid") != order.tid
        or approval.get("partner_order_id") != order.partner_order_id
        or int(paid_total or 0) != order.price
    ):
        logger.error("[ Log ] : KakaoPay 크레딧 승인 실패 : %s", order.partner_order_id)
        raise ServiceUnavailableException("결제 승인 정보가 주문 내용과 일치하지 않습니다.")

    await fulfill_credit_purchase(order.user_id, order.partner_order_id, order.credit_amount)
    order.status = "approved"
    session.commit()

    return RedirectResponse(
        url=f"{os.getenv('FRONTEND_URL')}/credits/payment?status=success&credits={order.credit_amount}",
        status_code=303,
    )

#크레딧 충전 취소 API 엔드포인트
@router.get("/kakao-pay/credits/cancel")
def kakao_credit_purchase_cancel(partner_order_id: str = Query(...), session: Session = Depends(get_db)):
    _update_credit_purchase_status(session, partner_order_id, "cancelled")
    return RedirectResponse(url=f"{os.getenv('FRONTEND_URL')}/credits/payment?status=cancel", status_code=303)

#크레딧 충전 실패 API 엔드포인트
@router.get("/kakao-pay/credits/fail")
def kakao_credit_purchase_fail(partner_order_id: str = Query(...), session: Session = Depends(get_db)):
    _update_credit_purchase_status(session, partner_order_id, "failed")
    return RedirectResponse(url=f"{os.getenv('FRONTEND_URL')}/credits/payment?status=fail", status_code=303)

def _update_credit_purchase_status(session: Session, partner_order_id: str, new_status: str) -> None:
    order = session.execute(
        select(CreditPurchaseOrder).where(
            CreditPurchaseOrder.partner_order_id == partner_order_id
        )
    ).scalar_one_or_none()
    if order and order.status == "ready":
        order.status = new_status
        session.commit()

#Plan 결제 API 엔드포인트
@router.post("/kakao-pay/plans/ready")
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
        "approval_url": f"{BACKEND_URL}/api/v1/kakao-pay/plans/approve?partner_order_id={partner_order_id}",
        "cancel_url": f"{BACKEND_URL}/api/v1/kakao-pay/plans/cancel?partner_order_id={partner_order_id}",
        "fail_url": f"{BACKEND_URL}/api/v1/kakao-pay/plans/fail?partner_order_id={partner_order_id}"
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


#Plan 결제 승인 API 엔드포인트
@router.get(
    "/kakao-pay/plans/approve"
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

#Plan 결제 취소 API 엔드포인트
@router.get("/kakao-pay/plans/cancel")
def kakao_pay_cancel(partner_order_id: str | None = Query(default=None), session: Session = Depends(get_db)):
    logger.warning("[ Log ] : 결제가 취소되었습니다.")
    _update_payment_status(session, partner_order_id, "cancelled")
    return RedirectResponse(url=f"{os.getenv('FRONTEND_URL')}/payment?status=cancel", status_code=303)

#Plan 결제 실패 API 엔드포인트
@router.get("/kakao-pay/plans/fail")
def kakao_pay_fail(partner_order_id: str | None = Query(default=None), session: Session = Depends(get_db)):
    logger.warning("[ Log ] : 결제가 실패했습니다.")
    _update_payment_status(session, partner_order_id, "failed")
    return RedirectResponse(url=f"{os.getenv('FRONTEND_URL')}/payment?status=fail", status_code=303)

#Plan 결제 정보 업데이트 함수
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