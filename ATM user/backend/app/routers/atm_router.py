import re
import secrets
import random
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from bson.objectid import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status

from backend.app.database import get_db
from backend.app import schemas
from backend.app.auth import hash_password, verify_password

router = APIRouter(prefix="/api/atm", tags=["ATM Machine"])

def mask_mobile_number(mobile: str) -> str:
    """Format mobile as ******1234 or ******9876."""
    cleaned = re.sub(r"[^\d]", "", mobile)
    if len(cleaned) >= 4:
        return "******" + cleaned[-4:]
    return "******" + cleaned

def ensure_utc(dt):
    """Normalize datetime strings or naive datetimes to timezone-aware UTC datetime."""
    if dt is None:
        return None
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt.replace("Z", "+00:00"))
        except Exception:
            return None
    if isinstance(dt, datetime):
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    return None

def get_user_by_id(db, user_id: str):
    """Find user in MongoDB by string id or ObjectId."""
    try:
        if ObjectId.is_valid(user_id):
            u = db.users.find_one({"_id": ObjectId(user_id)})
            if u:
                return u
    except Exception:
        pass
    return db.users.find_one({"_id": user_id})

def get_active_session(db, session_id: str):
    """Fetch session and verify not expired."""
    sess = db.atm_sessions.find_one({"session_id": session_id})
    if not sess:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ATM Session not found. Please start a new session."
        )
    if sess.get("status") != "ACTIVE":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"ATM Session is {sess.get('status', 'INVALID').lower()}. Please start a new session."
        )
    
    # Check session timeout (15 mins)
    expires_at = ensure_utc(sess.get("expires_at"))
    if expires_at and datetime.now(timezone.utc) > expires_at:
        db.atm_sessions.update_one(
            {"session_id": session_id},
            {"$set": {"status": "EXPIRED"}}
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ATM session has expired due to inactivity. Please restart your transaction."
        )
    return sess


# ============================================================================
# 1. SESSION INITIALIZATION
# ============================================================================
@router.post("/session/start", response_model=schemas.ATMSessionResponse)
def start_atm_session(db = Depends(get_db)):
    """Initialize a fresh ATM kiosk transaction session."""
    session_id = f"ATM-SESS-{secrets.token_hex(4).upper()}"
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=15)

    session_doc = {
        "session_id": session_id,
        "atm_id": "ATM-BLR-042",
        "status": "ACTIVE",
        "current_step": "MOBILE_ENTRY",
        "user_id": None,
        "masked_mobile": None,
        "user_name": None,
        "otp_verified": False,
        "demo_otp": None,
        "attempts": 0,
        "created_at": now,
        "expires_at": expires_at
    }

    db.atm_sessions.insert_one(session_doc)

    print(f"\n============================================================")
    print(f"[*] NEW ATM TRANSACTION SESSION INITIALIZED: {session_id}")
    print(f"    Terminal: ATM-BLR-042 | Ready for Mobile Entry")
    print(f"============================================================\n")

    return session_doc


# ============================================================================
# 2. STEP 3: ENTER REGISTERED MOBILE NUMBER
# ============================================================================
@router.post("/session/verify-mobile", response_model=schemas.ATMSessionResponse)
def verify_atm_mobile(payload: schemas.ATMMobileRequest, db = Depends(get_db)):
    """Match entered mobile number against existing MongoDB users."""
    session = get_active_session(db, payload.session_id)

    raw_mobile = payload.mobile.strip()
    cleaned = re.sub(r"[\s\-\(\)]", "", raw_mobile)
    if cleaned.startswith("+91"):
        cleaned = cleaned[3:]
    elif cleaned.startswith("91") and len(cleaned) >= 11:
        cleaned = cleaned[2:]
    elif cleaned.startswith("0") and len(cleaned) >= 10:
        cleaned = cleaned[1:]

    # Match existing MongoDB users
    candidates = [
        {"mobile": raw_mobile},
        {"mobile": cleaned},
        {"mobile": f"+91{cleaned}"},
        {"mobile": f"0{cleaned}"}
    ]

    user = db.users.find_one({"$or": candidates})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mobile number not registered with ATM App. Please check your number or register via User App."
        )

    if not user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your ATM account is deactivated. Please contact support."
        )

    user_id_str = str(user["_id"])
    masked = mask_mobile_number(user.get("mobile", cleaned))
    user_name = user.get("full_name", "Cardless Customer")

    db.atm_sessions.update_one(
        {"session_id": payload.session_id},
        {
            "$set": {
                "user_id": user_id_str,
                "masked_mobile": masked,
                "user_name": user_name,
                "current_step": "PIN_ENTRY",
                "attempts": 0
            }
        }
    )

    session["user_id"] = user_id_str
    session["masked_mobile"] = masked
    session["user_name"] = user_name
    session["current_step"] = "PIN_ENTRY"

    print(f"[*] ATM Session {payload.session_id}: Mobile verified for '{user_name}' ({masked})")
    return session


