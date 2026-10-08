from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database.orm import Base

#계정 프로필 DB 모델
class AccountProfile(Base):
    __tablename__ = "account_profile"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("user.user_id", ondelete="CASCADE"),
        primary_key=True
    )

    account_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="personal"
    )

#조직 DB 모델
class Organization(Base):
    __tablename__ = "organization"

    organization_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    leader_user_id: Mapped[int] = mapped_column(
        ForeignKey("user.user_id", ondelete="CASCADE"),
        unique=True,
        nullable=False
    
    )
    plan_code: Mapped[str] = mapped_column(
        String(20),
        nullable=False
    )

    invitation_code: Mapped[str] = mapped_column(
        String(32),
        unique=True,
        nullable=False
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending_payment"
    )

    max_members: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    paid_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

#조직 맴버쉽 DB 모델
class OrganizationMembership(Base):
    __tablename__ = "organization_membership"
    __table_args__ = (UniqueConstraint("user_id", name="uq_org_membership_user"),)

    membership_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organization.organization_id",ondelete="CASCADE"),
        nullable=False
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("user.user_id", ondelete="CASCADE"),
        nullable=False
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending"
    )

    applied_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

#결제정보 DB 모델
class PaymentOrder(Base):
    __tablename__ = "payment_order"

    order_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    partner_order_id: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("user.user_id", ondelete="CASCADE"),
        nullable=False
    )

    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organization.organization_id", ondelete="CASCADE"),
        nullable=False
    )

    plan_code: Mapped[str] = mapped_column(
        String(20),
        nullable=False
    )

    tid: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="ready"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
