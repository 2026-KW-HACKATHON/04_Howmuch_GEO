from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.database.database_connection import get_db
from app.exceptions.exceptions_handler import BadRequestException, ConflictException, UnauthorizedException
from app.models.account import AccountProfile, Organization, OrganizationMembership
from app.models.user import User
from app.services.plan_service import get_plan
from app.schemas.user.user_request import JoinOrganizationRequest

#조직 라우터
router = APIRouter(
    prefix="/api/v1/organization",
    tags=["Organization"]
)

#로그인 된 사용자인지 확인하는 함수
def _require_user_id(request: Request) -> int:
    user_id = request.session.get("user_id")
    if user_id is None:
        raise UnauthorizedException("로그인이 필요합니다.")
    return int(user_id)

#조직의 Plan 이 결제되어 Active 된 상태이며, 사용 가능 기간이 남아있는지 확인하는 함수
def _active_organization(session: Session, organization: Organization) -> bool:
    return organization.status == "active" and organization.paid_until is not None and organization.paid_until > datetime.now(timezone.utc)

#가입된 조직 확인 API 엔드포인트
@router.get("/me")
def get_my_organization(request: Request, session: Session = Depends(get_db)):

    #로그인이 되어있는지 확인
    user_id = _require_user_id(request)

    #계정프로필에서 계정 타입 확인
    profile = session.get(AccountProfile, user_id)
    account_type = profile.account_type if profile else "personal"

    #사용자가 조합장인 조직 조회
    organization = session.execute(
        select(Organization).where(
            Organization.leader_user_id == user_id
        )
    ).scalar_one_or_none()

    #소속된 조직의 맴버쉽 조회
    membership = session.execute(
        select(OrganizationMembership).where(
            OrganizationMembership.user_id == user_id
        )
    ).scalar_one_or_none()

    #사용자가 조합장이라면 반환
    if organization:
        plan = get_plan(organization.plan_code)
        return {
            "account_type": account_type,
            "role": "leader",
            "organization_id": organization.organization_id,
            "plan_code": organization.plan_code,
            "plan_name": plan.name if plan else organization.plan_code,
            "price": plan.price if plan else None,
            "duration_months": plan.duration_months if plan else None,
            "invitation_code": organization.invitation_code if _active_organization(session, organization) else None,
            "organization_status": organization.status,
            "paid_until": organization.paid_until.isoformat() if organization.paid_until else None,
            "max_members": organization.max_members,
            "unlimited_credits": _active_organization(session, organization),
        }

    #사용자가 일반 맴버라면 반환
    if membership:
        organization = session.get(Organization, membership.organization_id)
        plan = get_plan(organization.plan_code) if organization else None
        unlimited = bool(organization and membership.status == "active" and _active_organization(session, organization))
        return {
            "account_type": account_type,
            "role": "member",
            "membership_status": membership.status,
            "organization_name": session.get(User, organization.leader_user_id).user_name if organization else None,
            "plan_name": plan.name if plan else None,
            "price": plan.price if plan else None,
            "duration_months": plan.duration_months if plan else None,
            "paid_until": organization.paid_until.isoformat() if organization and organization.paid_until else None,
            "unlimited_credits": unlimited,
        }

    #사용자가 소속없는 개인 계정이라면 반환
    return {
        "account_type": account_type,
        "role": "personal",
        "unlimited_credits": False
    }

#조직 가입 API 엔드포인트
@router.post(
    "/join",
    status_code=status.HTTP_201_CREATED
)
def apply_to_organization(body: JoinOrganizationRequest, request: Request, session: Session = Depends(get_db)):

    #사용자가 로그인 되어있는지 확인
    user_id = _require_user_id(request)

    #계정 프로필이 개인 계정인지 확인
    profile = session.get(AccountProfile, user_id)
    if profile and profile.account_type != "personal":
        raise BadRequestException("개인 계정만 조합에 가입 신청할 수 있습니다.")

    #초대 가입 코드 파싱
    code = body.invitation_code.strip().upper()

    #초대코드에 대한 조직 조회
    organization = session.execute(
        select(Organization).where(
            Organization.invitation_code == code
        )
    ).scalar_one_or_none()

    #조직이 존재하지 않거나 유효한 조직이 아니라면 Bad Request Exception 반환
    if not organization or not _active_organization(session, organization):
        raise BadRequestException("유효한 조합 코드가 아니거나 플랜 기간이 종료되었습니다.")

    #이미 조합 신청 혹은 가입 상태인지 확인
    existing = session.execute(
        select(OrganizationMembership).where(
            OrganizationMembership.user_id == user_id
        )
    ).scalar_one_or_none()

    if existing:
        raise ConflictException("이미 조합 가입 신청 또는 가입 상태입니다.")

    #위의 해당 사항이 없다면 조직 맴버쉽 DB 에 정보 추가
    membership = OrganizationMembership(organization_id=organization.organization_id, user_id=user_id, status="pending")
    session.add(membership)
    session.commit()

    return {"status": "pending", "message": "조합장 승인 대기 상태입니다."}