# ============================================================================
# 3. STEP 4: ENTER ATM APP PIN & AUTO-DISPATCH OTP
# ============================================================================
@router.post("/session/verify-pin", response_model=schemas.ATMSessionResponse)
def verify_atm_pin(payload: schemas.ATMPinRequest, db = Depends(get_db)):
    """Verify ATM App PIN against user's hashed password and prepare OTP."""
    session = get_active_session(db, payload.session_id)
    user_id = session.get("user_id")

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please enter your registered mobile number first."
        )

    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User account record could not be found."
        )

    # Verify PIN against hashed password in MongoDB
    pin_input = payload.pin.strip()
    is_valid = verify_password(pin_input, user.get("hashed_password", ""))

    if not is_valid:
        cur_attempts = session.get("attempts", 0) + 1
        db.atm_sessions.update_one(
            {"session_id": payload.session_id},
            {"$set": {"attempts": cur_attempts}}
        )

        if cur_attempts >= 3:
            db.atm_sessions.update_one(
                {"session_id": payload.session_id},
                {"$set": {"status": "CANCELLED"}}
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Maximum PIN attempts exceeded. Transaction cancelled for your security."
            )

        remaining = 3 - cur_attempts
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid ATM App PIN. {remaining} attempt(s) remaining."
        )

    # PIN is correct! Reset attempts and generate initial OTP
    otp_code = f"{random.randint(100000, 999999)}"
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=5)

    # Invalidate prior OTPs for this session
    db.atm_otps.update_one(
        {"session_id": payload.session_id, "is_used": False},
        {"$set": {"is_used": True, "verification_status": "SUPERSEDED"}}
    )

    # Insert new OTP record
    otp_doc = {
        "session_id": payload.session_id,
        "user_id": user_id,
        "otp_code": otp_code,
        "otp_hash": hash_password(otp_code),
        "is_used": False,
        "attempt_count": 0,
        "verification_status": "PENDING",
        "created_at": now,
        "expires_at": expires_at,
        "last_resend_at": now
    }
    db.atm_otps.insert_one(otp_doc)

    # Update session
    db.atm_sessions.update_one(
        {"session_id": payload.session_id},
        {
            "$set": {
                "current_step": "OTP_VERIFICATION",
                "demo_otp": otp_code,
                "attempts": 0
            }
        }
    )

    # Prominently log Demo OTP in backend console
    print("\n" + "=" * 62)
    print(" [DEMO OTP] MULTI-BANK CARDLESS ATM AUTHENTICATION")
    print(f" Session ID   : {payload.session_id}")
    print(f" User         : {session.get('user_name')}")
    print(f" Mobile       : {session.get('masked_mobile')}")
    print(f" Generated OTP: >>> {otp_code} <<<")
    print(" Valid for    : 5 Minutes (Expires: " + expires_at.strftime("%H:%M:%S UTC") + ")")
    print(" Usage Limit  : Single-use, Max 3 attempts")
    print("=" * 62 + "\n")

    session["current_step"] = "OTP_VERIFICATION"
    session["demo_otp"] = otp_code
    return session


