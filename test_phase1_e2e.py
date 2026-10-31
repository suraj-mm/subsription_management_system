import sys
import threading
sys.stdout.reconfigure(encoding="utf-8")
import time
import urllib.request
import urllib.error
import urllib.parse
import json
import uvicorn
from backend.app.main import app
from backend.app.database import engine
from sqlalchemy import inspect


def make_request(url, method="GET", data=None, headers=None, form=False):
    if headers is None:
        headers = {}
    body = None
    if data is not None:
        if form:
            body = urllib.parse.urlencode(data).encode("utf-8")
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        else:
            body = json.dumps(data).encode("utf-8")
            headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            resp_body = resp.read().decode("utf-8")
            return resp.status, json.loads(resp_body) if resp_body else {}
    except urllib.error.HTTPError as e:
        resp_body = e.read().decode("utf-8")
        try:
            parsed = json.loads(resp_body)
        except Exception:
            parsed = {"raw": resp_body}
        return e.code, parsed


def run_all_tests():
    port = 8888
    base_url = f"http://127.0.0.1:{port}"
    config = uvicorn.Config(app=app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    t = threading.Thread(target=server.run, daemon=True)
    t.start()

    time.sleep(2)  # Wait for boot & lifespan

    print("\n" + "=" * 65)
    print(" 🚀 RUNNING PHASE 1 AUTOMATED CHECKPOINT TEST SUITE")
    print("=" * 65)

    try:
        # Checkpoint 0: Schema verification (All 13 tables)
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
        expected_tables = {
            "users", "products", "product_variants", "plans", "taxes",
            "discounts", "quotation_templates", "quotation_template_lines",
            "subscriptions", "subscription_lines", "invoices", "invoice_lines",
            "payments"
        }
        missing = expected_tables - tables
        print(f"[*] Verified Tables: {len(tables)} found. Missing: {list(missing)}")
        assert not missing, f"Missing tables: {missing}"

        # Checkpoint 1: Signup with Abcdef1! (8 chars) is rejected
        status, data = make_request(f"{base_url}/auth/signup", method="POST", data={
            "name": "Short Password User",
            "email": "shortpass@example.com",
            "password": "Abcdef1!"
        })
        print(f"[1] Signup with 8-character password rejected: status={status} detail={data.get('detail')}")
        assert status == 422, f"Expected 422, got {status}"

        # Checkpoint 2: Signup with Abcdef12! (9 chars) succeeds
        status, customer = make_request(f"{base_url}/auth/signup", method="POST", data={
            "name": "Test Customer",
            "email": "customer@example.com",
            "password": "Abcdef12!",
            "company": "Bright Test Ltd",
            "phone": "+91 9998887776"
        })
        print(f"[2] Signup with 9-character valid password: status={status} user={customer.get('email')} role={customer.get('role')}")
        assert status == 201, f"Expected 201, got {status}"
        assert customer.get("role") == "customer"

        # Checkpoint 3: Duplicate email returns 409
        status, err = make_request(f"{base_url}/auth/signup", method="POST", data={
            "name": "Duplicate Customer",
            "email": "customer@example.com",
            "password": "Abcdef12!"
        })
        print(f"[3] Duplicate email signup: status={status} detail={err.get('detail')}")
        assert status == 409, f"Expected 409, got {status}"

        # Checkpoint 4: Login returns JWT and /me returns current user
        status, token_resp = make_request(f"{base_url}/auth/login", method="POST", data={
            "username": "customer@example.com",
            "password": "Abcdef12!"
        }, form=True)
        print(f"[4] Customer login: status={status} role={token_resp.get('role')} token_type={token_resp.get('token_type')}")
        assert status == 200, f"Expected 200, got {status}"
        customer_token = token_resp["access_token"]

        status, me = make_request(f"{base_url}/auth/me", headers={"Authorization": f"Bearer {customer_token}"})
        print(f"[4b] /auth/me verification: status={status} email={me.get('email')} role={me.get('role')}")
        assert status == 200, f"Expected 200, got {status}"
        assert me.get("email") == "customer@example.com"

        # Checkpoint 5: Customer token on /admin/staff returns 403 Forbidden
        status, err = make_request(f"{base_url}/admin/staff", method="POST", data={
            "name": "Unauthorized Staff Attempt",
            "email": "intruder_staff@brightloop.com",
            "password": "StaffPassword123!"
        }, headers={"Authorization": f"Bearer {customer_token}"})
        print(f"[5] Customer forbidden from adding staff: status={status} detail={err.get('detail')}")
        assert status == 403, f"Expected 403, got {status}"

        # Checkpoint 6: Log in as seeded admin, create staff user, then log in as that staff
        status, admin_auth = make_request(f"{base_url}/auth/login", method="POST", data={
            "username": "admin@brightloop.com",
            "password": "Admin@12345"
        }, form=True)
        print(f"[6a] Seeded Admin Login: status={status} role={admin_auth.get('role')}")
        assert status == 200, f"Expected 200, got {status}"
        admin_token = admin_auth["access_token"]

        status, new_staff = make_request(f"{base_url}/admin/staff", method="POST", data={
            "name": "Alex Operations",
            "email": "alex.staff@brightloop.com",
            "password": "StaffPassword123!"
        }, headers={"Authorization": f"Bearer {admin_token}"})
        print(f"[6b] Admin created new staff: status={status} email={new_staff.get('email')} role={new_staff.get('role')}")
        assert status == 201, f"Expected 201, got {status}"
        assert new_staff.get("role") == "staff"

        # Log in as newly created staff
        status, staff_auth = make_request(f"{base_url}/auth/login", method="POST", data={
            "username": "alex.staff@brightloop.com",
            "password": "StaffPassword123!"
        }, form=True)
        print(f"[6c] New Staff Login: status={status} role={staff_auth.get('role')}")
        assert status == 200, f"Expected 200, got {status}"
        assert staff_auth.get("role") == "staff"

        # Checkpoint 7: Forgot-password produces link, reset works, login with new password works
        status, forgot_resp = make_request(f"{base_url}/auth/forgot-password", method="POST", data={
            "email": "customer@example.com"
        })
        print(f"[7a] Forgot Password request: status={status} link={forgot_resp.get('reset_link')}")
        assert status == 200, f"Expected 200, got {status}"
        reset_link = forgot_resp.get("reset_link")
        assert reset_link is not None, "Expected reset_link in response when DEBUG=True"
        reset_token = reset_link.split("token=")[1]

        # Reset password
        status, reset_resp = make_request(f"{base_url}/auth/reset-password", method="POST", data={
            "token": reset_token,
            "new_password": "CustomerNewPass123!"
        })
        print(f"[7b] Password Reset executed: status={status} message={reset_resp.get('message')}")
        assert status == 200, f"Expected 200, got {status}"

        # Old password should fail
        status, _ = make_request(f"{base_url}/auth/login", method="POST", data={
            "username": "customer@example.com",
            "password": "Abcdef12!"
        }, form=True)
        print(f"[7c] Login with old password rejected: status={status}")
        assert status == 401, f"Expected 401, got {status}"

        # New password succeeds
        status, new_auth = make_request(f"{base_url}/auth/login", method="POST", data={
            "username": "customer@example.com",
            "password": "CustomerNewPass123!"
        }, form=True)
        print(f"[7d] Login with new password succeeded: status={status} role={new_auth.get('role')}")
        assert status == 200, f"Expected 200, got {status}"

        # Re-using the same reset token is rejected (fingerprint changed)
        status, err = make_request(f"{base_url}/auth/reset-password", method="POST", data={
            "token": reset_token,
            "new_password": "AnotherNewPass123!"
        })
        print(f"[7e] Re-using old reset token rejected: status={status} detail={err.get('detail')}")
        assert status == 400, f"Expected 400, got {status}"

        # Checkpoint 8: Health check
        status, health = make_request(f"{base_url}/health")
        print(f"[8] System Health: status={status} payload={health}")
        assert status == 200, f"Expected 200, got {status}"

        print("\n" + "=" * 65)
        print(" 🎉 ALL PHASE 1 CHECKPOINT TESTS PASSED WITH 100% SUCCESS!")
        print("=" * 65 + "\n")

    finally:
        server.should_exit = True


if __name__ == "__main__":
    run_all_tests()
