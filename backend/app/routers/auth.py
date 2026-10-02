from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import models, schemas, security
from ..database import get_db


router = APIRouter(
    prefix="/api/auth",
    tags=["Authentication"]
)


@router.post("/register")
def register(
    payload: schemas.UserCreate,
    db: Session = Depends(get_db)
):

    existing = (
        db.query(models.User)
        .filter(
            models.User.email == payload.email
        )
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=400,
            detail="Email already registered."
        )

    user = models.User(
        email=payload.email,
        full_name=payload.full_name,
        hashed_password=security.hash_password(
            payload.password
        ),
        role="user"
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    settings = models.UserSettings(
        user_id=user.id,
        email_address=user.email
    )

    db.add(settings)
    db.commit()

    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.name,
        "role": user.role
    }


@router.post("/login")
def login(
    payload: schemas.LoginRequest,
    db: Session = Depends(get_db)
):

    user = (
        db.query(models.User)
        .filter(
            models.User.email == payload.email
        )
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password."
        )

    if not security.verify_password(
        payload.password,
        user.hashed_password
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password."
        )

    token = security.create_access_token(
        user.email,
        user.role
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "role": user.role
        }
    }


@router.get("/me")
def me(
    current_user=Depends(
        security.get_current_user
    )
):

    return {
        "id": current_user.id,
        "email": current_user.email,
        "name": current_user.full_name,
        "role": current_user.role
    }