import urllib.request
import json
import time

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

def run_atm_tests():
    print("=" * 60)
    print("RUNNING AUTOMATED ATM & OTP VERIFICATION TEST SUITE")
    print("=" * 60)

    # 1. Health check
    print("\n--- 1. Testing Health Endpoint ---")
    status, body = request("/api/health")
    assert status == 200, f"Health check failed: {status} {body}"
    print(f"Health: OK ({body['service']} backed by {body['database']})")

    # 2. Session Initialization
    print("\n--- 2. Initializing ATM Session ---")
    status, body = request("/api/atm/session/start", method="POST")
    assert status == 200, f"Failed to start ATM session: {status} {body}"
    session_id = body["session_id"]
    assert session_id.startswith("ATM-SESS-"), f"Unexpected session ID: {session_id}"
    assert body["status"] == "ACTIVE"
    assert body["current_step"] == "MOBILE_ENTRY"
    print(f"ATM Session initialized: {session_id}")

    # 3. Mobile Verification: Unregistered
    print("\n--- 3. Testing Unregistered Mobile Rejection ---")
    status, body = request("/api/atm/session/verify-mobile", method="POST", data={
        "session_id": session_id,
        "mobile": "9999999999"
    })
    assert status == 404, f"Expected 404 for unregistered mobile, got {status}: {body}"
    print(f"Unregistered mobile correctly rejected: {body['detail']}")

    # 4. Mobile Verification: Registered (Arun Kumar 9876543210)
    print("\n--- 4. Testing Registered Mobile Verification ---")
    status, body = request("/api/atm/session/verify-mobile", method="POST", data={
        "session_id": session_id,
        "mobile": "9876543210"
    })
    assert status == 200, f"Failed registered mobile verification: {status} {body}"
    assert body["masked_mobile"] == "******3210", f"Unexpected masking: {body['masked_mobile']}"
    assert body["user_name"] == "Arun Kumar"
    assert body["current_step"] == "PIN_ENTRY"
    user_id = body["user_id"]
    print(f"Mobile verified: {body['user_name']} ({body['masked_mobile']}) -> Next: {body['current_step']}")

    # 5. PIN Verification: Wrong PIN
    print("\n--- 5. Testing Wrong ATM App PIN Rejection ---")
    status, body = request("/api/atm/session/verify-pin", method="POST", data={
        "session_id": session_id,
        "pin": "WrongPin999"
    })
    assert status == 401, f"Expected 401 for wrong PIN, got {status}: {body}"
    print(f"Wrong PIN correctly rejected: {body['detail']}")

    # 6. PIN Verification: Correct PIN & OTP Dispatch
    print("\n--- 6. Testing Correct PIN & Automatic OTP Generation ---")
    status, body = request("/api/atm/session/verify-pin", method="POST", data={
        "session_id": session_id,
        "pin": "Password@123"
    })
    assert status == 200, f"PIN verification failed: {status} {body}"
    assert body["current_step"] == "OTP_VERIFICATION"
    first_otp = body["demo_otp"]
    assert first_otp and len(first_otp) == 6, f"Invalid generated OTP: {first_otp}"
    print(f"PIN verified! Step: {body['current_step']} | Generated OTP: {first_otp}")

    # 7. OTP Send Endpoint
    print("\n--- 7. Testing Explicit POST /api/atm/otp/send Endpoint ---")
    status, body = request("/api/atm/otp/send", method="POST", data={
        "session_id": session_id,
        "user_id": user_id
    })
    assert status == 200, f"OTP send failed: {status} {body}"
    assert body["status"] == "success"
    active_otp = body["demo_otp"]
    assert len(active_otp) == 6
    print(f"OTP send API successful! OTP: {active_otp} (Expires in: {body['expires_in']}s)")

    # 8. OTP Verification: Wrong OTP
    print("\n--- 8. Testing Invalid OTP Rejection ---")
    status, body = request("/api/atm/otp/verify", method="POST", data={
        "session_id": session_id,
        "otp": "000000" if active_otp != "000000" else "111111"
    })
    assert status == 400, f"Expected 400 for bad OTP, got {status}: {body}"
    print(f"Invalid OTP correctly rejected: {body['detail']}")

    # 9. OTP Resend with Cooldown Enforcement
    print("\n--- 9. Testing OTP Resend & 30-Second Cooldown ---")
    # First resend (cooldown from send was 0 or just now)
    status, body = request("/api/atm/otp/resend", method="POST", data={
        "session_id": session_id
    })
    if status == 429:
        print(f"Cooldown active as expected: {body['detail']}")
        time.sleep(1)
    else:
        assert status == 200, f"Resend failed: {status} {body}"
        active_otp = body["demo_otp"]
        print(f"Resend succeeded! New OTP: {active_otp}")

        # Immediate second resend MUST fail due to 30s cooldown
        status2, body2 = request("/api/atm/otp/resend", method="POST", data={
            "session_id": session_id
        })
        assert status2 == 429, f"Expected 429 cooldown error, got {status2}: {body2}"
        print(f"Cooldown correctly enforced on rapid resend: {body2['detail']}")

    # 10. OTP Verification: Correct OTP
    print("\n--- 10. Testing Correct OTP Verification ---")
    status, body = request("/api/atm/otp/verify", method="POST", data={
        "session_id": session_id,
        "otp": active_otp
    })
    assert status == 200, f"OTP verification failed: {status} {body}"
    assert body["status"] == "success"
    assert body["otp_verified"] == True
    assert body["current_step"] == "BANK_SELECTION"
    print(f"OTP Verified! Status: {body['status']} | Next Step: {body['current_step']}")

    # 11. OTP Single-Use Enforcement
    print("\n--- 11. Testing Single-Use OTP Enforcement ---")
    status, body = request("/api/atm/otp/verify", method="POST", data={
        "session_id": session_id,
        "otp": active_otp
    })
    assert status == 400, f"Expected 400 for reused OTP, got {status}: {body}"
    print(f"Reused OTP correctly rejected: {body['detail']}")

    # 12. Fetch Dynamic Linked Banks from MongoDB
    print("\n--- 12. Testing Dynamic Retrieval of User Linked Banks from MongoDB ---")
    status, banks = request(f"/api/atm/session/{session_id}/banks")
    assert status == 200, f"Failed to get session banks: {status} {banks}"
    assert len(banks) >= 3, f"Expected at least 3 linked banks, got {len(banks)}"
    bank_codes = [b["bank_code"] for b in banks]
    assert "SBI" in bank_codes, "SBI missing from linked banks"
    assert "CANARA" in bank_codes, "Canara Bank missing from linked banks"
    assert "KVB" in bank_codes, "KVB missing from linked banks"
    print(f"Linked banks retrieved successfully from MongoDB Atlas: {bank_codes}")

    # Also test the user_id route
    status_u, user_banks = request(f"/api/users/{user_id}/linked-banks")
    assert status_u == 200
    assert len(user_banks) == len(banks)
    print(f"Endpoint GET /api/users/{user_id}/linked-banks verified ({len(user_banks)} banks)")

    # 13. Test Cash Withdrawal
    print("\n--- 13. Testing Complete Cash Withdrawal Transaction ---")
    sbi_bank = next(b for b in banks if b["bank_code"] == "SBI")
    status, txn = request("/api/atm/session/withdraw", method="POST", data={
        "session_id": session_id,
        "bank_id": sbi_bank["id"],
        "bank_pin": "1234",
        "amount": 2000.0
    })
    assert status == 200, f"Withdrawal failed: {status} {txn}"
    assert txn["status"] == "SUCCESS"
    assert txn["amount"] == 2000.0
    assert txn["bank_name"] == sbi_bank["bank_name"]
    assert "TXN-ATM-" in txn["transaction_id"]
    print(f"Cash dispensed: ₹{txn['amount']} from {txn['bank_name']}! Ref: {txn['transaction_id']}")

    print("\n" + "=" * 60)
    print("ALL 13 ATM & OTP VERIFICATION TESTS PASSED 100%!")
    print("=" * 60)

if __name__ == "__main__":
    run_atm_tests()
