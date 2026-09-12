from typing import List, Dict, Any
from fastapi import APIRouter, Depends
from backend.app.database import get_db
from backend.app import schemas
from backend.app.auth import get_current_user

router = APIRouter(prefix="/api/banks", tags=["Banks"])

def format_bank_doc(bank_doc: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": str(bank_doc["_id"]),
        "bank_name": bank_doc["bank_name"],
        "bank_code": bank_doc["bank_code"],
        "account_masked": bank_doc["account_masked"],
        "status": bank_doc.get("status", "Verified"),
        "withdrawal_limit": float(bank_doc["withdrawal_limit"]),
        "currency": bank_doc.get("currency", "₹"),
        "theme_gradient": bank_doc.get("theme_gradient", "linear-gradient(135deg, #1e3a8a, #3b82f6)"),
    }

@router.get("/linked", response_model=List[schemas.LinkedBankResponse])
def get_linked_banks(
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db)
):
    """Retrieve all verified demo linked banks for the current user from MongoDB Atlas."""
    user_id_str = str(current_user["_id"])
    cursor = db.linked_banks.find({"user_id": user_id_str})
    return [format_bank_doc(b) for b in cursor]

@router.post("/link-placeholder")
def placeholder_add_bank(current_user: dict = Depends(get_current_user)):
    """Placeholder endpoint for adding bank accounts."""
    return {
        "status": "info",
        "message": "Bank linking feature will be available in the next version."
    }
