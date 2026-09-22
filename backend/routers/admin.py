"""Administrative management. Every route requires a current active admin."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database import get_db
from models.user import Authority, User
from routers.auth import require_admin
from schemas.admin import AuthorityCreate, AuthorityPatch, AuthorityOut, UserCreate, UserPatch, DataOverviewOut
from schemas.auth import UserOut
from services.auth import hash_password
from services.admin_inventory import data_overview

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


def get_or_404(db, model, object_id):
    obj = db.get(model, object_id)
    if obj is None:
        raise HTTPException(status_code=404, detail=f"{model.__name__} not found")
    return obj


def save(db, obj):
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Conflicting record or invalid authority")
    db.refresh(obj)
    return obj


@router.get("/authorities", response_model=list[AuthorityOut])
def list_authorities(db: Session = Depends(get_db)):
    return db.query(Authority).order_by(Authority.name, Authority.id).all()


@router.post("/authorities", response_model=AuthorityOut, status_code=201)
def create_authority(req: AuthorityCreate, db: Session = Depends(get_db)):
    authority = Authority(**req.model_dump())
    db.add(authority)
    return save(db, authority)


@router.patch("/authorities/{authority_id}", response_model=AuthorityOut)
def update_authority(authority_id: int, req: AuthorityPatch, db: Session = Depends(get_db)):
    authority = get_or_404(db, Authority, authority_id)
    for field, value in req.model_dump(exclude_unset=True).items():
        setattr(authority, field, value)
    return save(db, authority)


@router.get("/users", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db)):
    return db.query(User).order_by(User.id).all()


@router.post("/users", response_model=UserOut, status_code=201)
def create_user(req: UserCreate, db: Session = Depends(get_db)):
    get_or_404(db, Authority, req.authority_id)
    if db.query(User.id).filter(func.lower(User.email) == req.email.lower()).first():
        raise HTTPException(status_code=409, detail="Email already registered")
    user = User(email=str(req.email), hashed_password=hash_password(req.password),
                authority_id=req.authority_id, role=req.role)
    db.add(user)
    return save(db, user)


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(user_id: int, req: UserPatch, db: Session = Depends(get_db)):
    user = get_or_404(db, User, user_id)
    if req.authority_id is not None:
        get_or_404(db, Authority, req.authority_id)
    for field, value in req.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    return save(db, user)


@router.get("/data-overview", response_model=DataOverviewOut)
def get_data_overview(db: Session = Depends(get_db)):
    return data_overview(db)
