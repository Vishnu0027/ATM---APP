import os
import sqlite3
import json
import certifi
import pymongo
from datetime import datetime, timezone
from bson.objectid import ObjectId
from backend.app.config import MONGODB_URI, MONGODB_DB_NAME, BASE_DIR

import tempfile
from pathlib import Path

# In serverless environments (Vercel), local filesystem is read-only except /tmp
if os.getenv("VERCEL"):
    SQLITE_PATH = Path(tempfile.gettempdir()) / "atm_app.db"
else:
    SQLITE_PATH = BASE_DIR / "database" / "atm_app.db"
    try:
        SQLITE_PATH.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        SQLITE_PATH = Path(tempfile.gettempdir()) / "atm_app.db"

class SQLiteCollection:
    def __init__(self, db_path, table_name):
        self.db_path = str(db_path)
        self.table_name = table_name

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _build_where(self, query):
        if not query:
            return "", []
        conditions = []
        params = []

        if "$or" in query:
            or_clauses = []
            for sub in query["$or"]:
                sub_conds = []
                for k, v in sub.items():
                    col = "id" if k == "_id" else k
                    if isinstance(v, dict) and "$regex" in v:
                        import re
                        pattern = v["$regex"].lstrip("^").rstrip("$")
                        pattern = re.sub(r"\\(.)", r"\1", pattern)
                        sub_conds.append(f"LOWER({col}) = LOWER(?)")
                        params.append(pattern)
                    elif isinstance(v, dict) and "$in" in v:
                        placeholders = ", ".join(["?"] * len(v["$in"]))
                        sub_conds.append(f"{col} IN ({placeholders})")
                        params.extend([str(x) for x in v["$in"]])
                    else:
                        sub_conds.append(f"{col} = ?")
                        params.append(str(v))
                if sub_conds:
                    or_clauses.append(" AND ".join(sub_conds))
            if or_clauses:
                conditions.append(f"({' OR '.join(or_clauses)})")

        for k, v in query.items():
            if k == "$or":
                continue
            col = "id" if k == "_id" else k
            if isinstance(v, dict) and "$regex" in v:
                import re
                pattern = v["$regex"].lstrip("^").rstrip("$")
                pattern = re.sub(r"\\(.)", r"\1", pattern)
                conditions.append(f"LOWER({col}) = LOWER(?)")
                params.append(pattern)
            elif isinstance(v, dict) and "$in" in v:
                placeholders = ", ".join(["?"] * len(v["$in"]))
                conditions.append(f"{col} IN ({placeholders})")
                params.extend([str(x) for x in v["$in"]])
            else:
                conditions.append(f"{col} = ?")
                params.append(str(v))

        where_sql = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        return where_sql, params

    def find_one(self, query):
        conn = self._get_conn()
        cur = conn.cursor()
        try:
            where_sql, params = self._build_where(query)
            sql = f"SELECT * FROM {self.table_name} {where_sql} LIMIT 1"
            cur.execute(sql, params)
            row = cur.fetchone()
            if not row:
                return None
            res = dict(row)
            res["_id"] = str(res["id"])
            return res
        finally:
            conn.close()

    def find(self, query=None):
        conn = self._get_conn()
        cur = conn.cursor()
        try:
            where_sql, params = self._build_where(query)
            sql = f"SELECT * FROM {self.table_name} {where_sql}"
            cur.execute(sql, params)
            rows = cur.fetchall()
            results = []
            for row in rows:
                item = dict(row)
                item["_id"] = str(item["id"])
                results.append(item)
            return results
        finally:
            conn.close()

    def count_documents(self, query=None):
        conn = self._get_conn()
        cur = conn.cursor()
        try:
            where_sql, params = self._build_where(query)
            sql = f"SELECT COUNT(*) as count FROM {self.table_name} {where_sql}"
            cur.execute(sql, params)
            row = cur.fetchone()
            return row["count"] if row else 0
        finally:
            conn.close()

    def insert_one(self, doc):
        conn = self._get_conn()
        cur = conn.cursor()
        try:
            doc_copy = dict(doc)
            doc_copy.pop("_id", None)
            
            # Map column names if needed
            keys = list(doc_copy.keys())
            placeholders = ", ".join(["?"] * len(keys))
            columns = ", ".join(keys)
            values = [str(v) if isinstance(v, (datetime, ObjectId)) else v for v in doc_copy.values()]

            sql = f"INSERT INTO {self.table_name} ({columns}) VALUES ({placeholders})"
            cur.execute(sql, values)
            conn.commit()
            inserted_id = str(cur.lastrowid)

            class InsertResult:
                def __init__(self, i_id):
                    self.inserted_id = i_id
            return InsertResult(inserted_id)
        finally:
            conn.close()

    def insert_many(self, docs):
        for doc in docs:
            self.insert_one(doc)

    def update_one(self, query, update):
        conn = self._get_conn()
        cur = conn.cursor()
        try:
            item = self.find_one(query)
            if not item:
                return
            set_data = update.get("$set", update)
            set_clauses = [f"{k} = ?" for k in set_data.keys()]
            values = [str(v) if isinstance(v, (datetime, ObjectId)) else v for v in set_data.values()]
            values.append(item["id"])
            sql = f"UPDATE {self.table_name} SET {', '.join(set_clauses)} WHERE id = ?"
            cur.execute(sql, values)
            conn.commit()
        finally:
            conn.close()


