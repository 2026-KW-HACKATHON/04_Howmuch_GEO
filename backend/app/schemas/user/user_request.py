from pydantic import BaseModel, EmailStr, Field, field_validator
import re

#회원가입 요청 스키마
class UserSignUpRequest(BaseModel):

    #사용자 입력 데이터 검증을 위한 Pydantic 모델 정의
    email: EmailStr = Field(..., description="이메일 주소")
    user_name: str = Field(..., description="아이디")
    password: str = Field(..., min_length=5, description="비밀번호")
    account_type: str = Field(default="personal", pattern="^(personal|leader)$")
    plan_code: str | None = Field(default=None, pattern="^(Standard|Pro|Premium)$")

    @field_validator("password")
    def validate_password(cls, value):

        #비밀번호에 특수문자가 포함되어 있는지 확인
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>_]",value):
            raise ValueError("[ Backend ] : 패스워드에 특수문자가 적어도 하나는 무조건 추가되어 있어야 합니다.")
            
        return value 

#로그인 요청 스키마   
class UserLoginRequest(BaseModel):

    #사용자 입력 데이터 검증을 위한 Pydantic 모델 정의
    user_name: str = Field(..., description="아이디")
    password: str = Field(..., min_length=5, description="비밀번호 입력")

#조직 가입 요청 스키마
class JoinOrganizationRequest(BaseModel):
    invitation_code: str = Field(..., min_length=4, max_length=32)