# ============================================================================
# 4. STEP 5: BACKEND OTP SEND API (EXPLICIT POST /api/atm/otp/send)
# ============================================================================
@router.post("/otp/send")
def send_atm_otp(payload: schemas.OTPSendRequest, db = Depends(get_db)):
    """Generate and dispatch a 6-digit OTP for the active ATM session."""
    session = get_active_session(db, payload.session_id)
    user_id = payload.user_id or session.get("user_id")

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session has no associated registered user."
        )

    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Associated user account not found in database."
        )

    otp_code = f"{random.randint(100000, 999999)}"
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=5)

    # Invalidate previous unverified OTPs
    db.atm_otps.update_one(
        {"session_id": payload.session_id, "is_used": False},
        {"$set": {"is_used": True, "verification_status": "SUPERSEDED"}}
    )

    otp_doc = {
        "session_id": payload.session_id,
        "user_id": str(user_id),
        "otp_code": otp_code,
        "otp_hash": hash_password(otp_code),
        "is_used": False,
        "attempt_count": 0,
        "verification_status": "PENDING",
        "created_at": now,
        "expires_at": expires_at,
        "last_resend_at": now
    }
    db.atm_otps.insert_one(otp_doc)

    db.atm_sessions.update_one(
        {"session_id": payload.session_id},
        {
            "$set": {
                "current_step": "OTP_VERIFICATION",
                "demo_otp": otp_code
            }
        }
    )

    masked = session.get("masked_mobile") or mask_mobile_number(user.get("mobile", ""))

    print("\n" + "=" * 62)
    print(" [DEMO OTP] OTP DISPATCHED VIA API (/api/atm/otp/send)")
    print(f" Session ID   : {payload.session_id}")
    print(f" Mobile       : {masked}")
    print(f" OTP Code     : >>> {otp_code} <<<")
    print(" Valid for    : 5 Minutes (300 seconds)")
    print("=" * 62 + "\n")

    return {
        "status": "success",
        "message": "OTP generated and sent to registered mobile.",
        "session_id": payload.session_id,
        "masked_mobile": masked,
        "demo_otp": otp_code,
        "expires_in": 300
    }


# ============================================================================
# 5. STEP 5: VERIFY OTP API (POST /api/atm/otp/verify)
# ============================================================================
@router.post("/otp/verify", response_model=schemas.OTPVerifyResponse)
def verify_atm_otp(payload: schemas.OTPVerifyRequest, db = Depends(get_db)):
    """
    Verify 6-digit OTP for active ATM session.
    Checks:
    - Session exists & is ACTIVE
    - OTP exists & belongs to this session
    - OTP is not expired (5 min limit)
    - OTP is not already used
    - Attempt limit (< 3 attempts)
    - OTP match
    """
    session = get_active_session(db, payload.session_id)

    # Fetch latest active OTP for this session
    otp_record = db.atm_otps.find_one(
        {"session_id": payload.session_id, "is_used": False}
    )

    if not otp_record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active OTP found for this session. Please click 'Resend OTP'."
        )

    # 1. Check attempt limit
    attempts = otp_record.get("attempt_count", 0)
    if attempts >= 3:
        db.atm_sessions.update_one(
            {"session_id": payload.session_id},
            {"$set": {"status": "CANCELLED"}}
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum OTP attempts exceeded. Please restart the ATM session."
        )

    # 2. Check expiration (5 minutes)
    expires_at = ensure_utc(otp_record.get("expires_at"))
    if expires_at and datetime.now(timezone.utc) > expires_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OTP expired. Please request a new OTP."
        )

    # 3. Check OTP match
    entered_otp = payload.otp.strip()
    stored_code = str(otp_record.get("otp_code", ""))
    stored_hash = otp_record.get("otp_hash", "")

    is_match = False
    if stored_code and entered_otp == stored_code:
        is_match = True
    elif stored_hash and verify_password(entered_otp, stored_hash):
        is_match = True

    if not is_match:
        new_attempt_count = attempts + 1
        db.atm_otps.update_one(
            {"_id": otp_record["_id"]},
            {"$set": {"attempt_count": new_attempt_count}}
        )

        if new_attempt_count >= 3:
            db.atm_sessions.update_one(
                {"session_id": payload.session_id},
                {"$set": {"status": "CANCELLED"}}
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Maximum OTP attempts exceeded. Please restart the ATM session."
            )

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid OTP. {3 - new_attempt_count} attempt(s) remaining."
        )

    # Correct OTP! Mark OTP used and advance session to BANK_SELECTION
    db.atm_otps.update_one(
        {"_id": otp_record["_id"]},
        {
            "$set": {
                "is_used": True,
                "verification_status": "VERIFIED",
                "verified_at": datetime.now(timezone.utc)
            }
        }
    )

    db.atm_sessions.update_one(
        {"session_id": payload.session_id},
        {
            "$set": {
                "otp_verified": True,
                "current_step": "BANK_SELECTION"
            }
        }
    )

    print(f"[*] ATM Session {payload.session_id}: OTP successfully verified! Advanced to BANK_SELECTION.")

    return {
        "status": "success",
        "message": "OTP verified successfully.",
        "session_id": payload.session_id,
        "current_step": "BANK_SELECTION",
        "otp_verified": True,
        "user_id": session.get("user_id"),
        "masked_mobile": session.get("masked_mobile")
    }


