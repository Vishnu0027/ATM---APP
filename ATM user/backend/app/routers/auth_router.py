import re
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from pymongo.errors import DuplicateKeyError
from backend.app.database import get_db
from backend.app import schemas
from backend.app.auth import hash_password, verify_password, create_access_token, get_current_user, format_user_doc
from backend.app.seed import seed_demo_banks_for_user

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

@router.post("/register", response_model=schemas.UserResponse, status_code=status.HTTP_201_CREATED)
def register_user(payload: schemas.UserRegister, db = Depends(get_db)):
    """Register a new user in MongoDB Atlas, hash PIN, and link demo prototype banks."""
    email_val = payload.email.strip().lower()

    # Check if user with same email exists
    if db.users.find_one({"email": email_val}):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email address already exists."
        )

    # Check if user with same mobile exists
    if db.users.find_one({"mobile": payload.mobile}):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this phone number already exists."
        )

    user_doc = {
        "full_name": payload.full_name,
        "email": email_val,
        "mobile": payload.mobile,
        "hashed_password": hash_password(payload.password),
        "is_active": True,
        "created_at": datetime.now(timezone.utc)
    }

    try:
        res = db.users.insert_one(user_doc)
        user_doc["_id"] = res.inserted_id
    except DuplicateKeyError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this phone number already exists."
        )

    user_id_str = str(res.inserted_id)

    # Pre-link demo banks for prototype experience in MongoDB Atlas
    seed_demo_banks_for_user(db, user_id_str)

    return format_user_doc(user_doc)

@router.post("/login", response_model=schemas.TokenResponse)
def login_user(payload: schemas.UserLogin, db = Depends(get_db)):
    """Authenticate user by phone number, user name, or email and PIN, returning a JWT bearer token."""
    candidates = []

    if payload.mobile:
        m = payload.mobile.strip()
        candidates.append({"mobile": m})
        cleaned_m = re.sub(r"[\s\-\(\)]", "", m)
        candidates.append({"mobile": cleaned_m})
        if cleaned_m.startswith("+91"):
            candidates.append({"mobile": cleaned_m[3:]})
        elif cleaned_m.startswith("91") and len(cleaned_m) >= 11:
            candidates.append({"mobile": cleaned_m[2:]})
        elif cleaned_m.startswith("0") and len(cleaned_m) >= 10:
            candidates.append({"mobile": cleaned_m[1:]})

    if payload.email:
        e = payload.email.strip()
        candidates.append({"email": {"$regex": f"^{re.escape(e)}$", "$options": "i"}})

    if payload.user_name:
        u = payload.user_name.strip()
        candidates.append({"full_name": {"$regex": f"^{re.escape(u)}$", "$options": "i"}})

    if payload.identifier:
        raw_identifier = payload.identifier.strip()
        cleaned_mobile = re.sub(r"[\s\-\(\)]", "", raw_identifier)
        if cleaned_mobile.startswith("+91"):
            cleaned_mobile = cleaned_mobile[3:]
        elif cleaned_mobile.startswith("91") and len(cleaned_mobile) >= 11:
            cleaned_mobile = cleaned_mobile[2:]
        elif cleaned_mobile.startswith("0") and len(cleaned_mobile) >= 10:
            cleaned_mobile = cleaned_mobile[1:]

        candidates.extend([
            {"mobile": raw_identifier},
            {"mobile": cleaned_mobile},
            {"full_name": {"$regex": f"^{re.escape(raw_identifier)}$", "$options": "i"}},
            {"email": {"$regex": f"^{re.escape(raw_identifier)}$", "$options": "i"}}
        ])

    if not candidates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please provide User Name, Email, or Phone Number."
        )

    users = list(db.users.find({"$or": candidates}))

    matched_user = None
    for u in users:
        if verify_password(payload.password, u.get("hashed_password", "")):
            matched_user = u
            break

    if not matched_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials. Please verify your phone number/user name and PIN."
        )

    user = matched_user

    if not user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has been deactivated. Please contact support."
        )

    # Sync email if provided during login (e.g. replacing placeholder or updating to entered email)
    if payload.email and payload.email.strip():
        entered_email = payload.email.strip().lower()
        if re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", entered_email):
            if user.get("email") != entered_email:
                existing_email_user = db.users.find_one({
                    "email": entered_email,
                    "_id": {"$ne": user["_id"]}
                })
                if not existing_email_user:
                    db.users.update_one({"_id": user["_id"]}, {"$set": {"email": entered_email}})
                    user["email"] = entered_email

    user_id_str = str(user["_id"])
    token = create_access_token(user_id=user_id_str, email=user["email"])

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": format_user_doc(user)
    }

@router.post("/update-email", response_model=schemas.UserResponse)
def update_user_email(
    payload: schemas.UpdateEmailPayload,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db)
):
    """Update current user's email address in MongoDB Atlas."""
    new_email = payload.email.strip().lower()
    existing_user = db.users.find_one({
        "email": new_email,
        "_id": {"$ne": current_user["_id"]}
    })
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This email address is already in use by another account."
        )

    db.users.update_one({"_id": current_user["_id"]}, {"$set": {"email": new_email}})
    current_user["email"] = new_email
    return format_user_doc(current_user)

@router.get("/me", response_model=schemas.UserResponse)
def get_authenticated_user(current_user: dict = Depends(get_current_user)):
    """Retrieve current authenticated user profile from MongoDB Atlas."""
    return format_user_doc(current_user)

@router.post("/logout")
def logout_user(current_user: dict = Depends(get_current_user)):
    """Client logout notification."""
    return {"message": "Logged out successfully."}
