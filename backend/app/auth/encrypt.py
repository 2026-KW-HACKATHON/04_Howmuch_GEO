from typing import Tuple
from pwdlib import PasswordHash
from pwdlib.exceptions import PwdlibError

#Pwdlib 기반 PasswordManager 클래스
class PasswordManager:

    #PasswordManager 클래스 초기화
    def __init__(self) -> None:
        self._hasher: PasswordHash = PasswordHash.recommended()

    #비밀번호 해싱
    def hash_password(self, password: str) -> str:
        if not password or not password.strip():
            raise ValueError("비밀번호는 공백이거나 비어있을 수 없습니다.")
        return self._hasher.hash(password)

    #비밀번호 검증
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        if not plain_password or not hashed_password:
            return False
        try:
            return self._hasher.verify(plain_password, hashed_password)
        except (PwdlibError, ValueError):
            return False

    #비밀번호 검증 및 필요시 해시 업데이트
    def verify_and_update_password(self, plain_password: str, hashed_password: str) -> Tuple[bool, str | None]:
        if not plain_password or not hashed_password:
            return False, None
        try:
            is_valid, updated_hash = self._hasher.verify_and_update(
                plain_password, hashed_password
            )
            return is_valid, updated_hash
        except (PwdlibError, ValueError):
            return False, None

#PasswordManager 인스턴스 생성
password_manager = PasswordManager()