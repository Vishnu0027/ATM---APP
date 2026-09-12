import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# Load environment variables from .env if present (supports local development)
for env_candidate in [BASE_DIR / ".env", BASE_DIR.parent / ".env"]:
    if env_candidate.is_file():
        try:
            from dotenv import load_dotenv
            load_dotenv(dotenv_path=env_candidate)
        except ImportError:
            try:
                with open(env_candidate, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            key, val = line.split("=", 1)
                            key, val = key.strip(), val.strip().strip("'\"")
                            if key not in os.environ:
                                os.environ[key] = val
            except Exception:
                pass
        break

# MongoDB Atlas Configuration
# On Vercel: Provide MONGODB_URI in Vercel Project Settings > Environment Variables
# Locally: Reads from .env file or environment, with fallback to default demo cluster
MONGODB_URI = os.getenv(
    "MONGODB_URI",
    "mongodb+srv://vishnunishath525_db_user:TjcI0KczUDZmTYuZ@cluster0.i4rr7aw.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
)
MONGODB_DB_NAME = os.getenv("MONGODB_DB_NAME", "UniCash")

# JWT / Security Configuration
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "atm-unicash-super-secret-key-prod-change-2026")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 60 * 24))  # 24 hours

# Frontend Directories
FRONTEND_DIR = BASE_DIR / "frontend"
ATM_MACHINE_DIR = BASE_DIR.parent / "atm machine"
