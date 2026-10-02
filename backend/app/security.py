import hashlib
import os
import secrets
from datetime import datetime, timedelta

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from .database import get_db
from . import models


SECRET_KEY = os.getenv(
    "JWT_SECRET",
    "CHANGE_THIS_SECRET_KEY_FOR_PRODUCTION"
)

ALGORITHM = "HS256"

ACCESS_TOKEN_EXPIRE_MINUTES = 24 * 60


oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/auth/login",
    auto_error=False
)


def hash_password(password: str) -> str:

    salt = secrets.token_bytes(16)

    key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        120000
    )

    return (
        salt.hex()
        + ":"
        + key.hex()
    )


def verify_password(
    password: str,
    stored_password: str
) -> bool:

    try:

        salt_hex, key_hex = stored_password.split(":")

        salt = bytes.fromhex(salt_hex)

        expected = bytes.fromhex(key_hex)

        actual = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            120000
        )

        return secrets.compare_digest(
            actual,
            expected
        )

    except Exception:

        return False


def create_access_token(
    email: str,
    role: str
):

    expire = datetime.utcnow() + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )

    payload = {
        "sub": email,
        "role": role,
        "exp": expire
    }

    return jwt.encode(
        payload,
        SECRET_KEY,
        algorithm=ALGORITHM
    )


def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):

    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Please login first."
    )

    if not token:
        raise credentials_error

    try:

        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )

        email = payload.get("sub")

        if not email:
            raise credentials_error

    except JWTError:

        raise credentials_error

    user = (
        db.query(models.User)
        .filter(
            models.User.email == email
        )
        .first()
    )

    if not user:

        raise credentials_error

    return user


def require_admin(
    current_user=Depends(get_current_user)
):

    if current_user.role != "admin":

        raise HTTPException(
            status_code=403,
            detail="Administrator access required."
        )

    return current_user