from pydantic import BaseModel

#결제 요청 스키마
class PaymentRequest(BaseModel):
    item_name: str
    quantity: int
    price: int
    tax_free_amount: int