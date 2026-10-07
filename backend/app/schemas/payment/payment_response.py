from pydantic import BaseModel
from datetime import datetime

class AmountSchema(BaseModel):
    total: int
    tax_free: int
    vat: int
    point: int
    discount: int
    green_deposit: int

#결제 응답 스키마
class PaymentResponse(BaseModel):
    aid: str
    tid: str
    cid: str
    partner_order_id: str
    partner_user_id: str
    item_name: str
    quantity: int
    amount: AmountSchema
    payment_method_type: str
    created_at: datetime
    approved_at: datetime