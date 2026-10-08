from pydantic import BaseModel

#결제 요청 스키마
class PaymentRequest(BaseModel):
    item_name: str | None = None
    quantity: int = 1
    price: int | None = None
    tax_free_amount: int = 0