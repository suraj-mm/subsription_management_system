import sys
import threading
import time
import urllib.request
import urllib.error
import urllib.parse
import json
import uvicorn
from decimal import Decimal
from backend.app.main import app

sys.stdout.reconfigure(encoding="utf-8")


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


def run_phase2_tests():
    port = 8889
    base_url = f"http://127.0.0.1:{port}"
    config = uvicorn.Config(app=app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    t = threading.Thread(target=server.run, daemon=True)
    t.start()

    time.sleep(2)  # Wait for startup

    print("\n" + "=" * 65)
    print(" 🚀 RUNNING PHASE 2 AUTOMATED CHECKPOINT TEST SUITE")
    print("=" * 65)

    try:
        # 1. Admin Login
        st, admin_auth = make_request(f"{base_url}/auth/login", method="POST", data={
            "username": "admin@brightloop.com",
            "password": "Admin@12345"
        }, form=True)
        assert st == 200
        admin_tok = admin_auth["access_token"]
        print(f"[*] Admin logged in: {admin_auth['user']['email']}")

        # 2. Create Customer
        st, cust_auth = make_request(f"{base_url}/auth/signup", method="POST", data={
            "name": "Phase 2 Customer",
            "email": "customer_p2@example.com",
            "password": "CustomerPass123!"
        })
        assert st == 201
        customer_id = cust_auth["id"]
        print(f"[*] Customer registered: ID {customer_id}")

        # Customer Login
        st, c_login = make_request(f"{base_url}/auth/login", method="POST", data={
            "username": "customer_p2@example.com",
            "password": "CustomerPass123!"
        }, form=True)
        assert st == 200
        customer_tok = c_login["access_token"]

        # 3. Create Staff
        st, staff_user = make_request(f"{base_url}/admin/staff", method="POST", data={
            "name": "Phase 2 Staff",
            "email": "staff_p2@brightloop.com",
            "password": "StaffPass123!"
        }, headers={"Authorization": f"Bearer {admin_tok}"})
        assert st == 201
        print(f"[*] Staff created: {staff_user['email']}")

        st, s_login = make_request(f"{base_url}/auth/login", method="POST", data={
            "username": "staff_p2@brightloop.com",
            "password": "StaffPass123!"
        }, form=True)
        assert st == 200
        staff_tok = s_login["access_token"]

        # 4. Create Tax: GST 18%
        st, tax_resp = make_request(f"{base_url}/taxes", method="POST", data={
            "name": "GST 18%",
            "rate": "18.00",
            "type": "percent"
        }, headers={"Authorization": f"Bearer {admin_tok}"})
        assert st == 201
        tax_id = tax_resp["id"]
        print(f"[Check 1a] Tax created: {tax_resp['name']} (Rate: {tax_resp['rate']}%) ID={tax_id}")

        # 5. Create Product: ERP Core License (1000.00) with default tax_id
        st, prod1 = make_request(f"{base_url}/products", method="POST", data={
            "name": "ERP Core License",
            "type": "service",
            "sales_price": "1000.00",
            "cost_price": "400.00",
            "tax_id": tax_id
        }, headers={"Authorization": f"Bearer {admin_tok}"})
        assert st == 201
        prod1_id = prod1["id"]

        # Add Odoo Variant (+560.00)
        st, var1 = make_request(f"{base_url}/products/{prod1_id}/variants", method="POST", data={
            "attribute": "Brand",
            "value": "Odoo",
            "extra_price": "560.00"
        }, headers={"Authorization": f"Bearer {admin_tok}"})
        assert st == 201
        var1_id = var1["id"]
        print(f"[Check 1b] Product + Odoo variant created: Base={prod1['sales_price']}, Variant extra={var1['extra_price']}")

        # Create Second Product: Implementation Support (2000.00)
        st, prod2 = make_request(f"{base_url}/products", method="POST", data={
            "name": "Implementation Support",
            "type": "service",
            "sales_price": "2000.00",
            "cost_price": "800.00",
            "tax_id": tax_id
        }, headers={"Authorization": f"Bearer {admin_tok}"})
        assert st == 201
        prod2_id = prod2["id"]

        # 6. Create Plans:
        # Plan A: Enterprise Monthly (allow_pause = True)
        st, plan_a = make_request(f"{base_url}/plans", method="POST", data={
            "name": "Enterprise Monthly",
            "price": "5000.00",
            "billing_period": "monthly",
            "min_quantity": 2,
            "auto_close": True,
            "allow_pause": True,
            "allow_early_close": True,
            "allow_renew": True
        }, headers={"Authorization": f"Bearer {admin_tok}"})
        assert st == 201
        plan_a_id = plan_a["id"]
        print(f"[Check 2a] Plan A created: {plan_a['name']} (min_qty={plan_a['min_quantity']}, allow_pause={plan_a['allow_pause']})")

        # Plan B: Strict No-Pause Plan (allow_pause = False)
        st, plan_b = make_request(f"{base_url}/plans", method="POST", data={
            "name": "Strict Annual",
            "price": "12000.00",
            "billing_period": "yearly",
            "min_quantity": 1,
            "allow_pause": False,
            "allow_early_close": False,
            "allow_renew": True
        }, headers={"Authorization": f"Bearer {admin_tok}"})
        assert st == 201
        plan_b_id = plan_b["id"]
        print(f"[Check 2b] Plan B created: {plan_b['name']} (allow_pause={plan_b['allow_pause']})")

        # 7. Create Quotation Template with 2 lines:
        # Line 1: ERP Core + Odoo variant (qty=2)
        # Line 2: Implementation Support (qty=1)
        st, template = make_request(f"{base_url}/quotation-templates", method="POST", data={
            "name": "Standard Odoo Enterprise Bundle",
            "validity_days": 15,
            "plan_id": plan_a_id,
            "lines": [
                {"product_id": prod1_id, "variant_id": var1_id, "quantity": 2},
                {"product_id": prod2_id, "quantity": 1}
            ]
        }, headers={"Authorization": f"Bearer {staff_tok}"})
        assert st == 201
        template_id = template["id"]
        print(f"[Check 2c] Quotation Template created: ID={template_id} with {len(template['lines'])} lines")

        # 8. Create Subscription from Template
        st, sub_resp = make_request(f"{base_url}/subscriptions/from-template/{template_id}", method="POST", data={
            "customer_id": customer_id
        }, headers={"Authorization": f"Bearer {staff_tok}"})
        assert st == 201
        sub_id = sub_resp["id"]
        print(f"[Check 3] Subscription created from template:")
        print(f"    Number: {sub_resp['subscription_number']}")
        print(f"    Status: {sub_resp['status']} (Expected 'Quotation')")
        print(f"    Quote valid until: {sub_resp['quotation_valid_until']}")
        print(f"    Subtotal: {sub_resp['subtotal']}, Tax: {sub_resp['tax_amount']}, Grand Total: {sub_resp['total_amount']}")

        assert sub_resp["status"] == "Quotation"
        assert sub_resp["quotation_valid_until"] is not None

        # Verify line snapshot: Line 1 effective price = 1000 + 560 = 1560
        line1 = next(l for l in sub_resp["lines"] if l["product_id"] == prod1_id)
        assert Decimal(str(line1["unit_price"])) == Decimal("1560.00"), f"Expected 1560.00, got {line1['unit_price']}"
        assert line1["qty"] == 2
        # Line 1 amount: subtotal=3120, tax 18%=561.60 -> total=3681.60
        assert Decimal(str(line1["amount"])) == Decimal("3681.60")

        # 9. Transition: Confirm -> Active
        st, confirmed = make_request(f"{base_url}/subscriptions/{sub_id}/confirm", method="POST", headers={"Authorization": f"Bearer {staff_tok}"})
        assert st == 200
        assert confirmed["status"] == "Confirmed"
        print(f"[Check 4a] Confirmed status: {confirmed['status']}")

        st, activated = make_request(f"{base_url}/subscriptions/{sub_id}/activate", method="POST", headers={"Authorization": f"Bearer {staff_tok}"})
        assert st == 200
        assert activated["status"] == "Active"
        assert activated["next_invoice_date"] == activated["start_date"]
        print(f"[Check 4b] Activated status: {activated['status']}, next_invoice_date set to: {activated['next_invoice_date']}")

        # 10. Pause and Resume flow
        st, paused = make_request(f"{base_url}/subscriptions/{sub_id}/pause", method="POST", headers={"Authorization": f"Bearer {staff_tok}"})
        assert st == 200
        assert paused["status"] == "Paused"
        print(f"[Check 4c] Successfully paused subscription: status={paused['status']}")

        st, resumed = make_request(f"{base_url}/subscriptions/{sub_id}/resume", method="POST", headers={"Authorization": f"Bearer {staff_tok}"})
        assert st == 200
        assert resumed["status"] == "Active"
        print(f"[Check 4d] Successfully resumed subscription: status={resumed['status']}")

        # 11. Test Pause on plan with allow_pause=False -> MUST return 400
        st, sub_b = make_request(f"{base_url}/subscriptions", method="POST", data={
            "customer_id": customer_id,
            "plan_id": plan_b_id,
            "start_date": "2026-11-01",
            "lines": [{"product_id": prod2_id, "qty": 1}]
        }, headers={"Authorization": f"Bearer {staff_tok}"})
        assert st == 201
        sub_b_id = sub_b["id"]

        # Advance to Active: Draft -> Quotation -> Confirmed -> Active
        from backend.app.services.subscription_service import transition_subscription
        # Quick transition via DB or endpoints
        st, _ = make_request(f"{base_url}/subscriptions/{sub_b_id}/confirm", method="POST", headers={"Authorization": f"Bearer {staff_tok}"})
        # Wait, Draft cannot go directly to Confirmed (ALLOWED: Draft -> Quotation -> Confirmed)
        # Verify 400 when jumping states:
        assert st == 400, f"Expected 400 when jumping Draft to Confirmed, got {st}"
        print(f"[Check 5a] State machine enforced: Draft to Confirmed blocked with 400")

        # Let's advance it cleanly:
        from backend.app.database import SessionLocal
        from backend.app.models import Subscription
        db = SessionLocal()
        s_obj = db.query(Subscription).filter(Subscription.id == sub_b_id).first()
        s_obj.status = "Active"
        db.commit()
        db.close()

        # Try to pause sub_b (which has allow_pause=False)
        st, err_resp = make_request(f"{base_url}/subscriptions/{sub_b_id}/pause", method="POST", headers={"Authorization": f"Bearer {staff_tok}"})
        print(f"[Check 5b] Pause on strict plan (allow_pause=False) returned: status={st} detail={err_resp.get('detail')}")
        assert st == 400, f"Expected 400, got {st}"

        # 12. Customer Role Scoping & RBAC Verification
        st, cust_subs = make_request(f"{base_url}/subscriptions", headers={"Authorization": f"Bearer {customer_tok}"})
        assert st == 200
        print(f"[Check 6a] Customer query subscriptions count: {cust_subs['total']}")
        for s in cust_subs["items"]:
            assert s["customer_id"] == customer_id, "Customer must only see their own subscriptions!"

        # Customer attempts to call /confirm -> MUST return 403
        st, err = make_request(f"{base_url}/subscriptions/{sub_id}/confirm", method="POST", headers={"Authorization": f"Bearer {customer_tok}"})
        print(f"[Check 6b] Customer attempting /confirm returned: status={st}")
        assert st == 403, f"Expected 403, got {st}"

        print("\n" + "=" * 65)
        print(" 🎉 ALL PHASE 2 CHECKPOINT REQUIREMENTS PASSED 100%!")
        print("=" * 65 + "\n")

    finally:
        server.should_exit = True


if __name__ == "__main__":
    run_phase2_tests()
