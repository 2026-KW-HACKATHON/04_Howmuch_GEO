from dataclasses import dataclass
import calendar
from datetime import datetime

#Plan 데이터 구조도
@dataclass(frozen=True)
class Plan:
    code: str
    name: str
    max_members: int
    duration_months: int
    price: int

#Plan 종류
PLANS = {
    "Standard": Plan("Standard", "Standard", 10, 1, 10000),
    "Pro": Plan("Pro", "Pro", 30, 6, 50000),
    "Premium": Plan("Premium", "Premium", 50, 12, 100000),
}

#Plan 조회 함수
def get_plan(plan_code: str) -> Plan | None:
    return PLANS.get(plan_code.strip().title())

#Plan 기간 계산 함수
def add_plan_duration(start: datetime, months: int) -> datetime:
    month_index = start.year * 12 + start.month - 1 + months
    year, month_zero_indexed = divmod(month_index, 12)
    month = month_zero_indexed + 1
    day = min(start.day, calendar.monthrange(year, month)[1])
    return start.replace(year=year, month=month, day=day)
