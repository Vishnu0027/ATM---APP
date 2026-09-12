import urllib.request
import json

BASE_URL = "http://127.0.0.1:8000"

def request(path, method="GET", data=None, token=None):
    url = f"{BASE_URL}{path}"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = json.dumps(data).encode("utf-8") if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            status_code = resp.status
            content = resp.read().decode("utf-8")
            return status_code, json.loads(content) if content else {}
    except urllib.error.HTTPError as e:
        content = e.read().decode("utf-8")
        return e.code, json.loads(content) if content else {}

def run_tests():
    print("--- 1. Testing Health Endpoint ---")
    status, body = request("/api/health")
    assert status == 200, f"Health check failed: {status} {body}"
    print(f"Health: OK {body}")

    print("\n--- 2. Testing Login with Demo User Email ---")
    status, body = request("/api/auth/login", method="POST", data={
        "identifier": "arun@example.com",
        "password": "Password@123"
    })
    assert status == 200, f"Email login failed: {status} {body}"
    token = body["access_token"]
    assert token, "Token missing from response"
    assert body["user"]["email"] == "arun@example.com"
    assert body["user"]["full_name"] == "Arun Kumar"
    print("Email Login: OK, Token obtained!")

    print("\n--- 3. Testing Login with Demo User Mobile ---")
    status, body = request("/api/auth/login", method="POST", data={
        "identifier": "9876543210",
        "password": "Password@123"
    })
    assert status == 200, f"Mobile login failed: {status} {body}"
    print("Mobile Login: OK!")

    print("\n--- 4. Testing Invalid Login Credentials ---")
    status, body = request("/api/auth/login", method="POST", data={
        "identifier": "arun@example.com",
        "password": "WrongPassword999"
    })
    assert status == 401, f"Expected 401 for invalid login, got {status}"
    print("Invalid Login Rejection: OK (401)")

    print("\n--- 5. Testing Registration Validation (Invalid Indian Phone) ---")
    status, body = request("/api/auth/register", method="POST", data={
        "full_name": "Test Person",
        "email": "testperson@example.com",
        "mobile": "12345",
        "password": "Password@123",
        "confirm_password": "Password@123",
        "terms_accepted": True
    })
    assert status == 422, f"Expected 422 validation error, got {status}"
    print("Invalid Mobile Phone Rejection: OK (422)")

    print("\n--- 6. Testing Registration Validation (Password Mismatch) ---")
    status, body = request("/api/auth/register", method="POST", data={
        "full_name": "Test Person",
        "email": "testperson@example.com",
        "mobile": "9876543299",
        "password": "Password@123",
        "confirm_password": "DifferentPassword@123",
        "terms_accepted": True
    })
    assert status == 422, f"Expected 422 password mismatch, got {status}"
    print("Password Mismatch Rejection: OK (422)")

    import time
    ts = int(time.time()) % 100000
    test_mobile = f"98123{ts:05d}"
    test_email = f"priya.sharma.{ts}@example.com"
    status, body = request("/api/auth/register", method="POST", data={
        "full_name": "Priya Sharma",
        "email": test_email,
        "mobile": test_mobile,
        "password": "SecurePassword@123",
        "confirm_password": "SecurePassword@123",
        "terms_accepted": True
    })
    assert status in (201, 200), f"Registration failed: {status} {body}"
    assert body["full_name"] == "Priya Sharma"
    assert "password" not in body and "hashed_password" not in body, "Password must not be exposed!"
    print(f"New User Registration: OK! Created user ID {body['id']}")

    print("\n--- 8. Testing New User Login ---")
    status, body = request("/api/auth/login", method="POST", data={
        "identifier": test_email,
        "password": "SecurePassword@123"
    })
    assert status == 200, f"Login failed for new user: {status} {body}"
    priya_token = body["access_token"]
    print("New User Login: OK!")

    print("\n--- 9. Testing Authenticated /api/auth/me ---")
    status, body = request("/api/auth/me", token=priya_token)
    assert status == 200 and body["email"] == test_email
    print(f"Auth /me: OK! User={body['full_name']}")

    print("\n--- 10. Testing Dashboard Summary & Banks ---")
    status, body = request("/api/dashboard/summary", token=priya_token)
    assert status == 200
    assert body["linked_banks_count"] == 3, f"Expected 3 linked banks, got {body['linked_banks_count']}"
    assert body["active_accounts_count"] == 3
    assert body["today_transactions_count"] == 0
    assert body["security_status"] == "Protected ✓"
    
    banks = body["banks"]
    assert len(banks) == 3
    bank_names = [b["bank_code"] for b in banks]
    assert "SBI" in bank_names
    assert "CANARA" in bank_names
    assert "KVB" in bank_names
    
    limits = {b["bank_code"]: b["withdrawal_limit"] for b in banks}
    assert limits["SBI"] == 60000.0, f"SBI limit expected 60000, got {limits['SBI']}"
    assert limits["CANARA"] == 40000.0, f"Canara limit expected 40000, got {limits['CANARA']}"
    assert limits["KVB"] == 25000.0, f"KVB limit expected 25000, got {limits['KVB']}"

    print(f"Dashboard Stats: OK! Counters: 3 banks, 3 active accounts, 0 txns, Protected Checkmark")
    print(f"Demo Banks Verified: SBI (INR 60,000), Canara Bank (INR 40,000), KVB (INR 25,000)")

    print("\n--- 11. Testing Placeholder Add Bank Endpoint ---")
    status, body = request("/api/banks/link-placeholder", method="POST", token=priya_token)
    assert status == 200
    assert "Bank linking feature will be available in the next version." in body["message"]
    print(f"Add Bank Placeholder: OK! Message: {body['message']}")

    print("\n--- 12. Testing Logout Endpoint ---")
    status, body = request("/api/auth/logout", method="POST", token=priya_token)
    assert status == 200
    print("Logout: OK!")

    print("\n==========================================")
    print("ALL 12 BACKEND AUTOMATED TESTS PASSED 100%!")
    print("==========================================")

if __name__ == "__main__":
    run_tests()
