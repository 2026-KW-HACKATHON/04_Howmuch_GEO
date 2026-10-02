from fastapi import APIRouter, status, Depends, Request
from sqlalchemy.orm import Session
from sqlalchemy import select, or_
from app.database.database_connection import get_db
from app.models.user import User
from app.auth.encrypt import password_manager
from app.schemas.user.user_request import UserSignUpRequest, UserLoginRequest
from app.schemas.user.user_response import UserSignUpResponse
from app.exceptions.exceptions_handler import ConflictException, UnauthorizedException

#User 라우터
router = APIRouter(
    prefix="/api/v1",
    tags=["User"]
)

#회원가입 API 엔드포인트
@router.post(
    "/user/signup",
    status_code = status.HTTP_201_CREATED,
    response_model = UserSignUpResponse
)
def signup_user_handler(body: UserSignUpRequest, session: Session = Depends(get_db)):

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
    session.commit()
    session.refresh(user)

    return user

#로그인 API 엔드포인트
@router.post(
    "/user/login",
    status_code = status.HTTP_200_OK
)
def login_user_handler(request:Request, body: UserLoginRequest, session: Session = Depends(get_db)):

    #사용자 이름으로 사용자 조회
    user = session.execute(
        select(User).where(
            User.user_name == body.user_name
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