class ResilientDatabase:
    """Intelligent database adapter providing seamless MongoDB Atlas connectivity with local SQLite fallback."""
    def __init__(self):
        self.atlas_client = None
        self.atlas_db = None
        self.atlas_available = False
        self.last_atlas_error = None
        self._connect_atlas(raise_on_error=False)

        # Local SQLite fallback collections
        self._sqlite_users = SQLiteCollection(SQLITE_PATH, "users")
        self._sqlite_banks = SQLiteCollection(SQLITE_PATH, "linked_banks")
        self._sqlite_sessions = SQLiteCollection(SQLITE_PATH, "atm_sessions")
        self._sqlite_otps = SQLiteCollection(SQLITE_PATH, "atm_otps")
        self._ensure_sqlite_schema()

    def _ensure_sqlite_schema(self):
        conn = sqlite3.connect(str(SQLITE_PATH))
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                mobile TEXT UNIQUE NOT NULL,
                hashed_password TEXT NOT NULL,
                is_active INTEGER DEFAULT 1,
                created_at TEXT
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS linked_banks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                bank_name TEXT NOT NULL,
                bank_code TEXT NOT NULL,
                account_masked TEXT NOT NULL,
                status TEXT DEFAULT 'Verified',
                withdrawal_limit REAL NOT NULL,
                currency TEXT DEFAULT '₹',
                theme_gradient TEXT,
                created_at TEXT
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS atm_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT UNIQUE NOT NULL,
                atm_id TEXT DEFAULT 'ATM-BLR-042',
                user_id TEXT,
                masked_mobile TEXT,
                user_name TEXT,
                status TEXT DEFAULT 'ACTIVE',
                current_step TEXT DEFAULT 'MOBILE_ENTRY',
                otp_verified INTEGER DEFAULT 0,
                demo_otp TEXT,
                attempts INTEGER DEFAULT 0,
                created_at TEXT,
                expires_at TEXT
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS atm_otps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                otp_code TEXT NOT NULL,
                otp_hash TEXT,
                is_used INTEGER DEFAULT 0,
                attempt_count INTEGER DEFAULT 0,
                verification_status TEXT DEFAULT 'PENDING',
                created_at TEXT,
                expires_at TEXT,
                last_resend_at TEXT
            )
        """)
        conn.commit()
        conn.close()

    def _connect_atlas(self, raise_on_error=False):
        """Establish or refresh MongoDB Atlas connection."""
        if self.atlas_client is not None and self.atlas_db is not None and self.atlas_available:
            return self.atlas_db

        try:
            # Resilient timeout for serverless environments (10 seconds)
            client = pymongo.MongoClient(
                MONGODB_URI,
                tlsCAFile=certifi.where(),
                serverSelectionTimeoutMS=10000,
                connectTimeoutMS=10000,
                socketTimeoutMS=20000,
                maxPoolSize=50,
                minPoolSize=0,
                retryWrites=True,
                appName="UniCash-ATM"
            )
            # Ping Atlas to verify connection is alive
            client.admin.command("ping")
            self.atlas_client = client
            self.atlas_db = client[MONGODB_DB_NAME]
            self.atlas_available = True
            self.last_atlas_error = None
            print(f"[*] Connected to MongoDB Atlas '{MONGODB_DB_NAME}' successfully!")
            return self.atlas_db
        except Exception as e:
            self.atlas_available = False
            self.last_atlas_error = f"{type(e).__name__}: {e}"
            is_vercel = bool(os.getenv("VERCEL") or os.getenv("VERCEL_ENV") or os.getenv("NOW_REGION"))
            print(f"[!] MongoDB Atlas connection failed ({type(e).__name__}): {e}")
            if raise_on_error or is_vercel:
                raise RuntimeError(
                    f"MongoDB Atlas connection required on Vercel/Production, but failed ({type(e).__name__}): {e}. "
                    f"Please verify: 1) MONGODB_URI in Vercel settings, 2) MongoDB Atlas Network Access whitelist allows 0.0.0.0/0."
                ) from e
            return None

    def _get_coll(self, name, sqlite_fallback_coll):
        """Retrieve MongoDB Atlas collection, reconnecting if needed. Enforces MongoDB on Vercel."""
        is_vercel = bool(os.getenv("VERCEL") or os.getenv("VERCEL_ENV") or os.getenv("NOW_REGION"))
        # On Vercel or when MONGODB_URI is provided, strictly enforce MongoDB Atlas
        if is_vercel or bool(os.getenv("MONGODB_URI")):
            if not self.atlas_available or self.atlas_db is None:
                self._connect_atlas(raise_on_error=True)
            if self.atlas_db is not None:
                return self.atlas_db[name]
            raise RuntimeError(
                f"MongoDB Atlas collection '{name}' unavailable on Vercel. Error: {self.last_atlas_error}"
            )

        # Local development offline fallback: try connecting first
        if not self.atlas_available or self.atlas_db is None:
            self._connect_atlas(raise_on_error=False)

        if self.atlas_available and self.atlas_db is not None:
            return self.atlas_db[name]

        return sqlite_fallback_coll

    @property
    def users(self):
        return self._get_coll("users", self._sqlite_users)

    @property
    def linked_banks(self):
        return self._get_coll("linked_banks", self._sqlite_banks)

    @property
    def atm_sessions(self):
        return self._get_coll("atm_sessions", self._sqlite_sessions)

    @property
    def atm_otps(self):
        return self._get_coll("atm_otps", self._sqlite_otps)


# Instantiate singleton database
db = ResilientDatabase()

def init_db():
    """Verify database status."""
    db._connect_atlas(raise_on_error=bool(os.getenv("VERCEL") or os.getenv("VERCEL_ENV")))

def get_db():
    """FastAPI dependency providing active database instance."""
    return db
