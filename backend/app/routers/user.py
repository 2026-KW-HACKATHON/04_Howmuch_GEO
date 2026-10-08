import secrets
from fastapi import APIRouter, status, Depends, Request
from sqlalchemy.orm import Session
from sqlalchemy import select, or_
from app.database.database_connection import get_db
from app.models.user import User
from app.models.account import AccountProfile, Organization
from app.auth.encrypt import password_manager
from app.schemas.user.user_request import UserSignUpRequest, UserLoginRequest
from app.schemas.user.user_response import UserSignUpResponse
from app.exceptions.exceptions_handler import BadRequestException, ConflictException, UnauthorizedException
from app.services.credit_service import get_daily_credits
from app.services.plan_service import get_plan
from app.services.organization_service import get_active_organization, get_account_type, has_unlimited_credits

#User 라우터
router = APIRouter(
    prefix="/api/v1",
    tags=["User Router"]
)

#회원가입 API 엔드포인트
@router.post(
    "/user/signup",
    status_code = status.HTTP_201_CREATED,
    response_model = UserSignUpResponse
)
def signup_user_handler(body: UserSignUpRequest, session: Session = Depends(get_db)):

    plan = None

    #계정 종류가 조합장이라면 Plan 조회
    if body.account_type == "leader":
        plan = get_plan(body.plan_code or "")
        if plan is None:
            raise BadRequestException("조합장 가입에는 유효한 플랜 선택이 필요합니다.")
    elif body.plan_code:
        raise BadRequestException("개인 계정에는 조합장 플랜을 선택할 수 없습니다.")

    #같은 아이디 혹은 이메일이 있는지 확인
    user = session.execute(
        select(User).where(
            or_(
                User.user_name == body.user_name,
                User.email == body.email
            )
        )
    ).scalars().all()

    #같은 아이디나 이메일이 존재한다면 ConflictException 발생
    if user:
        for u in user:
            if u.user_name == body.user_name:
                raise ConflictException("이미 존재하는 아이디입니다.")
            if u.email == body.email:
                raise ConflictException("이미 가입된 이메일입니다.")

    #비밀번호 암호화
    hashed_password = password_manager.hash_password(body.password)

    #객체 생성 및 세션 커밋
    user = User(
        user_name = body.user_name,
        email = body.email,
        password = hashed_password,
    )

    session.add(user)
    session.flush()

    session.add(AccountProfile(user_id=user.user_id, account_type=body.account_type))

    #플랜이 존재한다면 초대코드 난수 생성 후 Organization DB 에 정보 저장
    if plan:
        invitation_code = secrets.token_urlsafe(9).replace("-", "").replace("_", "").upper()[:12]
        session.add(Organization(
            leader_user_id=user.user_id,
            plan_code=plan.code,
            invitation_code=invitation_code,
            status="pending_payment",
            max_members=plan.max_members,
        ))
    session.commit()

    #정보 반환
    return {
        "user_id": user.user_id,
        "user_name": user.user_name,
        "email": user.email,
        "account_type": body.account_type,
        "plan_code": plan.code if plan else None,
    }

#로그인 API 엔드포인트
@router.post(
    "/user/login",
    status_code = status.HTTP_200_OK
)
def login_user_handler(request:Request, body: UserLoginRequest, session: Session = Depends(get_db)):

    #사용자 이름으로 사용자 조회
    user = session.execute(
        select(User).where(
            or_(
                User.user_name == body.user_name,
                User.email == body.user_name,
            )
        )
    ).scalar_one_or_none()

    #사용자가 존재하지 않으면 UnauthorizedException 발생
    if not user:
        raise UnauthorizedException("틀린 아이디 혹은 비밀번호입니다.")

    #비밀번호 검증 및 필요시 해시 업데이트
    is_valid, new_hash = password_manager.verify_and_update_password(
        plain_password=body.password,
        hashed_password=user.password
    )

    #비밀번호가 일치하지 않으면 UnauthorizedException 발생
    if not is_valid:
        raise  UnauthorizedException("이메일 또는 비밀번호가 일치하지 않습니다.")

    #비밀번호 해시가 업데이트되었다면 데이터베이스에 반영
    if new_hash:
        user.password = new_hash
        session.commit()

    #로그인 성공 시 세션에 사용자 ID 저장
    request.session.clear()
    request.session["user_id"] = user.user_id
    return {"message": "로그인에 성공했습니다."}

#로그아웃 API 엔드포인트
@router.post(
    "/user/logout",
    status_code = status.HTTP_200_OK
)
def logout_user_handler(request: Request):

    #로그인 상태 확인
    if "user_id" not in request.session:
        raise UnauthorizedException("로그인 상태가 아닙니다.")

    #세션에서 사용자 ID 제거
    request.session.clear()
    return {"message":"로그아웃에 성공했습니다."}

#사용자 정보 조회 API 엔드포인트
@router.get(
    "/user/info",
    status_code = status.HTTP_200_OK
)
def get_user_info_handler(request: Request, session: Session = Depends(get_db)):

    #로그인 상태 확인
    if "user_id" not in request.session:
        raise UnauthorizedException("로그인 상태가 아닙니다.")

    user_id = request.session["user_id"]

    #사용자 정보 조회
    user = session.execute(
        select(User).where(
            User.user_id == user_id
        )
    ).scalar_one_or_none()

    #사용자가 존재하지 않으면 UnauthorizedException 발생
    if not user:
        raise UnauthorizedException("사용자를 찾을 수 없습니다.")

    return {
        "user_id": user.user_id,
        "user_name": user.user_name,
        "email": user.email,
        "account_type": get_account_type(session, user.user_id),
    }

#사용자 크레딧 조회 API 엔드포인트
@router.get(
    "/user/credits",
    status_code=status.HTTP_200_OK,
)
async def get_user_credits_handler(request: Request, session: Session = Depends(get_db)):

    #로그인된 사용자 ID 조회
    user_id = request.session.get("user_id")
    if user_id is None:
        raise UnauthorizedException("로그인이 필요합니다.")
    user_id = int(user_id)

    #사용자가 조합에 가입되어 무제한 크레딧이 제공된다면 무한 제공값으로 반환
    if has_unlimited_credits(session, user_id):
        organization = get_active_organization(session, user_id)
        return {
            "credits_remaining": -1,
            "daily_credits_remaining": -1,
            "purchased_credits": 0,
            "daily_credit_limit": -1,
            "resets_at": organization.paid_until.isoformat(),
            "unlimited": True,
        }

    #개인 사용자라면 잔여 기본 크레딧 반환
    result = await get_daily_credits(user_id)
    return {**result, "unlimited": False}

#사용자 크레딧 초기화 API 엔드포인트
@router.post(
    "/user/credits/reset",
    status_code=status.HTTP_200_OK,
)
async def reset_user_credits_handler(request: Request, session: Session = Depends(get_db)):

    #로그인된 사용자 ID 확인
    user_id = request.session.get("user_id")
    if user_id is None:
        raise UnauthorizedException("로그인이 필요합니다.")

    #사용자가 조합 소속이라 무제한 크레딧이 가능한 상황이라면 크레딧 충전 실패 반환
    if has_unlimited_credits(session, int(user_id)):
        raise BadRequestException("활성 조합 플랜 이용자는 크레딧 충전이 필요하지 않습니다.")

    raise BadRequestException("크레딧은 결제 승인 후 충전됩니다. 크레딧 구매 화면을 이용해 주세요.")