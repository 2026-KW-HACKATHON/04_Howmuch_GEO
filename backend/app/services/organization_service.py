from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.account import AccountProfile, Organization, OrganizationMembership

#계정 종류 반환 함수
def get_account_type(session: Session, user_id: int) -> str:
    profile = session.get(AccountProfile, user_id)
    return profile.account_type if profile else "personal"

#조직 활성화 유무 조회 함수
def get_active_organization(session: Session, user_id: int) -> Organization | None:

    #로그인된 사용자가 조합장인 조직 확인
    organization = session.execute(
        select(Organization).where(
            Organization.leader_user_id == user_id
        )
    ).scalar_one_or_none()

    #조직이 존재한다면 활성화 상태이며, 유효기간이 남았는지 확인
    if organization:
        if organization.status == "active" and organization.paid_until and organization.paid_until > datetime.now(timezone.utc):

            #유효하다면 반환
            return organization
        
        #유효하지 않다면 None 반환
        return None

    #조직 맴버쉽의 상태가 활성화 상태이면서 사용자가 가입되어있는 조직의 첫번째 Join 된 정보 반환
    row = session.execute(
        select(OrganizationMembership, Organization)
        .join(Organization, Organization.organization_id == OrganizationMembership.organization_id)
        .where(
            OrganizationMembership.user_id == user_id,
            OrganizationMembership.status == "active",
        )
    ).first()

    #정보가 없다면 None 반환
    if not row:
        return None

    membership, organization = row

    #조직의 상태가 활성화 상태가 아니거나 기간이 유효하지 않다면 None 반환
    if organization.status != "active" or not organization.paid_until or organization.paid_until <= datetime.now(timezone.utc):
        return None

    #결과 반환
    return organization

#가입된 조합이 활성화되어있는지 확인
def has_unlimited_credits(session: Session, user_id: int) -> bool:
    return get_active_organization(session, user_id) is not None
