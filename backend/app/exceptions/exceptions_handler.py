from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

#사용자 정의 예외 클래스 정의
class CustomException(Exception):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message

#사용자 정의 Conflict 예외 클래스 정의
class ConflictException(CustomException):
    def __init__(self, message: str = "[ Backend ] : Conflict 409 Error"):
        super().__init__(status_code=status.HTTP_409_CONFLICT, message=message)

#사용자 정의 Unauthorized 예외 클래스 정의
class UnauthorizedException(CustomException):
    def __init__(self, message: str = "[ Backend ] : Unauthorized 401 Error"):
        super().__init__(status_code=status.HTTP_401_UNAUTHORIZED, message=message)

#사용자 정의 Service Unavailable 예외 클래스 정의
class ServiceUnavailableException(CustomException):
    def __init__(self, message: str = "[ Backend ] : Service Unavailable 503 Error"):
        super().__init__(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, message=message)

#사용자 정의 예외 처리기 등록 함수
def add_exception_handlers(app: FastAPI):
    @app.exception_handler(CustomException)
    async def custom_exception_handler(request: Request, exc: CustomException):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "message": exc.message,
            },
        )