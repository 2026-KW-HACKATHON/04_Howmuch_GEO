from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database.orm import Base

#조직 시나리오 DB 모델
class OrganizationScenario(Base):
    __tablename__ = "organization_scenarios"

    scenario_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organization.organization_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    scenario_name: Mapped[str] = mapped_column(String(60), nullable=False)

    scenario_data: Mapped[dict] = mapped_column(JSON, nullable=False)

    updated_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("user.user_id", ondelete="CASCADE"),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

#이전 시나리오 자료 이전용 DB 모델
class LegacyOrganizationScenario(Base):
    __tablename__ = "organization_scenario"

    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organization.organization_id", ondelete="CASCADE"),
        primary_key=True,
    )

    scenario_data: Mapped[dict] = mapped_column(JSON, nullable=False)

    updated_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("user.user_id", ondelete="CASCADE"),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