#사용자 조합 탈퇴 API 엔드포인트
@router.delete(
    "/leave",
    status_code=status.HTTP_204_NO_CONTENT
)
def leave_organization(request: Request, session: Session = Depends(get_db)):

    #사용자가 로그인 되어있는지 확인
    user_id = _require_user_id(request)

    #사용자의 프로필 조회
    profile = session.get(AccountProfile, user_id)

    #사용자의 계정이 개인 계정이라면 Bad Request Exception 발생
    if profile and profile.account_type != "personal":
        raise BadRequestException("개인 계정만 조합에서 탈퇴할 수 있습니다.")

    #맴버쉽 DB 에서 사용자 id 에 대한 정보 조회
    membership = session.execute(
        select(OrganizationMembership).where(
            OrganizationMembership.user_id == user_id
        )
    ).scalar_one_or_none()

    if not membership:
        raise BadRequestException("탈퇴할 조합 가입 내역이 없습니다.")

    #해당하는 정보 삭제
    session.delete(membership)
    session.commit()

#조직 맴버 조회 API 엔드포인트
@router.get("/members")
def list_members(request: Request, session: Session = Depends(get_db)):

    #로그인된 사용자인지 확인
    user_id = _require_user_id(request)

    #사용자가 조합장인 조직 조회
    organization = session.execute(
        select(Organization).where(
            Organization.leader_user_id == user_id
        )
    ).scalar_one_or_none()

    #사용자가 조합장인 조직이 없다면 Bad Request Exception 발생
    if not organization:
        raise BadRequestException("조합장 계정만 구성원을 관리할 수 있습니다.")

    #사용자가 조합장인 조직의 모든 가입자들 명단 신청일 순으로 조회
    rows = session.execute(
        select(OrganizationMembership, User)
        .join(User, User.user_id == OrganizationMembership.user_id)
        .where(OrganizationMembership.organization_id == organization.organization_id)
        .order_by(OrganizationMembership.applied_at)
    ).all()

    #조회한 맴버들 반환
    return {
        "max_members": organization.max_members,
        "members": [
            {
                "user_id": user.user_id,
                "user_name": user.user_name,
                "email": user.email,
                "status": membership.status,
                "applied_at": membership.applied_at.isoformat(),
            }
            for membership, user in rows
        ],
    }

#맴버 조직 가입 승인 API 엔드포인트
@router.post("/members/{member_user_id}/approve")
def approve_member(member_user_id: int, request: Request, session: Session = Depends(get_db)):

    #사용자가 로그인 되어있는지 확인
    user_id = _require_user_id(request)

    #사용자가 조합장인 조직이 있는지 확인
    organization = session.execute(
        select(Organization).where(
            Organization.leader_user_id == user_id
        )
    ).scalar_one_or_none()

    #사용자가 조합장인 조직이 없거나 활성화된 플랜이 없는 조직의 조합장인 경우 Bad Request Exception 발생
    if not organization or not _active_organization(session, organization):
        raise BadRequestException("활성 플랜이 있는 조합장만 가입을 승인할 수 있습니다.")

    #조직 맴버쉽 DB 에서 사용자가 조합에 대한 신청한 Organization Membership 정보 조회
    membership = session.execute(
        select(OrganizationMembership).where(
            OrganizationMembership.organization_id == organization.organization_id,
            OrganizationMembership.user_id == member_user_id,
        )
    ).scalar_one_or_none()

    #데이터가 없거나 가입 신청 대기중 상태가 아니라면 Bad Request Exception 발생
    if not membership or membership.status != "pending":
        raise BadRequestException("승인 대기 중인 가입 신청을 찾을 수 없습니다.")

    #현재 승인된 인원수 조회
    active_count = session.scalar(
        select(func.count()).select_from(OrganizationMembership).where(
            OrganizationMembership.organization_id == organization.organization_id,
            OrganizationMembership.status == "active",
        )
    ) or 0

    #인원수가 플랜의 최대 인원수를 넘어서게 될 경우 Bad Request Exception 발생
    if active_count >= organization.max_members:
        raise BadRequestException("플랜의 최대 인원에 도달했습니다.")

    #사용자를 조합에 정상적으로 추가
    membership.status = "active"
    membership.approved_at = datetime.now(timezone.utc)
    session.commit()
    return {"status": "active"}

#맴버 삭제 API 엔드포인트
@router.delete(
    "/members/{member_user_id}",
    status_code=status.HTTP_204_NO_CONTENT
)
def remove_member(member_user_id: int, request: Request, session: Session = Depends(get_db)):

    #사용자가 로그인되어있는지 확인
    user_id = _require_user_id(request)

    #사용자가 조합장인 조직 조회
    organization = session.execute(
        select(Organization).where(
            Organization.leader_user_id == user_id
        )
    ).scalar_one_or_none()

    #사용자가 조합장인 조직이 존재하지 않는다면 Bad Request Exception 발생
    if not organization:
        raise BadRequestException("조합장 계정만 구성원을 관리할 수 있습니다.")

    #삭제하려는 맴버의 맴버쉽 정보 조회
    membership = session.execute(
        select(OrganizationMembership).where(
            OrganizationMembership.organization_id == organization.organization_id,
            OrganizationMembership.user_id == member_user_id,
        )
    ).scalar_one_or_none()

    #해당 맴버의 데이터가 없다면 Bad Request Exception 발생
    if not membership:
        raise BadRequestException("해당 구성원을 찾을 수 없습니다.")

    #맴버 삭제
    session.delete(membership)
    session.commit()
