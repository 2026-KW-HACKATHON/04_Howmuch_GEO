from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.account import AccountProfile, Organization, OrganizationMembership


def get_account_type(session: Session, user_id: int) -> str:
    profile = session.get(AccountProfile, user_id)
    return profile.account_type if profile else "personal"


def get_active_organization(session: Session, user_id: int) -> Organization | None:
    organization = session.execute(
        select(Organization).where(Organization.leader_user_id == user_id)
    ).scalar_one_or_none()
    if organization:
        if organization.status == "active" and organization.paid_until and organization.paid_until > datetime.now(timezone.utc):
            return organization
        return None

    row = session.execute(
        select(OrganizationMembership, Organization)
        .join(Organization, Organization.organization_id == OrganizationMembership.organization_id)
        .where(
            OrganizationMembership.user_id == user_id,
            OrganizationMembership.status == "active",
        )
    ).first()
    if not row:
        return None

    membership, organization = row
    if organization.status != "active" or not organization.paid_until or organization.paid_until <= datetime.now(timezone.utc):
        return None
    return organization


def has_unlimited_credits(session: Session, user_id: int) -> bool:
    return get_active_organization(session, user_id) is not None