# ============================================================================
# 6. RESEND OTP API (POST /api/atm/otp/resend)
# ============================================================================
@router.post("/otp/resend", response_model=schemas.OTPResendResponse)
def resend_atm_otp(payload: schemas.OTPResendRequest, db = Depends(get_db)):
    """
    Generate new OTP, invalidate previous, enforce 30-sec cooldown,
    and log new DEMO OTP in terminal.
    """
    session = get_active_session(db, payload.session_id)
    user_id = session.get("user_id")

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session has no registered user."
        )

    # Check last resend/created time for 30s cooldown
    last_otp = db.atm_otps.find_one(
        {"session_id": payload.session_id}
    )

    now = datetime.now(timezone.utc)
    if last_otp:
        last_time = last_otp.get("last_resend_at") or last_otp.get("created_at")
        if last_time:
            if isinstance(last_time, str):
                try:
                    last_time = datetime.fromisoformat(last_time.replace("Z", "+00:00"))
                except Exception:
                    last_time = None
            if last_time:
                elapsed_seconds = (now - last_time).total_seconds()
                if elapsed_seconds < 30:
                    remaining = int(30 - elapsed_seconds)
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail=f"Please wait before requesting another OTP. Resend available in {remaining} seconds."
                    )

    # Invalidate all prior OTPs for this session
    db.atm_otps.update_one(
        {"session_id": payload.session_id, "is_used": False},
        {"$set": {"is_used": True, "verification_status": "SUPERSEDED"}}
    )

    # Generate fresh OTP
    new_otp = f"{random.randint(100000, 999999)}"
    expires_at = now + timedelta(minutes=5)

    new_otp_doc = {
        "session_id": payload.session_id,
        "user_id": str(user_id),
        "otp_code": new_otp,
        "otp_hash": hash_password(new_otp),
        "is_used": False,
        "attempt_count": 0,
        "verification_status": "PENDING",
        "created_at": now,
        "expires_at": expires_at,
        "last_resend_at": now
    }
    db.atm_otps.insert_one(new_otp_doc)

    db.atm_sessions.update_one(
        {"session_id": payload.session_id},
        {"$set": {"demo_otp": new_otp}}
    )

    print("\n" + "=" * 62)
    print(" [DEMO OTP RESENT] NEW OTP DISPATCHED")
    print(f" Session ID   : {payload.session_id}")
    print(f" Mobile       : {session.get('masked_mobile')}")
    print(f" New OTP Code : >>> {new_otp} <<<")
    print(" Valid for    : 5 Minutes (Expires: " + expires_at.strftime("%H:%M:%S UTC") + ")")
    print(" Cooldown     : 30 seconds before next resend")
    print("=" * 62 + "\n")

    return {
        "status": "success",
        "message": "OTP resent successfully. Resend available in 30 seconds.",
        "resend_cooldown": 30,
        "demo_otp": new_otp,
        "expires_in": 300
    }


# ============================================================================
# 7. STEP 6: RETRIEVE USER'S LINKED BANKS DYNAMICALLY FROM MONGODB
# ============================================================================
@router.get("/session/{session_id}/banks", response_model=List[schemas.LinkedBankResponse])
def get_atm_session_banks(session_id: str, db = Depends(get_db)):
    """Fetch linked banks from MongoDB for verified ATM session."""
    session = get_active_session(db, session_id)

    if not session.get("otp_verified"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="OTP verification required before accessing linked bank accounts."
        )

    user_id = session.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session has no authenticated user."
        )

    cursor = db.linked_banks.find({"user_id": str(user_id)})
    banks = []
    for b in cursor:
        banks.append({
            "id": str(b["_id"]),
            "bank_name": b["bank_name"],
            "bank_code": b["bank_code"],
            "account_masked": b["account_masked"],
            "status": b.get("status", "Verified"),
            "withdrawal_limit": float(b["withdrawal_limit"]),
            "currency": b.get("currency", "₹"),
            "theme_gradient": b.get("theme_gradient", "linear-gradient(135deg, #1e3a8a, #3b82f6)")
        })

    if not banks:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No linked bank accounts found for this user."
        )

    return banks


