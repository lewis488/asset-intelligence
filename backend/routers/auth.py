from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from database import get_db
from models.user import Authority, User
from schemas.auth import LoginResponse, RegisterRequest, UserOut
from services.auth import create_access_token, decode_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    user = db.query(User).filter(User.id == int(payload["sub"])).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def require_contributor(current_user: User = Depends(get_current_user)) -> User:
    """403 if viewer — blocks upload and analysis-trigger endpoints."""
    if current_user.role == "viewer":
        raise HTTPException(status_code=403, detail="Viewers cannot upload data or trigger analysis")
    return current_user


def resolve_authority_id(
    current_user: User,
    requested: Optional[int] = None,
) -> Optional[int]:
    """
    Returns the authority_id to use for data-scoping queries.

    - Non-admin: always current_user.authority_id; requested param silently ignored.
    - Admin + requested: use requested (allows viewing any authority's data).
    - Admin + no requested: returns None → caller must treat as "no filter" (all authorities).

    Upload endpoints must NOT use this — they always stamp current_user.authority_id
    regardless of admin status, so admins can't accidentally mislabel their own uploads.
    """
    if current_user.role != "admin":
        return current_user.authority_id
    return requested  # None means "all authorities" for admin


@router.post("/register", response_model=UserOut, status_code=201)
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == req.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    authority = db.query(Authority).filter(Authority.name == req.authority_name).first()
    if not authority:
        authority = Authority(name=req.authority_name, region=req.region)
        db.add(authority)
        db.flush()

    user = User(
        authority_id=authority.id,
        email=req.email,
        hashed_password=hash_password(req.password),
        role=req.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=LoginResponse)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == form.username).first()
    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = create_access_token({"sub": str(user.id), "authority_id": user.authority_id})
    return {"access_token": token, "token_type": "bearer", "user": user}
