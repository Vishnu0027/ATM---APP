import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# MongoDB Atlas Configuration
# User provided: mongodb+srv://vishnunishath525_db_user:<db_password>@cluster0.i4rr7aw.mongodb.net/?appName=Cluster0
# Password: TjcI0KczUDZmTYuZ
# Database: UniCash
MONGODB_URI = os.getenv(
    "MONGODB_URI",
    "mongodb+srv://vishnunishath525_db_user:TjcI0KczUDZmTYuZ@cluster0.i4rr7aw.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
)
MONGODB_DB_NAME = os.getenv("MONGODB_DB_NAME", "UniCash")

# JWT / Security Configuration
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "atm-unicash-super-secret-key-prod-change-2026")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

# Frontend Directories
FRONTEND_DIR = BASE_DIR / "frontend"
ATM_MACHINE_DIR = BASE_DIR.parent / "atm machine"
