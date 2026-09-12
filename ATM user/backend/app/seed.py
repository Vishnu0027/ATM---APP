from datetime import datetime, timezone
from backend.app.auth import hash_password

DEMO_USER_EMAIL = "arun@example.com"
DEMO_USER_MOBILE = "9876543210"
DEMO_USER_NAME = "Arun Kumar"
DEMO_USER_PASSWORD = "Password@123"

DEMO_BANKS = [
    {
        "bank_name": "State Bank of India (SBI)",
        "bank_code": "SBI",
        "account_masked": "XXXX XXXX 4521",
        "status": "Verified",
        "withdrawal_limit": 60000.0,
        "currency": "₹",
        "theme_gradient": "linear-gradient(135deg, #0b2f6d 0%, #1e40af 100%)",
    },
    {
        "bank_name": "Canara Bank",
        "bank_code": "CANARA",
        "account_masked": "XXXX XXXX 8192",
        "status": "Verified",
        "withdrawal_limit": 40000.0,
        "currency": "₹",
        "theme_gradient": "linear-gradient(135deg, #0369a1 0%, #0284c7 100%)",
    },
    {
        "bank_name": "Karur Vysya Bank (KVB)",
        "bank_code": "KVB",
        "account_masked": "XXXX XXXX 3317",
        "status": "Verified",
        "withdrawal_limit": 25000.0,
        "currency": "₹",
        "theme_gradient": "linear-gradient(135deg, #065f46 0%, #0d9488 100%)",
    },
]

def seed_demo_banks_for_user(db, user_id: str):
    """Seed the 3 prototype demo banks for a user in MongoDB Atlas if they do not have them."""
    existing_count = db.linked_banks.count_documents({"user_id": str(user_id)})
    if existing_count == 0:
        bank_docs = []
        for bank in DEMO_BANKS:
            doc = dict(bank)
            doc["user_id"] = str(user_id)
            doc["created_at"] = datetime.now(timezone.utc)
            bank_docs.append(doc)
        if bank_docs:
            db.linked_banks.insert_many(bank_docs)

def seed_initial_data(db):
    """Ensure both demo user (Arun Kumar) and Vishnu with PIN 2006 are in the database."""
    # 1. Seed Vishnu (Phone: 987654321, PIN: 2006)
    vishnu = db.users.find_one({
        "$or": [
            {"mobile": "987654321"},
            {"full_name": "Vishnu"}
        ]
    })
    if not vishnu:
        new_vishnu = {
            "full_name": "Vishnu",
            "email": "vishnu@gmail.com",
            "mobile": "987654321",
            "hashed_password": hash_password("2006"),
            "is_active": True,
            "created_at": datetime.now(timezone.utc)
        }
        res_v = db.users.insert_one(new_vishnu)
        vishnu_id = str(res_v.inserted_id)
    else:
        vishnu_id = str(vishnu["_id"])
        # Update PIN to 2006 and mobile to 987654321
        try:
            db.users.update_one(
                {"_id": vishnu["_id"]},
                {"$set": {"hashed_password": hash_password("2006"), "mobile": "987654321", "full_name": "Vishnu"}}
            )
        except Exception:
            pass

    seed_demo_banks_for_user(db, vishnu_id)
    print(f"[*] Pre-seeded user 'Vishnu' (Phone: 987654321, PIN: 2006, ID: {vishnu_id}) and demo banks!")

    # 2. Seed Arun Kumar for automated testing
    user = db.users.find_one({
        "$or": [
            {"email": DEMO_USER_EMAIL},
            {"mobile": DEMO_USER_MOBILE}
        ]
    })
    if not user:
        new_user = {
            "full_name": DEMO_USER_NAME,
            "email": DEMO_USER_EMAIL,
            "mobile": DEMO_USER_MOBILE,
            "hashed_password": hash_password(DEMO_USER_PASSWORD),
            "is_active": True,
            "created_at": datetime.now(timezone.utc)
        }
        res = db.users.insert_one(new_user)
        user_id = str(res.inserted_id)
    else:
        user_id = str(user["_id"])

    seed_demo_banks_for_user(db, user_id)
    print(f"[*] Pre-seeded demo user '{DEMO_USER_NAME}' (ID: {user_id}) and demo banks in MongoDB Atlas!")
