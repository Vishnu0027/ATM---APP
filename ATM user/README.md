# Multi-Bank Cardless ATM (Version 1)

A modern, secure fintech prototype for a **Multi-Bank Cardless ATM** platform. This application allows users to securely authenticate and access multiple linked bank accounts from a single unified interface without carrying multiple physical cards.

---

## Features Implemented in Version 1

### 1. User Registration & Login
- **Full Registration System**:
  - Full Name, Email Address, and Indian Mobile Number validation (10-digit formats starting with 6, 7, 8, 9, or prefixed with `+91`).
  - Secure **bcrypt** password hashing at rest (never stored or transmitted as plain text).
  - Live **Password Strength Indicator** (Weak / Medium / Strong) with real-time complexity requirements checklist.
  - Show / Hide password toggle for all password inputs.
  - Mandatory Terms & Conditions acceptance.
  - Safe client and backend validation rejecting invalid credentials, duplicate emails/mobiles, and mismatched passwords.
- **Secure Authentication & Sessions**:
  - Login by either **Email** or **Mobile Number**.
  - One-click **"Use Demo Account"** button for rapid evaluation.
  - JWT (JSON Web Token) bearer authentication with 24-hour expiration.
  - "Forgot Password" informative dialog.
  - Full logout functionality terminating the active session.

### 2. User Dashboard
- **Personalized Header & Welcome Message**:
  - Displays dynamic greeting: **"Welcome, [User Name]"** (e.g. *"Welcome back, Arun"*).
  - Registered device verification badge and connection status indicator.
- **Four Summary Metric Cards**:
  - **Linked Banks**: `3`
  - **Active Accounts**: `3`
  - **Today's Transactions**: `0`
  - **Security Status**: `Protected ✓`
- **My Banks Section**:
  - Three realistic digital card representations:
    1. **State Bank of India (SBI)** — Status: `Verified`, Limit: `₹60,000`, Account: `XXXX XXXX 4521`
    2. **Canara Bank** — Status: `Verified`, Limit: `₹40,000`, Account: `XXXX XXXX 8192`
    3. **Karur Vysya Bank (KVB)** — Status: `Verified`, Limit: `₹25,000`, Account: `XXXX XXXX 3317`
  - Interactive **"+ Add Bank"** button displaying: *"Bank linking feature will be available in the next version."*
- **Recent Transactions Section**:
  - Clean empty-state interface: *"No transactions yet. Your ATM transactions will appear here."*
  - Context banner explaining cardless ATM withdrawals will unlock in Version 2.
- **Security Status Panel**:
  - Visual security shield displaying:
    - ✓ **Account Protected**
    - ✓ **Password Encrypted**
    - ✓ **Registered Device**
- **Responsive Layout**:
  - Desktop sidebar and top navigation.
  - Mobile & tablet slide-out drawer navigation with hamburger toggle.
  - Non-functional menu items show friendly *"Coming Soon in V2"* dialogs.

---

## Technology Stack

- **Backend**: Python 3.10+ / Python 3.14, FastAPI, Uvicorn, Pydantic v2, PyJWT, bcrypt, python-multipart, pymongo, dnspython
- **Frontend**: Semantic HTML5, Vanilla CSS3 (Custom Fintech Design System, Dark Mode, Glassmorphism), Vanilla JavaScript ES6+
- **Database**: **MongoDB Atlas** (Cloud Cluster: `cluster0.i4rr7aw.mongodb.net`, Database: `UniCash`)

---

## Project Structure

```
d:/Project/ATM user/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI app, CORS, routes & static file serving
│   │   ├── config.py            # Environment configurations & database URL
│   │   ├── database.py          # SQLAlchemy engine & session maker
│   │   ├── models.py            # ORM models (User, LinkedBank)
│   │   ├── schemas.py           # Pydantic schemas with custom validators
│   │   ├── auth.py              # bcrypt password hashing & JWT token dependencies
│   │   ├── seed.py              # Seed script for demo user & prototype banks
│   │   └── routers/
│   │       ├── __init__.py
│   │       ├── auth_router.py   # /api/auth/register, /api/auth/login, /api/auth/me
│   │       ├── bank_router.py   # /api/banks/linked, /api/banks/link-placeholder
│   │       └── dashboard_router.py # /api/dashboard/summary
├── database/
│   ├── schema.sql               # Universal PostgreSQL / SQLite table definitions
│   └── atm_app.db               # SQLite database file (created automatically)
├── frontend/
│   ├── index.html               # Main single-page application structure
│   ├── styles.css               # Modern fintech design system & responsive rules
│   └── app.js                   # Client-side routing, auth state, validations & UI
├── requirements.txt             # Python backend dependencies
├── run.py                       # Single-command launcher script
├── test_api.py                  # Automated test suite for backend & auth flows
└── README.md                    # Project documentation
```

---

## Quick Start Guide

### 1. Prerequisites
- Python 3.10 or higher (Python 3.14 tested and supported)

### 2. Setup Virtual Environment
```bash
# Windows
py -m venv .venv
.\.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Launch the Application
```bash
python run.py
```

Open your browser and navigate to:
**[http://127.0.0.1:8000](http://127.0.0.1:8000)**

API interactive documentation is available at:
**[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)**

---

## Demo Credentials

The database is automatically pre-seeded with the default demo account:

| Field | Value |
| :--- | :--- |
| **Name** | Arun Kumar |
| **Email** | `arun@example.com` |
| **Mobile** | `9876543210` |
| **Password** | `Password@123` |

> **Tip:** You can click the **"Use Demo Account"** button on the login screen to instantly autofill these credentials, or click **"Create Account"** to test registering a new user.

---

## Running the Automated Test Suite

To verify all backend endpoints, validation rules, password hashing, and dashboard counters:

```bash
python test_api.py
```

Expected output:
```
==========================================
ALL 12 BACKEND AUTOMATED TESTS PASSED 100%!
==========================================
```

---

## PostgreSQL Migration

To switch from SQLite to PostgreSQL in production:
1. Set the environment variable:
   ```bash
   export DATABASE_URL="postgresql://username:password@localhost:5432/atm_db"
   ```
2. Run the DDL script in `database/schema.sql` on your PostgreSQL instance if desired, or let SQLAlchemy auto-create tables on startup.
