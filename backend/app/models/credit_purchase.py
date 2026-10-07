from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database.orm import Base


class CreditPurchaseOrder(Base):
    __tablename__ = "credit_purchase_order"

    order_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    partner_order_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.user_id", ondelete="CASCADE"), nullable=False)
    tid: Mapped[str | None] = mapped_column(String(128), nullable=True)
    credit_amount: Mapped[int] = mapped_column(Integer, nullable=False)
    price: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ready")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
