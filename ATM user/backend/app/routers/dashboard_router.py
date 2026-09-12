from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from backend.app.database import get_db
from backend.app import schemas
from backend.app.auth import get_current_user, format_user_doc
from backend.app.routers.bank_router import format_bank_doc

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])

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

@router.get("/summary", response_model=schemas.DashboardSummaryResponse)
def get_dashboard_summary(
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db)
):
    """Retrieve summarized statistics and linked accounts from MongoDB Atlas UniCash."""
    user_id_str = str(current_user["_id"])
    banks_cursor = db.linked_banks.find({"user_id": user_id_str})
    formatted_banks = [format_bank_doc(b) for b in banks_cursor]
    bank_count = len(formatted_banks)

    return {
        "user": format_user_doc(current_user),
        "linked_banks_count": bank_count,
        "active_accounts_count": bank_count,
        "today_transactions_count": 0,
        "security_status": "Protected ✓",
        "banks": formatted_banks
    }

@router.get("/active-otp", response_model=schemas.ActiveOTPResponse)
def get_user_active_otp(
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db)
):
    """
    Retrieve any pending, unexpired OTP linked to an active ATM session for this user.
    Used by the ATM User Web App to simulate a push/in-app 2FA notification.
    """
    user_id_str = str(current_user["_id"])
    now = datetime.now(timezone.utc)

    # Query unverified pending OTPs for this user
    cursor = db.atm_otps.find({
        "user_id": user_id_str,
        "is_used": False,
        "verification_status": "PENDING"
    })
    if hasattr(cursor, "sort"):
        cursor = cursor.sort("created_at", -1)
    
    otp_list = list(cursor)

    for otp_doc in otp_list:
        expires_at = ensure_utc(otp_doc.get("expires_at"))
        if not expires_at or now >= expires_at:
            continue

        session_id = otp_doc.get("session_id")
        if not session_id:
            continue

        # Verify associated ATM kiosk session is active
        session = db.atm_sessions.find_one({"session_id": session_id})
        if not session or session.get("status") != "ACTIVE" or session.get("current_step") != "OTP_VERIFICATION":
            continue

        remaining_seconds = max(0, int((expires_at - now).total_seconds()))
        created_at_dt = ensure_utc(otp_doc.get("created_at")) or now

        return {
            "has_active_otp": True,
            "otp": {
                "session_id": session_id,
                "atm_id": session.get("atm_id", "ATM-BLR-042"),
                "otp_code": str(otp_doc.get("otp_code", "")),
                "expires_in_seconds": remaining_seconds,
                "created_at": created_at_dt.isoformat(),
                "expires_at": expires_at.isoformat()
            }
        }

    return {
        "has_active_otp": False,
        "otp": None
    }