# ============================================================================
# 8. STEPS 7-10: WITHDRAWAL TRANSACTION COMPLETION
# ============================================================================
@router.post("/session/withdraw", response_model=schemas.ATMTransactionResponse)
def execute_atm_withdrawal(payload: schemas.ATMWithdrawRequest, db = Depends(get_db)):
    """Complete cash withdrawal transaction on verified ATM session."""
    session = get_active_session(db, payload.session_id)

    if not session.get("otp_verified"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="OTP verification required before dispensing cash."
        )

    user_id = session.get("user_id")

    # Find the chosen bank in MongoDB
    bank = None
    try:
        if ObjectId.is_valid(payload.bank_id):
            bank = db.linked_banks.find_one({"_id": ObjectId(payload.bank_id), "user_id": str(user_id)})
    except Exception:
        pass
    if not bank:
        bank = db.linked_banks.find_one({"_id": payload.bank_id, "user_id": str(user_id)})

    if not bank:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Selected bank account not found or does not belong to this user."
        )

    # Validate 4-digit demo bank PIN
    bank_pin = payload.bank_pin.strip()
    if not bank_pin.isdigit() or len(bank_pin) != 4:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Bank PIN. Demo Bank PIN must be exactly 4 digits."
        )

    # Validate amount
    amount = payload.amount
    if amount <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please enter a valid withdrawal amount greater than zero."
        )
    if amount % 100 != 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ATM notes available in multiples of ₹100, ₹200, and ₹500 only."
        )
    limit = float(bank.get("withdrawal_limit", 40000.0))
    if amount > limit:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Amount exceeds your daily withdrawal limit of ₹{limit:,.2f} for {bank.get('bank_name')}."
        )

    txn_id = f"TXN-ATM-{secrets.token_hex(4).upper()}"
    now = datetime.now(timezone.utc)

    # Mark session completed
    db.atm_sessions.update_one(
        {"session_id": payload.session_id},
        {
            "$set": {
                "status": "COMPLETED",
                "current_step": "COMPLETED",
                "completed_at": now
            }
        }
    )

    print("\n" + "=" * 62)
    print(" [ATM CASH DISPENSED] TRANSACTION SUCCESSFUL")
    print(f" Transaction ID: {txn_id}")
    print(f" Session ID    : {payload.session_id}")
    print(f" Bank          : {bank['bank_name']} ({bank['account_masked']})")
    print(f" Amount        : ₹{amount:,.2f}")
    print(f" Status        : DISPENSED & COMPLETED")
    print("=" * 62 + "\n")

    return {
        "status": "SUCCESS",
        "transaction_id": txn_id,
        "session_id": payload.session_id,
        "amount": float(amount),
        "bank_name": bank["bank_name"],
        "account_masked": bank["account_masked"],
        "atm_id": session.get("atm_id", "ATM-BLR-042"),
        "timestamp": now,
        "message": "Cash dispensed successfully! Please collect your cash from the dispenser."
    }


# ============================================================================
# 9. CANCEL SESSION
# ============================================================================
@router.post("/session/cancel")
def cancel_atm_session(payload: schemas.OTPResendRequest, db = Depends(get_db)):
    """Cancel active ATM session."""
    db.atm_sessions.update_one(
        {"session_id": payload.session_id},
        {"$set": {"status": "CANCELLED"}}
    )
    print(f"[*] ATM Session {payload.session_id} cancelled by user.")
    return {"status": "cancelled", "message": "ATM session has been safely cancelled."}


# ============================================================================
# 10. GET SESSION STATUS
# ============================================================================
@router.get("/session/{session_id}", response_model=schemas.ATMSessionResponse)
def get_session_status(session_id: str, db = Depends(get_db)):
    """Fetch current session state."""
    return get_active_session(db, session_id)
