from datetime import datetime
from sqlalchemy import Integer, String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.orm import Base

#사용자 테이블 구조 정의
class User(Base):
    __tablename__ = "user"

    user_id: Mapped[int] = mapped_column(
        Integer,
        primary_key = True,
        autoincrement = True,
    )

    user_name: Mapped[str] = mapped_column(
        String(255),
        unique = True,
        nullable = False,
    )

    email: Mapped[str] = mapped_column(
        String(255),
        unique = True,
        index = True,
        nullable = False,
    )

    password: Mapped[str] = mapped_column(
        String(255),
        nullable = False,
    )