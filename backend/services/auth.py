from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from backend.config import settings

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
_ALGORITHM = "HS256"
_EXPIRE_HOURS = 8


def hash_password(pw: str) -> str:
    return _pwd.hash(pw)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd.verify(plain, hashed)


def create_access_token(data: dict) -> str:
    payload = {**data, "exp": datetime.now(tz=timezone.utc) + timedelta(hours=_EXPIRE_HOURS)}
    return jwt.encode(payload, settings.jwt_secret, algorithm=_ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[_ALGORITHM])
    except JWTError:
        return None
