from pydantic import BaseModel

#회원가입 응답 스키마
class UserSignUpResponse(BaseModel):
    user_id: int
    user_name: str
    email: str